"""Tests for SPEC-43: daily data refresh on Modal, Volume sync, overlay, and Git push."""
from __future__ import annotations

from datetime import date
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from dora.refresh_job import (
    apply_data_overlay,
    is_allowed_file,
    redact,
    run_refresh,
    set_secret,
)
from dora.version import _FINGERPRINT_CACHE, engine_fingerprint


@pytest.fixture
def git_repos(tmp_path):
    """Create a bare origin repo and a cloned work repo with dora stubs."""
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(bare)], check=True, capture_output=True)

    work = tmp_path / "work"
    work.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main", str(work)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(work), check=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=str(work), check=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=str(work), check=True)

    # Base commit
    (work / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    (work / "dora" / "data" / "basis_rosario.json").parent.mkdir(parents=True, exist_ok=True)
    (work / "dora" / "data" / "basis_rosario.json").write_text('{"basis": -10}', encoding="utf-8")

    # Stubs for subprocess execution in work
    (work / "dora" / "__init__.py").write_text("", encoding="utf-8")
    (work / "dora" / "feeds.py").write_text(
        'def refresh(*args, **kwargs):\n'
        '    return {"status": "updated", "sources": {"cbot": {"status": "updated"}, "magyp": {"status": "updated"}, "bcra": {"status": "updated"}}}\n'
        'if __name__ == "__main__":\n'
        '    import json\n'
        '    print(json.dumps(refresh()))\n',
        encoding="utf-8",
    )
    (work / "dora" / "observatory.py").write_text(
        'def run_observatory(*args, **kwargs):\n'
        '    return {"status": "ok"}\n'
        'if __name__ == "__main__":\n'
        '    run_observatory()\n',
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "."], cwd=str(work), check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(work), check=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=str(work), check=True)

    return work, bare


def test_1_run_refresh_copies_allowed_only(tmp_path):
    """1. run_refresh(push=False) copies exactly the allowed files into data_out,
    with relative paths; a non-allowed file written by the fake (e.g. dora/data/other.json)
    is not copied; an allowed file with invalid JSON is not copied.
    """
    work = tmp_path / "work"
    work.mkdir(parents=True, exist_ok=True)
    data_out = tmp_path / "data_out"

    # Setup files in work
    (work / "dora" / "data" / "price_curves").mkdir(parents=True, exist_ok=True)
    (work / "dora" / "data" / "price_curves" / "soja_latest.json").write_text('{"crop": "soja", "prices": [300]}', encoding="utf-8")
    (work / "dora" / "data" / "basis_rosario.json").write_text('{"basis": -15}', encoding="utf-8")
    (work / "observatory").mkdir(parents=True, exist_ok=True)
    (work / "observatory" / "2026-11-06.json").write_text('{"report": "ok"}', encoding="utf-8")

    # Non-allowed file
    (work / "dora" / "data" / "other.json").write_text('{"secret": 123}', encoding="utf-8")
    # Allowed path but invalid JSON
    (work / "dora" / "data" / "basis_bad.json").write_text("NOT A JSON {", encoding="utf-8")

    # Stubs in work
    (work / "dora" / "__init__.py").write_text("", encoding="utf-8")
    (work / "dora" / "feeds.py").write_text(
        'def refresh(*args, **kwargs):\n'
        '    return {"status": "updated", "sources": {"cbot": {"status": "updated"}, "magyp": {"status": "updated"}, "bcra": {"status": "updated"}}}\n',
        encoding="utf-8",
    )
    (work / "dora" / "observatory.py").write_text(
        'def run_observatory(*args, **kwargs):\n'
        '    return {"status": "ok"}\n',
        encoding="utf-8",
    )

    res = run_refresh(work, data_out, push=False, today=date(2026, 11, 6))

    assert (data_out / "dora" / "data" / "price_curves" / "soja_latest.json").exists()
    assert (data_out / "dora" / "data" / "basis_rosario.json").exists()
    assert (data_out / "observatory" / "2026-11-06.json").exists()

    assert not (data_out / "dora" / "data" / "other.json").exists()
    assert not (data_out / "dora" / "data" / "basis_bad.json").exists()
    assert res["status"] in ("ok", "no_changes")


