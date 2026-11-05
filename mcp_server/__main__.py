"""Main entry point for running DORA MCP server (stdio or streamable-http)."""
from __future__ import annotations

import os
import sys

import uvicorn

from mcp_server.server import create_http_app, mcp


def main():
    transport = os.environ.get("MCP_TRANSPORT", "stdio").strip().lower()
    if transport == "streamable-http":
        port = int(os.environ.get("PORT", "8000"))
        host = os.environ.get("HOST", "0.0.0.0")
        app = create_http_app()
        uvicorn.run(app, host=host, port=port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
