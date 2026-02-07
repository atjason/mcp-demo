import asyncio
import json
import os
from pathlib import Path

from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

from ollama import AsyncClient as OllamaClient

# Path to server script (server/server.py next to client/)
_server_dir = Path(__file__).resolve().parent.parent / "server"
_server_script = _server_dir / "server.py"

# Model: use env or default to qwen2.5:3b
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")


async def main():
    # 1. MCP server params
    server_params = StdioServerParameters(
        command="python",
        args=[str(_server_script)],
        cwd=_server_dir,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            list_tools_result = await session.list_tools()
            tools = list_tools_result.tools
            print("MCP Tools:", [t.name for t in tools])

            ollama = OllamaClient()

            # MCP Tool -> Ollama tool schema
            ollama_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description or "",
                        "parameters": t.inputSchema or {},
                    },
                }
                for t in tools
            ]

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

                    for call in msg["tool_calls"]:
                        tool_name = call["function"]["name"]
                        raw_args = call["function"].get("arguments")
                        if isinstance(raw_args, str):
                            tool_args = json.loads(raw_args) if raw_args else {}
                        else:
                            tool_args = raw_args or {}

                        result = await session.call_tool(tool_name, tool_args)
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