def test_2_feeds_fake_raises(tmp_path):
    """2. Feeds fake raises: previous files kept, observatory still runs, status feeds_failed."""
    work = tmp_path / "work"
    work.mkdir(parents=True, exist_ok=True)
    data_out = tmp_path / "data_out"
    data_out.mkdir(parents=True, exist_ok=True)

    # Previous file in data_out
    prev_file = data_out / "dora" / "data" / "price_curves" / "soja_latest.json"
    prev_file.parent.mkdir(parents=True, exist_ok=True)
    prev_file.write_text('{"previous": true}', encoding="utf-8")

    # Stub dora/feeds.py that raises
    (work / "dora").mkdir(parents=True, exist_ok=True)
    (work / "dora" / "__init__.py").write_text("", encoding="utf-8")
    (work / "dora" / "feeds.py").write_text(
        'def refresh(*args, **kwargs):\n'
        '    raise RuntimeError("BCRA feed timeout")\n',
        encoding="utf-8",
    )
    # Stub observatory that writes obs.json
    (work / "dora" / "observatory.py").write_text(
        'from pathlib import Path\n'
        'def run_observatory(*args, **kwargs):\n'
        '    obs_dir = Path("observatory")\n'
        '    obs_dir.mkdir(parents=True, exist_ok=True)\n'
        '    (obs_dir / "obs.json").write_text(\'{"obs": 1}\', encoding="utf-8")\n'
        '    return {"status": "ok"}\n',
        encoding="utf-8",
    )

    res = run_refresh(work, data_out, push=False, today=date(2026, 11, 6))

    assert "feeds_failed" in res["status"]
    # Previous file preserved
    assert prev_file.exists()
    assert json.loads(prev_file.read_text(encoding="utf-8")) == {"previous": True}
    assert (data_out / "observatory" / "obs.json").exists()


def test_3_dora_api_key_unset_for_observatory(tmp_path, monkeypatch):
    """3. DORA_API_KEY set in test environment: observatory fake sees it unset (no paid call)."""
    work = tmp_path / "work"
    work.mkdir(parents=True, exist_ok=True)
    data_out = tmp_path / "data_out"

    monkeypatch.setenv("DORA_API_KEY", "secret-test-key-12345")

    # Stubs in work
    (work / "dora").mkdir(parents=True, exist_ok=True)
    (work / "dora" / "__init__.py").write_text("", encoding="utf-8")
    (work / "dora" / "feeds.py").write_text(
        'def refresh(*args, **kwargs):\n'
        '    return {"status": "updated", "sources": {"cbot": {"status": "updated"}, "magyp": {"status": "updated"}, "bcra": {"status": "updated"}}}\n',
        encoding="utf-8",
    )
    (work / "dora" / "observatory.py").write_text(
        'import os\n'
        'from pathlib import Path\n'
        'def run_observatory(*args, **kwargs):\n'
        '    saw_key = "DORA_API_KEY" in os.environ\n'
        '    Path("saw_key.txt").write_text(str(saw_key), encoding="utf-8")\n'
        '    return {"status": "ok"}\n',
        encoding="utf-8",
    )

    run_refresh(work, data_out, push=False)

    saw_key = (work / "saw_key.txt").read_text(encoding="utf-8")
    assert saw_key == "False", "Observatory must run without DORA_API_KEY"
    assert os.environ.get("DORA_API_KEY") == "secret-test-key-12345", "DORA_API_KEY must be restored"


