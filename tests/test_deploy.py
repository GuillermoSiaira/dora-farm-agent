"""Acceptance tests for SPEC-11: ready to publish (Hugging Face Space, daily refresh, observatory page). No network calls."""
import json
import os
from pathlib import Path
import pytest
import yaml

from app import resolve_server_config

ROOT = Path(__file__).resolve().parent.parent


# 1. The README front matter parses as YAML and has sdk: gradio and app_file: app.py.
def test_readme_front_matter():
    readme_path = ROOT / "README.md"
    assert readme_path.is_file(), "README.md must exist"

    text = readme_path.read_text(encoding="utf-8")
    assert text.startswith("---"), "README.md must start with YAML front matter marker '---'"

    parts = text.split("---", 2)
    assert len(parts) >= 3, "README.md must contain opening and closing '---' markers for front matter"
    front_raw = parts[1]

    data = yaml.safe_load(front_raw)
    assert isinstance(data, dict), "Front matter must parse into a YAML dictionary"
    assert data.get("title") == "DORA Farm Agent"
    assert data.get("sdk") == "gradio"
    assert data.get("app_file") == "app.py"


# 2. app.py picks host and port from the environment variables when set (test the function without launching).
def test_app_picks_host_and_port_from_env(monkeypatch):
    # Test defaults
    monkeypatch.delenv("GRADIO_SERVER_NAME", raising=False)
    monkeypatch.delenv("GRADIO_SERVER_PORT", raising=False)
    host_def, port_def = resolve_server_config()
    assert host_def == "0.0.0.0"
    assert port_def == 7860

    # Test custom env vars
    monkeypatch.setenv("GRADIO_SERVER_NAME", "127.0.0.1")
    monkeypatch.setenv("GRADIO_SERVER_PORT", "8080")
    host_custom, port_custom = resolve_server_config()
    assert host_custom == "127.0.0.1"
    assert port_custom == 8080

    # Test invalid port fallback
    monkeypatch.setenv("GRADIO_SERVER_PORT", "invalid_number")
    _, port_fallback = resolve_server_config()
    assert port_fallback == 7860


# 3. The workflow file parses as YAML, has a schedule and a workflow_dispatch trigger,
#    and its run steps call dora.feeds and dora.observatory.
def test_workflow_file_triggers_and_steps():
    workflow_path = ROOT / ".github" / "workflows" / "refresh.yml"
    assert workflow_path.is_file(), ".github/workflows/refresh.yml must exist"

    content = workflow_path.read_text(encoding="utf-8")
    wf = yaml.safe_load(content)

    # In PyYAML, 'on' key parses as boolean True or string 'on'
    triggers = wf.get(True) or wf.get("on")
    assert triggers is not None, "Workflow must define triggers ('on')"
    assert "schedule" in triggers, "Workflow must include schedule trigger"
    assert "workflow_dispatch" in triggers, "Workflow must include workflow_dispatch trigger"

    # Check that steps call dora.feeds and dora.observatory
    jobs = wf.get("jobs", {})
    assert "refresh" in jobs
    steps = jobs["refresh"].get("steps", [])
    step_runs = " ".join(str(s.get("run", "")) for s in steps)

    assert "dora.feeds" in step_runs
    assert "dora.observatory" in step_runs


# 4. site/index.html exists, references observatory/latest.json, and loads Leaflet from cdnjs with an exact version.
def test_site_index_html():
    index_path = ROOT / "site" / "index.html"
    assert index_path.is_file(), "site/index.html must exist"

    html = index_path.read_text(encoding="utf-8")
    assert "observatory/latest.json" in html, "site/index.html must reference observatory/latest.json"
    assert "cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js" in html, "site/index.html must load Leaflet 1.9.4 from cdnjs"
    assert "cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css" in html, "site/index.html must load Leaflet 1.9.4 css from cdnjs"


# 5. docs/observatory-format.md lists every top-level and per-region field present in observatory/latest.json.
def test_observatory_format_docs_completeness():
    latest_path = ROOT / "observatory" / "latest.json"
    doc_path = ROOT / "docs" / "observatory-format.md"
    assert latest_path.is_file(), "observatory/latest.json must exist"
    assert doc_path.is_file(), "docs/observatory-format.md must exist"

    with open(latest_path, encoding="utf-8") as f:
        data = json.load(f)

    doc_text = doc_path.read_text(encoding="utf-8")

    # Top-level fields
    for field in data.keys():
        assert f"`{field}`" in doc_text, f"Top-level field '{field}' must be documented in docs/observatory-format.md"

    # Per-region fields (inspect first region)
    regions = data.get("regions", {})
    assert len(regions) > 0, "latest.json must contain regions"
    sample_reg = next(iter(regions.values()))

    for field in sample_reg.keys():
        assert f"`{field}`" in doc_text, f"Regional field '{field}' must be documented in docs/observatory-format.md"
