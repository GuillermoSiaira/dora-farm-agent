# SPEC-43 Handoff: Daily Data Refresh on Modal

**Date:** 2026-11-06  
**Branch:** `spec-43-modal-refresh` (created from `spec-41-onchain-record`)  
**Status:** Completed, Claude's review (6/11) fixes applied and verified offline (15/15 passed in `test_spec43.py`, 20/20 with `test_deploy.py`), deployed and live-checked on Modal (`cbot_latest.json` included in changed files).

---

## 1. Summary of Changes & Review Fixes (6/11)

- **Root Cause Addressed:** `.github/workflows/refresh.yml` failed on GitHub Actions due to account billing lock. Daily updates to market price curves, basis, and regional observatory are now executed autonomously on Modal with cron schedule.
- **Job Engine (`dora/refresh_job.py`):**
  - **Review Fix 1 (Subprocess in clone with PYTHONPATH):** In Modal, running `dora.feeds` directly imported `/app/dora` from the container image rather than the cloned repository in `/work`, causing feeds output to write to `/app` instead of `/work`. Fixed by running both `dora.feeds` and `dora.observatory` via `subprocess.run([sys.executable, "-m", ...], cwd=repo_path, env=env)` with `PYTHONPATH=repo_path` and `DORA_API_KEY` removed.
  - **Source Validation:** Parses JSON output of `dora.feeds` and checks sources (`cbot`, `magyp`, `bcra`). If any source status is not `updated` or `fresh`, records status as `feeds_failed: <sources>`.
  - **Review Fix 3 (`set-secret` helper):** Added `python -m dora.refresh_job set-secret [path_to_env]` which reads `DORA_GITHUB_PUSH_TOKEN` from `.env` and executes `modal secret create dora-github DORA_GITHUB_PUSH_TOKEN=... --force` without echoing the token to console or logs.
  - Copies strictly allowed files (`dora/data/price_curves/*_latest.json`, `dora/data/basis_*.json`, `observatory/*.json`) into destination only if they parse as valid JSON.
  - Implements `redact(text, token)` ensuring no PAT or basic auth tokens ever appear in logs, exceptions, or `last_refresh.json`.
  - Implements `apply_data_overlay(data_dir, app_dir)` to layer volume data onto the application filesystem and clears `_FINGERPRINT_CACHE` so cryptographic provenance accurately reflects the data used.
- **Modal Cron and Entrypoint (`infra/modal/refresh.py`):**
  - App `dora-refresh` with Debian slim + `git`.
  - Durable Modal Volume `dora-data` mounted at `/data`.
  - Scheduled function `daily_refresh()` running Monday to Friday at 21:30 UTC (`modal.Cron("30 21 * * 1-5")`).
  - Manual trigger entrypoint `refresh_now(push=False, branch="refresh-smoke")`.
- **Overlay Integration in Containers (`infra/modal/serve_mcp.py` & `infra/modal/serve_app.py`):**
  - Both containers mount `dora-data` at `/data`.
  - At container startup (before engine initialization), `data_volume.reload()` and `apply_data_overlay(Path("/data"), Path("/app"))` are executed.
  - MCP `/health` route reports `"data_refreshed": <date or null>`.
  - Web app container does not use `DORA_WARM`, ensuring scaling to zero when idle.
- **GitHub Actions Workflow (`.github/workflows/refresh.yml`):**
  - **Review Fix 2:** Verified `schedule:` trigger is completely removed, `workflow_dispatch:` is retained, and comment explains Modal migration per SPEC-43.
- **Documentation:**
  - Added "Daily data refresh (Modal)" section to `README.md`.

---

## 2. Test Suite Execution & Output

```
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\projects\dora-main
configfile: pytest.ini
collected 20 items

tests\test_spec43.py ...............                                     [ 75%]
tests\test_deploy.py .....                                               [100%]

============================== 20 passed in 22.59s ==============================
```

### Full Repository Suite (`python -m pytest -q`):
```
502 passed, 1 skipped, 3 warnings in 251.41s (0:04:11)
```

`git status --porcelain dora/data observatory` is completely empty without manual restore.

---

## 3. Modal Deployment & Live Check Output

### 3.1 Live check on Modal (`refresh_now`):
```
python -m modal run infra/modal/refresh.py::refresh_now
Triggering refresh_now on Modal (push=False, branch=refresh-smoke)...
Refresh completed: {'date': '2026-11-06', 'status': 'ok', 'changed': ['dora/data/price_curves/argentina_latest.json', 'dora/data/price_curves/cbot_latest.json', 'observatory/2026-11-06.json', 'observatory/latest.json'], 'commit': None}
Stopping app - local entrypoint completed.
✓ App completed. View run at https://modal.com/apps/guillermosiaira/main/ap-IoGxiED8lBgluNa15AecZc
```
Notice that `changed` now properly contains `'dora/data/price_curves/cbot_latest.json'` and `'dora/data/price_curves/argentina_latest.json'`.

### 3.2 Modal Deployments:
1. `dora-refresh`: Redeployed with cron `30 21 * * 1-5`
   - View: `https://modal.com/apps/guillermosiaira/main/deployed/dora-refresh`
2. `dora-mcp`: Redeployed with `/data` volume overlay
   - View: `https://modal.com/apps/guillermosiaira/main/deployed/dora-mcp`
3. `dora` (web app): Redeployed with `/data` volume overlay (scaling to zero)
   - View: `https://modal.com/apps/guillermosiaira/main/deployed/dora`

### 3.3 Live `/health` Check:
```bash
python -c "import urllib.request; resp = urllib.request.urlopen('https://guillermosiaira--dora-mcp-mcp-app.us-east.modal.run/health'); print(resp.status, resp.read().decode())"
```
**Output:**
```json
200 {"ok":true,"engine_version":"0.40.0","engine_fingerprint":"e535f7400f04323be8282c6e50cbca72d0d721732bd2432c3c8b66cab1370e33","data_refreshed":"2026-11-06"}
```
`data_refreshed` successfully returned `"2026-11-06"`.

---

## 4. Modal Secrets & Token Status

- **Secret Created:** `dora-github` in Modal (contains `DORA_GITHUB_PUSH_TOKEN`).
- **Token presence in `.env`:** Currently absent (empty).
  - As instructed in Section 3 of SPEC-43, `refresh_now` ran with `push=False` and public clone.
  - The Modal secret `dora-github` was initialized with an empty token so the deployment and cron functions load without error.

---

## 5. Next Steps for Guillermo

1. **GitHub PAT:** Create a fine-grained Personal Access Token on GitHub (starts with `github_pat_`):
   - Scope: Only repository `GuillermoSiaira/dora-farm-agent`
   - Permissions: `Contents: Read and write`
   - Paste in `.env` (or a secure location):
     ```
     DORA_GITHUB_PUSH_TOKEN=github_pat_...
     ```
2. **Update Modal Secret safely (without exposing in CLI / history):**
   Run the newly added helper:
   ```bash
   python -m dora.refresh_job set-secret
   ```
   This reads `DORA_GITHUB_PUSH_TOKEN` from `.env` and calls `modal secret create dora-github --force` without printing the token.
3. **Verify Git Push:**
   ```bash
   python -m modal run infra/modal/refresh.py::refresh_now --push --branch refresh-smoke
   ```
   Check the commit on branch `refresh-smoke` on GitHub, then delete the temporary branch.
4. **Scheduled Cron:** From Monday to Friday at 21:30 UTC, `daily_refresh()` will automatically commit and push to `main`.