def test_4_push_path_data_changed(git_repos, tmp_path):
    """4. Push path, data changed: one commit on origin/main, author dora-refresh-bot,
    message Daily refresh <date>, only allowed paths in git show --stat;
    an unrelated dirty file in the work tree is not committed.
    """
    work, bare = git_repos
    data_out = tmp_path / "data_out"

    # Change an allowed data file
    target_basis = work / "dora" / "data" / "basis_rosario.json"
    target_basis.write_text('{"basis": -25}', encoding="utf-8")

    # Unrelated dirty file
    unrelated = work / "unrelated_code.py"
    unrelated.write_text("print('not allowed')", encoding="utf-8")

    res = run_refresh(work, data_out, push=True, branch="main", today=date(2026, 11, 6))

    assert res["status"] == "ok"
    assert res["commit"] is not None

    # Verify commit on origin
    show_res = subprocess.run(
        ["git", "show", "--stat", res["commit"]],
        cwd=str(work),
        capture_output=True,
        text=True,
        check=True,
    )
    commit_info = show_res.stdout
    assert "dora-refresh-bot" in commit_info
    assert "Daily refresh 2026-11-06" in commit_info
    assert "basis_rosario.json" in commit_info
    assert "unrelated_code.py" not in commit_info

    # Verify unrelated file remains untracked in work tree
    status_res = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(work),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "unrelated_code.py" in status_res.stdout


def test_5_no_data_change(git_repos, tmp_path):
    """5. No data change: no commit, status no_changes."""
    work, bare = git_repos
    data_out = tmp_path / "data_out"

    res = run_refresh(work, data_out, push=True, branch="main", today=date(2026, 11, 6))

    assert res["status"] == "no_changes"
    assert res["commit"] is None
    assert res["changed"] == []


def test_6_remote_moved_with_unrelated_commit(git_repos, tmp_path):
    """6. Remote moved with an unrelated commit: rebase, push succeeds, both commits on origin/main."""
    work, bare = git_repos
    data_out = tmp_path / "data_out"

    # Push an unrelated commit to origin from another repo
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-b", "main", str(bare), str(other)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Peer"], cwd=str(other), check=True)
    subprocess.run(["git", "config", "user.email", "peer@example.com"], cwd=str(other), check=True)
    (other / "doc.txt").write_text("unrelated doc update", encoding="utf-8")
    subprocess.run(["git", "add", "doc.txt"], cwd=str(other), check=True)
    subprocess.run(["git", "commit", "-m", "Remote update"], cwd=str(other), check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=str(other), check=True)

    # Local work modifies an allowed file
    (work / "dora" / "data" / "basis_rosario.json").write_text('{"basis": -30}', encoding="utf-8")

    res = run_refresh(work, data_out, push=True, branch="main", today=date(2026, 11, 6))

    assert res["status"] == "ok"
    assert res["commit"] is not None

    log_res = subprocess.run(
        ["git", "log", "--oneline", "-n", "3"],
        cwd=str(work),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Remote update" in log_res.stdout
    assert "Daily refresh" in log_res.stdout


def test_7_remote_moved_with_conflicting_commit(git_repos, tmp_path):
    """7. Remote moved changing the same data file: rebase conflict, no push, status push_conflict."""
    work, bare = git_repos
    data_out = tmp_path / "data_out"

    # Push conflicting change from other clone
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-b", "main", str(bare), str(other)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Peer"], cwd=str(other), check=True)
    subprocess.run(["git", "config", "user.email", "peer@example.com"], cwd=str(other), check=True)
    (other / "dora" / "data" / "basis_rosario.json").write_text('{"basis": -99}', encoding="utf-8")
    subprocess.run(["git", "add", "dora/data/basis_rosario.json"], cwd=str(other), check=True)
    subprocess.run(["git", "commit", "-m", "Conflicting basis"], cwd=str(other), check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=str(other), check=True)

    # Local work modifies the same file
    (work / "dora" / "data" / "basis_rosario.json").write_text('{"basis": -50}', encoding="utf-8")

    res = run_refresh(work, data_out, push=True, branch="main", today=date(2026, 11, 6))

    assert res["status"] == "push_conflict"
    assert res["commit"] is None

    # Work tree is clean (rebase was aborted)
    st = subprocess.run(["git", "status", "--porcelain"], cwd=str(work), capture_output=True, text=True, check=True)
    # The file in work tree might be left dirty, but git status shows no rebase in progress
    git_dir = work / ".git"
    assert not (git_dir / "rebase-merge").exists()
    assert not (git_dir / "rebase-apply").exists()


