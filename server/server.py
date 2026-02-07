from mcp.server.fastmcp import FastMCP

# 创建 MCP Server
mcp = FastMCP("hello-mcp")

# 定义一个 Tool
@mcp.tool()
def say_hello(name: str) -> str:
    """
    Say hello to someone.
    """
    return f"Hello, {name}! 👋 This is MCP2 speaking."

# 启动 server（stdio 模式，最简单）
if __name__ == "__main__":
    mcp.run()

