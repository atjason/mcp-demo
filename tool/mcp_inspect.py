"""
检测指定 MCP 端点（Streamable HTTP）的完整信息：服务器信息、能力、工具列表及参数等。
用法: python tool/mcp_inspect.py [URL] [--json]
默认 URL: http://127.0.0.1:8001/mcp
"""
import argparse
import asyncio
import json
import sys
from contextlib import AsyncExitStack

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

DEFAULT_URL = "http://127.0.0.1:8001/mcp"


def _capabilities_summary(caps) -> dict:
    """将 ServerCapabilities 转为可序列化的摘要 dict。"""
    if caps is None:
        return {}
    out = {}
    if getattr(caps, "tools", None) is not None:
        out["tools"] = True
    if getattr(caps, "resources", None) is not None:
        out["resources"] = True
    if getattr(caps, "prompts", None) is not None:
        out["prompts"] = True
    if getattr(caps, "completions", None) is not None:
        out["completions"] = True
    if getattr(caps, "tasks", None) is not None:
        out["tasks"] = True
    if getattr(caps, "logging", None) is not None:
        out["logging"] = True
    if getattr(caps, "experimental", None):
        out["experimental"] = caps.experimental
    return out


def _tool_to_dict(t) -> dict:
    """将 Tool 转为可序列化的 dict。"""
    d = {
        "name": t.name,
        "description": t.description,
        "inputSchema": t.inputSchema,
    }
    if t.title is not None:
        d["title"] = t.title
    if t.outputSchema is not None:
        d["outputSchema"] = t.outputSchema
    if getattr(t, "annotations", None) is not None:
        d["annotations"] = (
            t.annotations.model_dump() if hasattr(t.annotations, "model_dump") else t.annotations
        )
    if getattr(t, "meta", None) is not None:
        d["meta"] = t.meta
    if getattr(t, "execution", None) is not None:
        d["execution"] = (
            t.execution.model_dump() if hasattr(t.execution, "model_dump") else t.execution
        )
    return d


def _server_info_to_dict(init_result) -> dict:
    """从 InitializeResult 提取可序列化的服务器信息。"""
    info = init_result.serverInfo
    d = {
        "protocolVersion": init_result.protocolVersion,
        "serverInfo": {
            "name": info.name,
            "version": info.version,
        },
        "capabilities": _capabilities_summary(init_result.capabilities),
    }
    if getattr(info, "title", None) is not None:
        d["serverInfo"]["title"] = info.title
    if getattr(info, "websiteUrl", None) is not None:
        d["serverInfo"]["websiteUrl"] = info.websiteUrl
    if getattr(init_result, "instructions", None) and init_result.instructions:
        d["instructions"] = init_result.instructions
    return d


async def detect(url: str) -> dict:
    """连接 MCP 端点，执行 initialize 与 list_tools，返回完整信息 dict。"""
    result = {"url": url, "server": {}, "tools": [], "resources": [], "prompts": []}

    async with AsyncExitStack() as exit_stack:
        try:
            read, write, _ = await exit_stack.enter_async_context(streamable_http_client(url))
        except Exception as e:
            print(f"连接失败 {url}: {e}", file=sys.stderr)
            sys.exit(1)

        session = ClientSession(read, write)
        await exit_stack.enter_async_context(session)

        try:
            init_result = await session.initialize()
        except Exception as e:
            print(f"initialize 失败: {e}", file=sys.stderr)
            sys.exit(1)

        result["server"] = _server_info_to_dict(init_result)
        caps = init_result.capabilities

        try:
            list_result = await session.list_tools()
        except Exception as e:
            print(f"list_tools 失败: {e}", file=sys.stderr)
            sys.exit(1)

        result["tools"] = [_tool_to_dict(t) for t in list_result.tools]

        if getattr(caps, "resources", None) is not None:
            try:
                res_list = await session.list_resources()
                result["resources"] = [
                    {"uri": r.uri, "name": getattr(r, "name", None), "description": getattr(r, "description", None)}
                    for r in (res_list.resources or [])
                ]
            except Exception:
                result["resources"] = []

        if getattr(caps, "prompts", None) is not None:
            try:
                prompts_list = await session.list_prompts()
                result["prompts"] = [
                    {"name": p.name, "description": getattr(p, "description", None)}
                    for p in (prompts_list.prompts or [])
                ]
            except Exception:
                result["prompts"] = []

    return result


def print_readable(data: dict) -> None:
    """以可读格式打印检测结果。"""
    url = data.get("url", "")
    server = data.get("server", {})
    tools = data.get("tools", [])
    resources = data.get("resources", [])
    prompts = data.get("prompts", [])

    print("=" * 60)
    print("MCP 端点:", url)
    print("=" * 60)

    si = server.get("serverInfo", {})
    print("\n[ 服务器信息 ]")
    print("  协议版本:", server.get("protocolVersion", ""))
    print("  服务名:  ", si.get("name", ""))
    print("  版本:    ", si.get("version", ""))
    if si.get("title"):
        print("  标题:    ", si["title"])
    if si.get("websiteUrl"):
        print("  网址:    ", si["websiteUrl"])
    if server.get("instructions"):
        instr = server["instructions"]
        print("  说明:    ", instr[:200] + ("..." if len(instr) > 200 else ""))

    cap = server.get("capabilities", {})
    if cap:
        print("\n[ 能力 ]")
        for k, v in cap.items():
            if k != "experimental" and isinstance(v, bool):
                print(f"  {k}: {v}")
        if cap.get("experimental"):
            print("  experimental:", cap["experimental"])

    print("\n[ 工具 ] 共", len(tools), "个")
    for t in tools:
        print("\n  ---", t.get("name", ""))
        if t.get("title"):
            print("  title:", t["title"])
        if t.get("description"):
            desc = (t["description"] or "")[:300]
            print("  description:", desc)
        schema = t.get("inputSchema") or {}
        props = schema.get("properties") or {}
        req = schema.get("required") or []
        if props or req:
            print("  parameters:")
            for name, prop in props.items():
                req_mark = " (required)" if name in req else ""
                typ = prop.get("type", prop.get("description", ""))
                print(f"    - {name}: {typ}{req_mark}")
        if t.get("outputSchema"):
            print("  outputSchema: (已包含，可用 --json 查看)")

    if resources:
        print("\n[ 资源 ] 共", len(resources), "个")
        for r in resources:
            print("  -", r.get("uri"), r.get("name") or "")

    if prompts:
        print("\n[ Prompts ] 共", len(prompts), "个")
        for p in prompts:
            print("  -", p.get("name"), p.get("description") or "")

    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="检测 MCP 端点信息（服务器、能力、工具及参数）",
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=DEFAULT_URL,
        help=f"MCP Streamable HTTP 地址 (默认: {DEFAULT_URL})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出",
    )
    args = parser.parse_args()
    url = args.url.strip() if args.url else DEFAULT_URL

    if not url.startswith("http://") and not url.startswith("https://"):
        print("错误: URL 须以 http:// 或 https:// 开头", file=sys.stderr)
        sys.exit(1)

    data = asyncio.run(detect(url))

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print_readable(data)


if __name__ == "__main__":
    main()