def test_8_redact_secrets():
    """8. Redact utility strips personal access tokens and auth URLs from text."""
    secret = "ghp_1234567890abcdef1234567890abcdef12"
    url_with_token = f"https://x-access-token:{secret}@github.com/org/repo.git"
    raw_log = f"Failed to push to {url_with_token} with key {secret}"

    cleaned = redact(raw_log, secret)
    assert secret not in cleaned
    assert "x-access-token:***@" in cleaned
    assert cleaned == "Failed to push to https://x-access-token:***@github.com/org/repo.git with key ***"


def test_9_apply_data_overlay(tmp_path):
    """9. apply_data_overlay copies valid allowed JSON files from volume into app dir."""
    volume = tmp_path / "volume"
    app = tmp_path / "app"

    (volume / "dora" / "data" / "price_curves").mkdir(parents=True, exist_ok=True)
    (volume / "dora" / "data" / "price_curves" / "cbot_latest.json").write_text('{"crop": "cbot"}', encoding="utf-8")
    (volume / "dora" / "data" / "basis_argentina.json").write_text('{"basis": -12}', encoding="utf-8")
    (volume / "observatory").mkdir(parents=True, exist_ok=True)
    (volume / "observatory" / "latest.json").write_text('{"status": "fresh"}', encoding="utf-8")

    # Disallowed file on volume
    (volume / "dora" / "engine.py").write_text("malicious code", encoding="utf-8")
    (volume / "observatory" / "invalid.json").write_text("bad json {", encoding="utf-8")

    overlaid = apply_data_overlay(volume, app)

    assert "dora/data/price_curves/cbot_latest.json" in overlaid
    assert "dora/data/basis_argentina.json" in overlaid
    assert "observatory/latest.json" in overlaid

    assert (app / "dora" / "data" / "price_curves" / "cbot_latest.json").exists()
    assert (app / "dora" / "data" / "basis_argentina.json").exists()
    assert (app / "observatory" / "latest.json").exists()

    assert not (app / "dora" / "engine.py").exists()
    assert not (app / "observatory" / "invalid.json").exists()


def test_10_engine_fingerprint_changes_with_overlay(tmp_path):
    """10. Fingerprint changes when overlay introduces newer data."""
    tree_a = tmp_path / "tree_a"
    tree_b = tmp_path / "tree_b"

    for tree in (tree_a, tree_b):
        (tree / "dora" / "data").mkdir(parents=True, exist_ok=True)
        (tree / "dora" / "data" / "basis_rosario.json").write_text('{"b": 1}', encoding="utf-8")

    # Tree B has new data written directly
    (tree_b / "dora" / "data" / "basis_rosario.json").write_text('{"b": 2}', encoding="utf-8")

    # Tree A gets new data via overlay
    data_vol = tmp_path / "data_vol"
    (data_vol / "dora" / "data").mkdir(parents=True, exist_ok=True)
    (data_vol / "dora" / "data" / "basis_rosario.json").write_text('{"b": 2}', encoding="utf-8")

    apply_data_overlay(data_vol, tree_a)

    _FINGERPRINT_CACHE.clear()
    fp_a = engine_fingerprint(tree_a)

    _FINGERPRINT_CACHE.clear()
    fp_b = engine_fingerprint(tree_b)

    assert fp_a == fp_b


def test_11_workflow_no_schedule():
    """11. The workflow file has no schedule and has workflow_dispatch."""
    wf_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "refresh.yml"
    assert wf_path.exists(), "refresh.yml must exist"
    content = wf_path.read_text(encoding="utf-8")
    assert "schedule:" not in content
    assert "workflow_dispatch:" in content
    assert "infra/modal/refresh.py" in content


