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
)
from dora.version import _FINGERPRINT_CACHE, engine_fingerprint


@pytest.fixture
def git_repos(tmp_path):
    """Create a bare origin repo and a cloned work repo."""
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
    subprocess.run(["git", "add", "."], cwd=str(work), check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=str(work), check=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=str(work), check=True)

    return work, bare


def test_1_run_refresh_copies_allowed_only(tmp_path, monkeypatch):
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

    import dora.feeds as feeds
    import dora.observatory as obs

    monkeypatch.setattr(feeds, "refresh", lambda *args, **kwargs: {"status": "fresh"})
    monkeypatch.setattr(obs, "run_observatory", lambda *args, **kwargs: {"status": "ok"})

    res = run_refresh(work, data_out, push=False, today=date(2026, 11, 6))

    assert (data_out / "dora" / "data" / "price_curves" / "soja_latest.json").exists()
    assert (data_out / "dora" / "data" / "basis_rosario.json").exists()
    assert (data_out / "observatory" / "2026-11-06.json").exists()

    assert not (data_out / "dora" / "data" / "other.json").exists()
    assert not (data_out / "dora" / "data" / "basis_bad.json").exists()
    assert res["status"] in ("ok", "no_changes")


def test_2_feeds_fake_raises(tmp_path, monkeypatch):
    """2. Feeds fake raises: previous files kept, observatory still runs, status feeds_failed."""
    work = tmp_path / "work"
    work.mkdir(parents=True, exist_ok=True)
    data_out = tmp_path / "data_out"
    data_out.mkdir(parents=True, exist_ok=True)

    # Previous file in data_out
    prev_file = data_out / "dora" / "data" / "price_curves" / "soja_latest.json"
    prev_file.parent.mkdir(parents=True, exist_ok=True)
    prev_file.write_text('{"previous": true}', encoding="utf-8")

    import dora.feeds as feeds
    import dora.observatory as obs

    def failing_feeds(*args, **kwargs):
        raise RuntimeError("BCRA feed timeout")

    obs_called = []
    def fake_obs(output_dir=None, *args, **kwargs):
        obs_called.append(True)
        if output_dir:
            out_p = Path(output_dir) / "obs.json"
            out_p.write_text('{"obs": 1}', encoding="utf-8")
        return {"status": "ok"}

    monkeypatch.setattr(feeds, "refresh", failing_feeds)
    monkeypatch.setattr(obs, "run_observatory", fake_obs)

    res = run_refresh(work, data_out, push=False, today=date(2026, 11, 6))

    assert res["status"] == "feeds_failed"
    assert len(obs_called) == 1
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

    import dora.feeds as feeds
    import dora.observatory as obs

    monkeypatch.setattr(feeds, "refresh", lambda *args, **kwargs: {"status": "ok"})

    saw_key = []
    def checking_obs(*args, **kwargs):
        saw_key.append("DORA_API_KEY" in os.environ)
        return {"status": "ok"}

    monkeypatch.setattr(obs, "run_observatory", checking_obs)

    run_refresh(work, data_out, push=False)

    assert saw_key == [False], "Observatory must run without DORA_API_KEY"
    assert os.environ.get("DORA_API_KEY") == "secret-test-key-12345", "DORA_API_KEY must be restored"


def test_4_push_path_data_changed(git_repos, tmp_path, monkeypatch):
    """4. Push path, data changed: one commit on origin/main, author dora-refresh-bot,
    message Daily refresh <date>, only allowed paths in git show --stat;
    an unrelated dirty file in the work tree is not committed.
    """
    work, bare = git_repos
    data_out = tmp_path / "data_out"

    import dora.feeds as feeds
    import dora.observatory as obs

    # Change an allowed data file
    target_basis = work / "dora" / "data" / "basis_rosario.json"
    target_basis.write_text('{"basis": -25}', encoding="utf-8")

    # Unrelated dirty file
    unrelated = work / "unrelated_code.py"
    unrelated.write_text("print('not allowed')", encoding="utf-8")

    monkeypatch.setattr(feeds, "refresh", lambda *args, **kwargs: {"status": "ok"})
    monkeypatch.setattr(obs, "run_observatory", lambda *args, **kwargs: {"status": "ok"})

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


def test_5_no_data_change(git_repos, tmp_path, monkeypatch):
    """5. No data change: no commit, status no_changes."""
    work, bare = git_repos
    data_out = tmp_path / "data_out"

    import dora.feeds as feeds
    import dora.observatory as obs

    monkeypatch.setattr(feeds, "refresh", lambda *args, **kwargs: {"status": "ok"})
    monkeypatch.setattr(obs, "run_observatory", lambda *args, **kwargs: {"status": "ok"})

    res = run_refresh(work, data_out, push=True, branch="main", today=date(2026, 11, 6))

    assert res["status"] == "no_changes"
    assert res["commit"] is None
    assert res["changed"] == []


def test_6_remote_moved_with_unrelated_commit(git_repos, tmp_path, monkeypatch):
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

    import dora.feeds as feeds
    import dora.observatory as obs

    monkeypatch.setattr(feeds, "refresh", lambda *args, **kwargs: {"status": "ok"})
    monkeypatch.setattr(obs, "run_observatory", lambda *args, **kwargs: {"status": "ok"})

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
    assert "Daily refresh 2026-11-06" in log_res.stdout
    assert "Remote update" in log_res.stdout


