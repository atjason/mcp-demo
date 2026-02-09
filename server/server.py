import os
from mcp.server.fastmcp import FastMCP

# 创建 MCP Server（HTTP 时使用 MCP_PORT，默认 8001）
mcp = FastMCP(
    "hello-mcp",
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8001")),
)

# 定义一个 Tool
@mcp.tool()
def say_hello(name: str) -> str:
    """
    Say hello to someone.
    """
    return f"Hello, {name}! 👋 This is MCP2 speaking."

# 启动：MCP_TRANSPORT=stdio（默认）或 streamable-http；HTTP 时访问 http://host:port/mcp
if __name__ == "__main__":
    mcp.run(transport=os.environ.get("MCP_TRANSPORT", "stdio"))

