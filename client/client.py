import asyncio
import json
import os
import re
from contextlib import AsyncExitStack
from pathlib import Path

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

from ollama import AsyncClient as OllamaClient

_server_dir = Path(__file__).resolve().parent.parent / "server"

# (script_name, label) — each gets StdioServerParameters
MCP_SERVERS = [
    ("server.py", "hello"),
    ("server2.py", "time"),
    ("weather.py", "weather"),
]

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")


def _single_tool_match(user_text: str) -> tuple[str | None, dict]:
    """
    Intent -> (tool_name, args). Returns (None, {}) if no unique match.
    """
    text = user_text.strip()
    if not text:
        return None, {}

    # get_weather: 天气 [省 市 区]，默认 陕西 西安 雁塔区
    if "天气" in text:
        province, city, county = "陕西", "西安", "雁塔区"
        # 简单解析：尝试 "X省Y市Z区" 或 "Y市" 等
        parts = re.split(r"[，,]\s*", text)
        for p in parts:
            p = p.strip()
            if p.endswith("省"):
                province = p.replace("省", "").strip()
            elif p.endswith("市"):
                city = p.replace("市", "").strip()
            elif p.endswith("区") or p.endswith("县"):
                county = p[:-1].strip()
        # 也支持 "西安天气" -> city=西安
        for suffix in ("天气", "的天气", "天气怎么样"):
            if suffix in text:
                t = text.replace(suffix, "").strip()
                if t and t != "天气":
                    if t in ("西安", "北京", "上海"):  # 仅市名
                        city = t
                    break
        return "get_weather", {"province": province, "city": city, "county": county}

    # get_time: 几点了 / 时间 / 现在几点
    if re.search(r"几点了|现在几点|当前时间|时间$|^时间\s*$", text):
        return "get_time", {}

    # say_hello: 跟 X 打招呼 / 向 X 问好 / 和 X 说你好
    m = re.search(r"(?:跟|和|向|给)(.+?)(?:打招呼|问好|说你好)", text)
    if m:
        name = m.group(1).strip()
        if name:
            return "say_hello", {"name": name}
    if re.match(r"^跟?.+打招呼$", text):
        name = text.replace("打招呼", "").replace("跟", "").strip()
        if name:
            return "say_hello", {"name": name}

    return None, {}


async def main():
    exit_stack = AsyncExitStack()
    sessions: list[ClientSession] = []
    tool_to_session: dict[str, ClientSession] = {}
    all_tools: list = []

    async with exit_stack:
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

        ollama_tools = [
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

        ollama = OllamaClient()
        messages = []

        print("Chat (exit/quit/q to leave):")

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

            # Single function hit: if exactly one tool matched, call it and skip Ollama
            tool_name, tool_args = _single_tool_match(user_text)
            if tool_name and tool_name in tool_to_session:
                session = tool_to_session[tool_name]
                try:
                    result = await session.call_tool(tool_name, tool_args)
                    result_text = result.content[0].text if result.content else ""
                    print(result_text)
                except Exception as e:
                    print(f"调用 {tool_name} 失败: {e}")
                continue

            # Ollama branch
            messages.append({"role": "user", "content": user_text})

            while True:
                try:
                    response = await ollama.chat(
                        model=OLLAMA_MODEL,
                        messages=messages,
                        tools=ollama_tools,
                    )
                except Exception as e:
                    print(
                        f"Ollama 调用失败（请确认 Ollama 已启动且已拉取模型，例如 ollama pull {OLLAMA_MODEL}）: {e}"
                    )
                    raise

                msg = response["message"]
                messages.append(msg)

                if "tool_calls" not in msg or not msg["tool_calls"]:
                    if msg.get("content"):
                        print("Assistant:", msg["content"])
                    break

                for call in msg["tool_calls"]:
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