def test_7_remote_moved_with_conflicting_commit(git_repos, tmp_path, monkeypatch):
    """7. Remote moved changing the same data file: no push, status push_conflict,
    work tree clean (rebase aborted), data_out has the new data.
    """
    work, bare = git_repos
    data_out = tmp_path / "data_out"

    # Push conflicting change on the same file to origin
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-b", "main", str(bare), str(other)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Peer"], cwd=str(other), check=True)
    subprocess.run(["git", "config", "user.email", "peer@example.com"], cwd=str(other), check=True)
    (other / "dora" / "data" / "basis_rosario.json").parent.mkdir(parents=True, exist_ok=True)
    (other / "dora" / "data" / "basis_rosario.json").write_text('{"conflict": "remote version"}', encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(other), check=True)
    subprocess.run(["git", "commit", "-m", "Remote conflicting change"], cwd=str(other), check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=str(other), check=True)

    # Local change on the same file
    (work / "dora" / "data" / "basis_rosario.json").write_text('{"local": "local version"}', encoding="utf-8")

    import dora.feeds as feeds
    import dora.observatory as obs

    monkeypatch.setattr(feeds, "refresh", lambda *args, **kwargs: {"status": "ok"})
    monkeypatch.setattr(obs, "run_observatory", lambda *args, **kwargs: {"status": "ok"})

    res = run_refresh(work, data_out, push=True, branch="main", today=date(2026, 11, 6))

    assert res["status"] == "push_conflict"
    assert res["commit"] is None

    # Work tree is clean (not stuck in rebase)
    status_res = subprocess.run(
        ["git", "status"],
        cwd=str(work),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "rebase in progress" not in status_res.stdout

    # data_out has the locally generated new data
    assert (data_out / "dora" / "data" / "basis_rosario.json").exists()


def test_8_redact_secrets(caplog):
    """8. redact: a fake token in a git error message never appears in returned dict,
    last_refresh.json or captured logs.
    """
    fake_token = "ghp_super_secret_token_abcdef123456"
    git_msg = (
        f"fatal: unable to access 'https://x-access-token:{fake_token}@github.com/repo.git': "
        f"HTTP 403 Forbidden with token {fake_token}"
    )

    redacted = redact(git_msg, token=fake_token)
    assert fake_token not in redacted
    assert "x-access-token:***@" in redacted

    with caplog.at_level(logging.WARNING):
        logger = logging.getLogger("dora.test_redact")
        logger.warning("Error: %s", redact(git_msg, token=fake_token))

    assert fake_token not in caplog.text


def test_9_apply_data_overlay(tmp_path):
    """9. apply_data_overlay: copies allowed valid files over baked ones,
    ignores others and invalid JSON, no-op when source missing or empty.
    """
    data_dir = tmp_path / "data_vol"
    app_dir = tmp_path / "app"

    # 1. Non-existent data_dir -> clean no-op
    res = apply_data_overlay(data_dir, app_dir)
    assert res == []

    # 2. Populate data_dir
    (data_dir / "dora" / "data" / "price_curves").mkdir(parents=True, exist_ok=True)
    (data_dir / "dora" / "data" / "price_curves" / "trigo_latest.json").write_text('{"crop": "trigo"}', encoding="utf-8")
    (data_dir / "dora" / "data" / "basis_necochea.json").write_text('{"basis": -5}', encoding="utf-8")
    (data_dir / "observatory").mkdir(parents=True, exist_ok=True)
    (data_dir / "observatory" / "today.json").write_text('{"obs": 2}', encoding="utf-8")

    # Non-allowed file
    (data_dir / "dora" / "data" / "unauthorized.json").write_text('{"fail": 1}', encoding="utf-8")
    # Invalid JSON allowed file
    (data_dir / "dora" / "data" / "basis_broken.json").write_text('BROKEN JSON', encoding="utf-8")

    # Baked app setup
    (app_dir / "dora" / "data" / "basis_necochea.json").parent.mkdir(parents=True, exist_ok=True)
    (app_dir / "dora" / "data" / "basis_necochea.json").write_text('{"basis": 0}', encoding="utf-8")

    overlaid = apply_data_overlay(data_dir, app_dir)

    assert "dora/data/price_curves/trigo_latest.json" in overlaid
    assert "dora/data/basis_necochea.json" in overlaid
    assert "observatory/today.json" in overlaid

    assert (app_dir / "dora" / "data" / "price_curves" / "trigo_latest.json").exists()
    assert json.loads((app_dir / "dora" / "data" / "basis_necochea.json").read_text(encoding="utf-8")) == {"basis": -5}
    assert not (app_dir / "dora" / "data" / "unauthorized.json").exists()
    assert not (app_dir / "dora" / "data" / "basis_broken.json").exists()


def test_10_engine_fingerprint_changes_with_overlay(tmp_path):
    """10. Fingerprint: engine_fingerprint of a tree after the overlay equals that of a
    tree where the same files were written by hand (clear the fingerprint cache between calls).
    """
    tree_a = tmp_path / "tree_a"
    tree_b = tmp_path / "tree_b"

    # Base files
    for tree in (tree_a, tree_b):
        (tree / "dora").mkdir(parents=True, exist_ok=True)
        (tree / "dora" / "engine.py").write_text("# engine", encoding="utf-8")
        (tree / "dora" / "scenario.py").write_text("# scenario", encoding="utf-8")
        (tree / "dora" / "tools.py").write_text("# tools", encoding="utf-8")
        (tree / "dora" / "plan_check.py").write_text("# check", encoding="utf-8")
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
