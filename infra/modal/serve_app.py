"""Public DORA web app on Modal (Hugging Face now charges for Gradio Spaces).

Runs `python app.py` exactly as locally and exposes port 7860. Scales to zero when idle.

    modal secret create dora-app DORA_API_BASE=... DORA_API_KEY=... DORA_MODEL=... DORA_TRANSCRIBE_MODEL=...
    modal deploy infra/modal/serve_app.py

`DORA_WARM=1 modal deploy infra/modal/serve_app.py` keeps one container always on (for the judging weeks); a plain `modal deploy` goes back to scaling to zero.
"""
import os
from pathlib import Path
import subprocess
import sys

import modal


def warm_containers() -> int:
    return int(os.environ.get("DORA_WARM", "0"))


WARM = warm_containers()

image = modal.Image.debian_slim(python_version="3.12")
if modal.is_local():  # inside the container this file sits at /root and the repo is already in /app
    ROOT = Path(__file__).resolve().parents[2]
    image = image.pip_install_from_requirements(str(ROOT / "requirements.txt")).add_local_dir(
        str(ROOT),
        "/app",
        ignore=[".git", ".venv", ".claude", "**/__pycache__", "eval/results", ".env"],
    )

app = modal.App("dora", image=image)
data_volume = modal.Volume.from_name("dora-data", create_if_missing=True)


# One container: Gradio keeps each session's queue in memory, so every request must reach the same server.
@app.function(
    secrets=[modal.Secret.from_name("dora-app")],
    volumes={"/data": data_volume},
    timeout=3600,
    scaledown_window=600,
    max_containers=1,
    min_containers=WARM,
)
@modal.concurrent(max_inputs=50)
@modal.web_server(port=7860, startup_timeout=180)
def web():
    # Reload volume and apply fresh data overlay before running app
    data_volume.reload()
    if "/app" not in sys.path:
        sys.path.insert(0, "/app")

    from dora.refresh_job import apply_data_overlay
    apply_data_overlay(Path("/data"), Path("/app"))

    subprocess.Popen(["python", "-u", "app.py"], cwd="/app")  # -u: the [chat] log lines reach `modal app logs` at once
