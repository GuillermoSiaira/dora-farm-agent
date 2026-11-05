"""DORA MCP server package."""


def __getattr__(name: str):
    if name == "mcp":
        from mcp_server.server import mcp
        return mcp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["mcp"]
