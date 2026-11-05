"""Public DORA MCP server on Modal (SPEC-40 section 6).

Serves /mcp and /health over HTTP with Bearer token authentication.

Setup:
    python -m mcp_server.auth new guillermo
    # Output: guillermo:<hash>
    modal secret create dora-mcp DORA_MCP_KEYS="guillermo:<hash>" DORA_MCP_SIGNING_KEY="<random-hex-32>"
    modal deploy infra/modal/serve_mcp.py
"""
import os
from pathlib import Path

import modal

image = modal.Image.debian_slim(python_version="3.12")
if modal.is_local():
    ROOT = Path(__file__).resolve().parents[2]
    image = (
        image.pip_install_from_requirements(str(ROOT / "requirements.txt"))
        .pip_install_from_requirements(str(ROOT / "requirements-chain.txt"))
        .add_local_dir(
            str(ROOT),
            "/app",
            ignore=[
                ".git",
                ".venv",
                ".claude",
                "**/__pycache__",
                "eval/results",
                ".env",
                "site",
                "observatory",
                "assets",
                "records",
            ],
        )
    )

app = modal.App("dora-mcp", image=image)
records_volume = modal.Volume.from_name("dora-records", create_if_missing=True)

function_secrets = [modal.Secret.from_name("dora-mcp")]
if os.environ.get("DORA_MODAL_INCLUDE_CHAIN_SECRET") == "1":
    function_secrets.append(modal.Secret.from_name("dora-chain"))


@app.function(
    volumes={"/records": records_volume},
    env={"DORA_RECORDS_DIR": "/records"},
    secrets=function_secrets,
    timeout=120,
    scaledown_window=300,
    max_containers=1,
)
@modal.asgi_app()
def mcp_app():
    import sys
    if "/app" not in sys.path:
        sys.path.insert(0, "/app")
    from mcp_server.server import create_http_app
    return create_http_app()
