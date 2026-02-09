import os
from datetime import datetime

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "time-mcp",
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8002")),
)


@mcp.tool()
def get_time() -> str:
    """
    Get current date and time.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    mcp.run(transport=os.environ.get("MCP_TRANSPORT", "stdio"))
