import asyncio
import json
import os
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

                calls = msg["tool_calls"]
                # Exactly one tool_call: execute and print result only, no second Ollama round
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

                # Multiple tool_calls: execute all, append results, continue to next Ollama round
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
