"""
演示：使用在线 Qwen（OpenAI 兼容）API + 本地 MCP 服务。
配置从项目根目录的 config.json 读取（qwen.api_key、base_url、model）。
"""
import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client
from openai import AsyncOpenAI

_root = Path(__file__).resolve().parent.parent
_server_dir = _root / "server"
_config_path = _root / "config.json"

# 与 client.py 一致：本地 MCP 配置
MCP_SERVERS = [
    ("server.py", "hello"),
    ("server2.py", "time"),
    ("weather.py", "weather"),
    ("move.py", "move"),
]

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen-plus"


def load_qwen_config() -> dict:
    """从 config.json 读取 qwen 配置；缺失或 api_key 为空时退出。"""
    if not _config_path.exists():
        print(f"错误：未找到配置文件 {_config_path}，请复制 config.json.example 为 config.json 并填写 qwen.api_key。")
        sys.exit(1)
    try:
        with open(_config_path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"错误：config.json 格式无效: {e}")
        sys.exit(1)
    qwen = data.get("qwen")
    if not isinstance(qwen, dict):
        print("错误：config.json 中缺少 'qwen' 对象。")
        sys.exit(1)
    api_key = (qwen.get("api_key") or "").strip()
    if not api_key or api_key == "your-api-key":
        print("错误：请在 config.json 的 qwen 中设置有效的 api_key。")
        sys.exit(1)
    return {
        "api_key": api_key,
        "base_url": (qwen.get("base_url") or DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL,
        "model": (qwen.get("model") or DEFAULT_MODEL).strip() or DEFAULT_MODEL,
    }


async def main():
    cfg = load_qwen_config()
    client = AsyncOpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
    model = cfg["model"]

    mcp_server_urls = os.environ.get("MCP_SERVER_URLS", "").strip()
    if mcp_server_urls:
        mcp_server_urls = [u.strip() for u in mcp_server_urls.split(",") if u.strip()]
    else:
        mcp_server_urls = []

    exit_stack = AsyncExitStack()
    sessions: list[ClientSession] = []
    tool_to_session: dict[str, ClientSession] = {}
    all_tools: list = []

    async with exit_stack:
        if mcp_server_urls:
            for url in mcp_server_urls:
                try:
                    (read, write, _) = await exit_stack.enter_async_context(
                        streamable_http_client(url)
                    )
                    session = ClientSession(read, write)
                    await exit_stack.enter_async_context(session)
                    await session.initialize()
                    sessions.append(session)
                    list_result = await session.list_tools()
                    for t in list_result.tools:
                        all_tools.append(t)
                        tool_to_session[t.name] = session
                except Exception as e:
                    print(f"连接 {url} 失败: {e}")
        else:
            for script_name, _label in MCP_SERVERS:
                script_path = _server_dir / script_name
                if not script_path.exists():
                    continue
                params = StdioServerParameters(
                    command="python",
                    args=[str(script_path)],
                    cwd=_server_dir,
                )
                read, write = await exit_stack.enter_async_context(stdio_client(params))
                session = ClientSession(read, write)
                await exit_stack.enter_async_context(session)
                await session.initialize()
                sessions.append(session)
                list_result = await session.list_tools()
                for t in list_result.tools:
                    all_tools.append(t)
                    tool_to_session[t.name] = session

        if not all_tools:
            print("未加载到任何 MCP 工具，退出。")
            return

        tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": t.inputSchema or {},
                },
            }
            for t in all_tools
        ]
        print("MCP Tools:", [t.name for t in all_tools])
        print("Chat (exit/quit/q to leave):")

        messages: list[dict] = []

        while True:
            try:
                user_text = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                break
            if not user_text:
                continue
            if user_text.lower() in ("exit", "quit", "q"):
                print("Bye.")
                break

            messages.append({"role": "user", "content": user_text})

            while True:
                try:
                    response = await client.chat.completions.create(
                        model=model,
                        messages=messages,
                        tools=tools,
                    )
                except Exception as e:
                    print(f"Qwen API 调用失败: {e}")
                    raise

                choice = response.choices[0] if response.choices else None
                if not choice:
                    print("Qwen API 返回无 choices，退出。")
                    return
                message = choice.message

                # 归一化为与 client.py 一致的 msg 结构
                tool_calls_list = []
                if getattr(message, "tool_calls", None):
                    for tc in message.tool_calls:
                        if getattr(tc, "function", None):
                            tool_calls_list.append({
                                "id": getattr(tc, "id", None),
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments or "",
                                },
                            })
                msg = {
                    "role": "assistant",
                    "content": message.content if getattr(message, "content", None) else None,
                    "tool_calls": tool_calls_list if tool_calls_list else None,
                }
                messages.append(msg)

                if not msg.get("tool_calls"):
                    if msg.get("content"):
                        print("Assistant:", msg["content"])
                    break

                calls = msg["tool_calls"]
                if len(calls) == 1:
                    call = calls[0]
                    tname = call["function"]["name"]
                    raw_args = call["function"].get("arguments")
                    if isinstance(raw_args, str):
                        tool_args = json.loads(raw_args) if raw_args else {}
                    else:
                        tool_args = raw_args or {}
                    session = tool_to_session.get(tname)
                    if not session:
                        print(f"未知工具: {tname}")
                    else:
                        result = await session.call_tool(tname, tool_args)
                        result_text = result.content[0].text if result.content else ""
                        print(result_text)
                    break

                for call in calls:
                    tname = call["function"]["name"]
                    raw_args = call["function"].get("arguments")
                    if isinstance(raw_args, str):
                        tool_args = json.loads(raw_args) if raw_args else {}
                    else:
                        tool_args = raw_args or {}
                    session = tool_to_session.get(tname)
                    if not session:
                        result_text = f"未知工具: {tname}"
                    else:
                        result = await session.call_tool(tname, tool_args)
                        result_text = result.content[0].text if result.content else ""
                    tool_id = call.get("id")
                    if tool_id:
                        messages.append(
                            {"role": "tool", "content": result_text, "tool_call_id": tool_id}
                        )
                    else:
                        messages.append({"role": "tool", "content": result_text})


if __name__ == "__main__":
    asyncio.run(main())
