"""fastmcp entrypoint"""

from fastmcp import FastMCP


def create_server():
    return FastMCP("giga-mcp")


app = create_server()
