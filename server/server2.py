from datetime import datetime

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("time-mcp")


@mcp.tool()
def get_time() -> str:
    """
    Get current date and time.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    mcp.run()
