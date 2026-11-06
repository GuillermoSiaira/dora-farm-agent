"""Modal scheduled job for daily feeds and regional observatory refresh (SPEC-43).

Mounts durable Modal Volume 'dora-data' at /data, refreshes feeds & observatory,
copies allowed JSON files to the volume, and pushes to GitHub if configured.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import modal

logger = logging.getLogger("dora.modal_refresh")

image = modal.Image.debian_slim(python_version="3.12").apt_install("git")
if modal.is_local():
    ROOT = Path(__file__).resolve().parents[2]
    image = (
        image.pip_install_from_requirements(str(ROOT / "requirements.txt"))
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
                "records",
            ],
        )
    )

app = modal.App("dora-refresh", image=image)
data_volume = modal.Volume.from_name("dora-data", create_if_missing=True)


def _execute_refresh(push: bool = False, branch: str = "main") -> dict[str, Any]:
    if "/app" not in sys.path:
        sys.path.insert(0, "/app")

    token = os.environ.get("DORA_GITHUB_PUSH_TOKEN", "").strip()
    can_push = push and bool(token)

    if token:
        clone_url = f"https://x-access-token:{token}@github.com/GuillermoSiaira/dora-farm-agent.git"
    else:
        clone_url = "https://github.com/GuillermoSiaira/dora-farm-agent.git"

    work_dir = Path("/work")
    shutil.rmtree(work_dir, ignore_errors=True)

    # Attempt to shallow clone target branch; fallback to main if branch does not exist on remote yet
    res = subprocess.run(
        ["git", "clone", "--depth", "20", "--branch", branch, clone_url, str(work_dir)],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        subprocess.run(
            ["git", "clone", "--depth", "20", "--branch", "main", clone_url, str(work_dir)],
            check=True,
            capture_output=True,
            text=True,
        )
        if branch != "main":
            subprocess.run(
                ["git", "checkout", "-b", branch],
                cwd=str(work_dir),
                check=True,
                capture_output=True,
                text=True,
            )

    # Configure author
    subprocess.run(
        ["git", "config", "user.name", "dora-refresh-bot"],
        cwd=str(work_dir),
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "dora-refresh-bot@users.noreply.github.com"],
        cwd=str(work_dir),
        check=True,
    )

    from dora.refresh_job import run_refresh

    result = run_refresh(work_dir, Path("/data"), push=can_push, branch=branch)
    data_volume.commit()
    return result


@app.function(
    secrets=[modal.Secret.from_name("dora-github")],
    volumes={"/data": data_volume},
    timeout=1200,
)
def run_refresh_task(push: bool = False, branch: str = "main") -> dict[str, Any]:
    """Execute the refresh task inside a Modal container."""
    return _execute_refresh(push=push, branch=branch)


@app.function(
    schedule=modal.Cron("30 21 * * 1-5"),
    secrets=[modal.Secret.from_name("dora-github")],
    volumes={"/data": data_volume},
    timeout=1200,
)
def daily_refresh() -> dict[str, Any]:
    """Scheduled cron refresh running Monday to Friday at 21:30 UTC."""
    branch = os.environ.get("DORA_REFRESH_BRANCH", "main")
    token = os.environ.get("DORA_GITHUB_PUSH_TOKEN", "").strip()
    push = bool(token)
    return _execute_refresh(push=push, branch=branch)


@app.local_entrypoint()
def refresh_now(push: bool = False, branch: str = "refresh-smoke"):
    """Manual trigger entrypoint for testing and smoke runs."""
    print(f"Triggering refresh_now on Modal (push={push}, branch={branch})...")
    result = run_refresh_task.remote(push=push, branch=branch)
    print("Refresh completed:", result)
    return result