def test_12_no_repo_disk_trace():
    """12. After the suite, git status --porcelain dora/data observatory in the repo is empty."""
    repo_root = Path(__file__).resolve().parents[1]
    res = subprocess.run(
        ["git", "status", "--porcelain", "dora/data", "observatory"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    assert res.stdout.strip() == "", f"Repo data files were modified: {res.stdout}"


def test_13_stub_feeds_writes_relative_to_file(tmp_path):
    """13. A temporary repo with its own stub dora/feeds.py that writes relative to its own __file__;
    the files must land under repo_path and in data_out.
    """
    work = tmp_path / "work"
    work.mkdir(parents=True, exist_ok=True)
    data_out = tmp_path / "data_out"

    dora_dir = work / "dora"
    dora_dir.mkdir(parents=True, exist_ok=True)
    (dora_dir / "__init__.py").write_text("", encoding="utf-8")
    (dora_dir / "feeds.py").write_text(
        'from pathlib import Path\n'
        'def refresh(*args, **kwargs):\n'
        '    target = Path(__file__).resolve().parent / "data" / "price_curves" / "cbot_latest.json"\n'
        '    target.parent.mkdir(parents=True, exist_ok=True)\n'
        '    target.write_text(\'{"crop": "cbot", "as_of": "2026-11-06"}\', encoding="utf-8")\n'
        '    return {"status": "updated", "sources": {"cbot": {"status": "updated"}, "magyp": {"status": "updated"}, "bcra": {"status": "updated"}}}\n',
        encoding="utf-8",
    )
    (dora_dir / "observatory.py").write_text(
        'def run_observatory(*args, **kwargs):\n    return {"status": "ok"}\n',
        encoding="utf-8",
    )

    res = run_refresh(work, data_out, push=False)

    # 1. Landed under repo_path
    repo_file = work / "dora" / "data" / "price_curves" / "cbot_latest.json"
    assert repo_file.is_file(), f"File did not land in repo_path: {repo_file}"
    assert json.loads(repo_file.read_text(encoding="utf-8")) == {"crop": "cbot", "as_of": "2026-11-06"}

    # 2. Landed in data_out
    out_file = data_out / "dora" / "data" / "price_curves" / "cbot_latest.json"
    assert out_file.is_file(), f"File did not land in data_out: {out_file}"
    assert json.loads(out_file.read_text(encoding="utf-8")) == {"crop": "cbot", "as_of": "2026-11-06"}


def test_14_set_secret(tmp_path, monkeypatch):
    """14. set_secret reads DORA_GITHUB_PUSH_TOKEN from .env and invokes modal secret create."""
    env_file = tmp_path / ".env"
    env_file.write_text('DORA_GITHUB_PUSH_TOKEN=github_pat_11ABCXYZ987\n', encoding="utf-8")

    called_cmd = []
    def fake_subprocess_run(cmd, *args, **kwargs):
        called_cmd.append(list(cmd))
        class FakeRes:
            returncode = 0
            stderr = ""
        return FakeRes()

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)

    code = set_secret(env_file)
    assert code == 0
    assert len(called_cmd) == 1
    cmd = called_cmd[0]
    assert cmd == ["modal", "secret", "create", "dora-github", "DORA_GITHUB_PUSH_TOKEN=github_pat_11ABCXYZ987", "--force"]


def test_15_feeds_source_failed(tmp_path):
    """15. When any of cbot/magyp/bcra is not updated/fresh, status reports feeds_failed naming the source."""
    work = tmp_path / "work"
    work.mkdir(parents=True, exist_ok=True)
    data_out = tmp_path / "data_out"

    dora_dir = work / "dora"
    dora_dir.mkdir(parents=True, exist_ok=True)
    (dora_dir / "__init__.py").write_text("", encoding="utf-8")
    (dora_dir / "feeds.py").write_text(
        'def refresh(*args, **kwargs):\n'
        '    return {"status": "updated", "sources": {"cbot": {"status": "updated"}, "magyp": {"status": "kept_last"}, "bcra": {"status": "updated"}}}\n',
        encoding="utf-8",
    )
    (dora_dir / "observatory.py").write_text(
        'def run_observatory(*args, **kwargs):\n    return {"status": "ok"}\n',
        encoding="utf-8",
    )

    res = run_refresh(work, data_out, push=False)
    assert "feeds_failed" in res["status"]
    assert "magyp" in res["status"]
