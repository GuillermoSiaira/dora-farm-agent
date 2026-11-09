"""Daily data refresh job for feeds, observatory, Volume sync and git push (SPEC-43).

Runs on Modal (or locally for tests), independent of GitHub Actions.
Strictly copies only allowed data files and redacts all secrets.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

logger = logging.getLogger("dora.refresh_job")

ALLOWED_PARTS = [
    ("dora", "data", "price_curves"),
    ("dora", "data"),
    ("observatory",),
]


def redact(text: str, token: str | None = None) -> str:
    """Replace personal access tokens and auth URLs with *** in any output or log."""
    if not text:
        return ""
    # Redact x-access-token embedded in URLs
    res = re.sub(r"x-access-token:[^@\s\"']+@", "x-access-token:***@", text)
    # Redact any other basic auth user:pass or token@ in URLs
    res = re.sub(r"https://(?!x-access-token:)[^@\s\"']+@github\.com", "https://***@github.com", res)
    # Redact explicit token if provided
    if token and len(token) > 3:
        res = res.replace(token, "***")
    # Redact env token if configured
    env_token = os.environ.get("DORA_GITHUB_PUSH_TOKEN")
    if env_token and len(env_token) > 3:
        res = res.replace(env_token, "***")
    return res


def is_allowed_file(rel_path: str | Path) -> bool:
    """Check if relative path belongs to the strictly allowed set:
    - dora/data/price_curves/*_latest.json
    - dora/data/basis_*.json
    - observatory/*.json
    """
    p = Path(rel_path)
    parts = p.parts
    if len(parts) == 4 and parts[0] == "dora" and parts[1] == "data" and parts[2] == "price_curves":
        return parts[3].endswith("_latest.json")
    if len(parts) == 3 and parts[0] == "dora" and parts[1] == "data":
        return parts[2].startswith("basis_") and parts[2].endswith(".json")
    if len(parts) == 2 and parts[0] == "observatory":
        return parts[1].endswith(".json")
    return False


def apply_data_overlay(data_dir: Path | str, app_dir: Path | str) -> list[str]:
    """Overlay fresh data files from data_dir (Modal volume) onto app_dir.
    Only copies valid JSON files that match the allowed set.
    Clears engine fingerprint cache so signatures reflect current data.
    """
    data_path = Path(data_dir)
    app_path = Path(app_dir)
    if not data_path.exists() or not data_path.is_dir():
        return []

    overlaid: list[str] = []
    for root, _, files in os.walk(data_path):
        for f in files:
            full_p = Path(root) / f
            try:
                rel = full_p.relative_to(data_path)
            except ValueError:
                continue

            rel_str = rel.as_posix()
            if not is_allowed_file(rel):
                continue

            try:
                raw = full_p.read_text(encoding="utf-8")
                json.loads(raw)
            except Exception:
                continue

            dest = app_path / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(full_p, dest)
            overlaid.append(rel_str)

    try:
        from dora.version import _FINGERPRINT_CACHE
        _FINGERPRINT_CACHE.clear()
    except Exception:
        pass

    return overlaid


def _run_git(args: list[str], cwd: Path, token: str | None = None) -> tuple[int, str, str]:
    """Run a git command in cwd, returning (code, stdout, stderr) with secrets redacted."""
    try:
        proc = subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
        return (proc.returncode, redact(proc.stdout, token), redact(proc.stderr, token))
    except Exception as e:
        return (-1, "", redact(str(e), token))


def run_refresh(
    repo_dir: Path | str,
    data_out: Path | str,
    *,
    push: bool = False,
    branch: str = "main",
    today: date | None = None,
) -> dict[str, Any]:
    """Execute daily refresh job:
    1. Refresh feeds
    2. Refresh observatory (no paid model call)
    3. Copy allowed valid JSON files to data_out
    4. If push, commit and push to git branch with rebase retry
    5. Write last_refresh.json
    """
    repo_path = Path(repo_dir).resolve()
    data_path = Path(data_out).resolve()
    data_path.mkdir(parents=True, exist_ok=True)

    today_date = today if today is not None else datetime.now(timezone.utc).date()
    date_str = today_date.isoformat()

    status = "ok"

    env_sub = os.environ.copy()
    existing_pythonpath = env_sub.get("PYTHONPATH", "")
    env_sub["PYTHONPATH"] = (
        f"{repo_path}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(repo_path)
    )

    # 1. Feeds refresh (run as subprocess in clone)
    feeds_failed_sources = []
    try:
        feeds_cmd = [
            sys.executable,
            "-c",
            "import json; from dora.feeds import refresh; res = refresh(max_age_hours=0); print('__DORA_FEEDS__:' + json.dumps(res))",
        ]
        proc_feeds = subprocess.run(
            feeds_cmd,
            cwd=str(repo_path),
            env=env_sub,
            capture_output=True,
            text=True,
        )
        if proc_feeds.returncode != 0:
            logger.warning("Feeds subprocess failed (code %d): %s", proc_feeds.returncode, redact(proc_feeds.stderr))
            status = "feeds_failed"
        else:
            feeds_res = None
            for line in proc_feeds.stdout.splitlines():
                if "__DORA_FEEDS__:" in line:
                    try:
                        feeds_res = json.loads(line.split("__DORA_FEEDS__:", 1)[1].strip())
                        break
                    except Exception:
                        pass
                elif line.strip().startswith("{") and line.strip().endswith("}"):
                    try:
                        feeds_res = json.loads(line.strip())
                    except Exception:
                        pass

            if not feeds_res:
                logger.warning("Could not parse feeds JSON from output: %s", redact(proc_feeds.stdout))
                status = "feeds_failed"
            else:
                sources = feeds_res.get("sources") or {}
                for src_name in ("cbot", "magyp", "bcra"):
                    src_info = sources.get(src_name) or feeds_res.get(src_name)
                    if isinstance(src_info, dict):
                        src_status = src_info.get("status")
                    elif isinstance(src_info, str):
                        src_status = src_info
                    else:
                        src_status = None

                    if src_status not in ("updated", "fresh"):
                        feeds_failed_sources.append(src_name)

                if feeds_failed_sources:
                    logger.warning("Feeds sources not updated/fresh: %s", feeds_failed_sources)
                    status = f"feeds_failed: {', '.join(feeds_failed_sources)}"
    except Exception as e:
        logger.warning("Feeds refresh encountered an issue: %s", redact(str(e)))
        status = "feeds_failed"

    # 2. Regional observatory (run without DORA_API_KEY in the environment)
    env_obs = env_sub.copy()
    env_obs.pop("DORA_API_KEY", None)
    try:
        obs_cmd = [
            sys.executable,
            "-c",
            "import dora.observatory as obs; obs.run_observatory()",
        ]
        proc_obs = subprocess.run(
            obs_cmd,
            cwd=str(repo_path),
            env=env_obs,
            capture_output=True,
            text=True,
        )
        if proc_obs.returncode != 0:
            logger.warning("Observatory subprocess failed (code %d): %s", proc_obs.returncode, redact(proc_obs.stderr))
            if status == "ok":
                status = "observatory_failed"
    except Exception as e:
        logger.warning("Observatory run encountered an issue: %s", redact(str(e)))
        if status == "ok":
            status = "observatory_failed"

    # 3. Copy allowed files into data_out
    copied_files: list[str] = []
    for root, _, files in os.walk(repo_path):
        for f in files:
            full_p = Path(root) / f
            try:
                rel = full_p.relative_to(repo_path)
            except ValueError:
                continue

            if not is_allowed_file(rel):
                continue

            # Verify it parses as valid JSON
            try:
                raw = full_p.read_text(encoding="utf-8")
                json.loads(raw)
            except Exception:
                continue

            dest = data_path / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(full_p, dest)
            copied_files.append(rel.as_posix())

    # 4. Check changes in git
    changed: list[str] = []
    commit_sha: str | None = None

    is_git_repo = (repo_path / ".git").exists()
    token = os.environ.get("DORA_GITHUB_PUSH_TOKEN")

    if is_git_repo:
        # Identify allowed files that were modified or untracked
        code, out, _ = _run_git(["status", "--porcelain"], cwd=repo_path, token=token)
        all_dirty = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            # status line format: XY path or XY "path" -> get path
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                p_str = parts[1].strip('"').replace("\\", "/")
                all_dirty.append(p_str)

        allowed_dirty = [p for p in all_dirty if is_allowed_file(p)]

        if not allowed_dirty:
            if status == "ok":
                status = "no_changes"
        else:
            changed = sorted(allowed_dirty)
            if push:
                # Stage only allowed dirty files
                for f_rel in changed:
                    _run_git(["add", f_rel], cwd=repo_path, token=token)

                # Check if there are cached changes
                c_code, c_out, _ = _run_git(["diff", "--cached", "--name-only"], cwd=repo_path, token=token)
                cached = [l.strip().replace("\\", "/") for l in c_out.splitlines() if l.strip()]
                cached_allowed = [p for p in cached if is_allowed_file(p)]

                if not cached_allowed:
                    if status == "ok":
                        status = "no_changes"
                else:
                    changed = sorted(cached_allowed)
                    commit_msg = f"Daily refresh {date_str}"
                    commit_code, commit_out, commit_err = _run_git(
                        [
                            "-c", "user.name=dora-refresh-bot",
                            "-c", "user.email=dora-refresh-bot@users.noreply.github.com",
                            "commit", "-m", commit_msg,
                        ],
                        cwd=repo_path,
                        token=token,
                    )

                    if commit_code == 0:
                        _, sha_out, _ = _run_git(["rev-parse", "HEAD"], cwd=repo_path, token=token)
                        commit_sha = sha_out.strip()

                        # Push to branch
                        p_code, p_out, p_err = _run_git(["push", "origin", branch], cwd=repo_path, token=token)
                        if p_code != 0:
                            logger.info("Direct push rejected, attempting git pull --rebase: %s", redact(p_err, token))
                            r_code, r_out, r_err = _run_git(["pull", "--rebase", "origin", branch], cwd=repo_path, token=token)
                            if r_code != 0:
                                # Rebase conflict
                                _run_git(["rebase", "--abort"], cwd=repo_path, token=token)
                                status = "push_conflict"
                                commit_sha = None
                            else:
                                # Rebase succeeded, push again
                                p2_code, p2_out, p2_err = _run_git(["push", "origin", branch], cwd=repo_path, token=token)
                                if p2_code == 0:
                                    _, sha2_out, _ = _run_git(["rev-parse", "HEAD"], cwd=repo_path, token=token)
                                    commit_sha = sha2_out.strip()
                                else:
                                    logger.error("Push failed after rebase: %s", redact(p2_err, token))
                                    status = "push_failed"
                    else:
                        logger.error("Commit failed: %s", redact(commit_err, token))
                        status = "push_failed"

    result = {
        "date": date_str,
        "status": status,
        "changed": changed,
        "commit": commit_sha,
    }

    # Write last_refresh.json
    try:
        last_refresh_file = data_path / "last_refresh.json"
        last_refresh_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning("Could not write last_refresh.json: %s", redact(str(e), token))

    return result

def set_secret(env_path: Path | str | None = None) -> int:
    """Read DORA_GITHUB_PUSH_TOKEN from .env and create Modal secret dora-github without echoing token."""
    if env_path is None:
        candidates = [Path(".env"), Path(__file__).resolve().parents[1] / ".env"]
        for c in candidates:
            if c.is_file():
                env_path = c
                break
    else:
        env_path = Path(env_path)

    token = None
    if env_path and env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DORA_GITHUB_PUSH_TOKEN="):
                val = line.split("=", 1)[1].strip()
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                token = val.strip()
                break

    if not token:
        token = os.environ.get("DORA_GITHUB_PUSH_TOKEN", "").strip()

    if not token:
        print("Error: DORA_GITHUB_PUSH_TOKEN not found in .env or environment.")
        return 1

    if not token.startswith("github_pat_"):
        print("Warning: Fine-grained GitHub tokens typically start with 'github_pat_'.")

    cmd = ["modal", "secret", "create", "dora-github", f"DORA_GITHUB_PUSH_TOKEN={token}", "--force"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print("Modal secret 'dora-github' successfully created from .env (token not echoed).")
        return 0
    else:
        redacted_err = redact(res.stderr, token)
        print(f"Failed to create Modal secret: {redacted_err}")
        return res.returncode


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "set-secret":
        sys.exit(set_secret())
    else:
        print("Usage: python -m dora.refresh_job set-secret")
        sys.exit(1)
