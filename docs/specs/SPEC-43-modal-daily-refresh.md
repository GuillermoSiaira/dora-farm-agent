# SPEC-43: the daily data refresh runs on Modal, not on GitHub Actions

**Status:** ready (6/11), approved by Guillermo. Implement **before SPEC-42**, on branch `spec-43-modal-refresh` created from `spec-41-onchain-record`, in **`D:\projects\dora-main`**. SPEC-42 then branches from `spec-43-modal-refresh`. Do not merge, do not push the branch (the job itself pushes data, see section 3). Commit with messages starting `SPEC-43 implementation:`; write the handoff and Claude reviews.

Touch only: a new `infra/modal/refresh.py`, a new `dora/refresh_job.py`, `infra/modal/serve_mcp.py` and `infra/modal/serve_app.py` (mount the data volume and apply the overlay at start), `.github/workflows/refresh.yml` (remove the schedule), `README.md` (one short paragraph), a new `tests/test_spec43.py` and the handoff.

**Why.** `.github/workflows/refresh.yml` runs `python -m dora.feeds` and `python -m dora.observatory` Monday to Friday at 21:30 UTC, then commits the new price curves, basis files and observatory to `main`. It has **never succeeded**: there is no commit by `github-actions` in `main`, and since at least 31/10 every run dies in 3 s with "account is locked due to a billing issue". GitHub accepts no prepaid card, and Guillermo has only prepaid cards, so the fix can't be "pay GitHub". The data the app and the MCP serve stays frozen at whatever was last committed by hand (price curves: 1/11). Modal already runs the app (`serve_app.py`), the MCP and the on-chain publisher (`serve_mcp.py`), has credits, and supports cron.

## 1. The job (`dora/refresh_job.py`, no Modal imports)
`run_refresh(repo_dir: Path, data_out: Path, *, push: bool, branch: str = "main", today: date | None = None) -> dict` does what the workflow did, in this order:
1. `dora.feeds.refresh()` (same call as `python -m dora.feeds`). If it raises, log the error, keep the previous files and continue (the workflow did `|| echo`). Status `feeds_failed`.
2. `dora.observatory` (same entry point as `python -m dora.observatory`). **No paid model call**: run it without `DORA_API_KEY` in the environment, exactly as the workflow did (no commentary). If it raises, status `observatory_failed`, keep going.
3. Copy the **allowed files** into `data_out` (the Modal Volume), keeping relative paths. Allowed set, same as the workflow's `git add`: `dora/data/price_curves/*_latest.json`, `dora/data/basis_*.json`, `observatory/*.json`. A file is copied only if it parses as JSON. Nothing else is ever copied.
4. If `push`: section 3.
Returns `{"date", "status": "ok"|"no_changes"|"feeds_failed"|"observatory_failed"|"push_conflict"|"push_failed", "changed": [relative paths], "commit": sha|None}`, and writes it as `data_out/last_refresh.json` (the MCP `/health` adds it, section 4).

## 2. Modal (`infra/modal/refresh.py`)
- App `dora-refresh`, same image recipe as `serve_mcp.py` (requirements.txt), plus `git` (`apt_install("git")`).
- Volume `dora-data` (`create_if_missing=True`) mounted at `/data`.
- `@app.function(schedule=modal.Cron("30 21 * * 1-5"), secrets=[modal.Secret.from_name("dora-github")], volumes={"/data": vol}, timeout=1200)` `daily_refresh()`: shallow-clone the repo (`git clone --depth 20 --branch main https://x-access-token:$TOKEN@github.com/GuillermoSiaira/dora-farm-agent.git /work`), call `run_refresh("/work", Path("/data"), push=True, branch=os.environ.get("DORA_REFRESH_BRANCH", "main"))`, then `vol.commit()`.
- `refresh_now(push: bool = False, branch: str = "refresh-smoke")` as a `@app.local_entrypoint`-callable function for manual runs.
- The repo is cloned fresh each run: the job works on what is in `main`, not on what was baked into the image.

## 3. Pushing the data to GitHub
Pushing to a public repo does not depend on Actions billing (Guillermo pushed `7d047e7` on 5/11 with the account locked).
- Token: a **fine-grained personal access token** that Guillermo creates (GitHub → Settings → Developer settings → Fine-grained tokens): only repository `GuillermoSiaira/dora-farm-agent`, permission **Contents: read and write**, nothing else, expiry 1 year. He pastes it into `.env` as `DORA_GITHUB_PUSH_TOKEN=`. You create the Modal secret from `.env` without printing it: `modal secret create dora-github DORA_GITHUB_PUSH_TOKEN=<value read from .env>` run from a Python helper that never echoes the value. If the line is not in `.env`, stop at this step, finish the rest with `push=False`, and say in the handoff what's missing.
- Commit: `git add` the allowed set only; if `git diff --cached --quiet`, status `no_changes`, no commit. Otherwise author `dora-refresh-bot <dora-refresh-bot@users.noreply.github.com>`, message `Daily refresh YYYY-MM-DD` (UTC), push to `branch`.
- If the push is rejected because the remote moved: `git pull --rebase` once and push again. If the rebase conflicts (someone changed the same data files), `git rebase --abort`, status `push_conflict`, no push; the Volume still has the new data (section 4), so the app is fresh anyway.
- **The token never appears** in logs, exceptions, `last_refresh.json` or the handoff: every git stdout/stderr and exception text goes through `redact(text)` that replaces the token and any `x-access-token:...@` with `***`.
- Never `--force`. Never touch any path outside the allowed set.

## 4. The app and the MCP read the fresh data without a redeploy
Today `serve_app.py` and `serve_mcp.py` bake `dora/data` into the image at deploy time, so fresh data needs a redeploy. Add to both: mount `dora-data` at `/data` (read-only use) and, at container start, **before importing `dora`**, call `apply_data_overlay(Path("/data"), Path("/app"))` (in `dora/refresh_job.py`): for each allowed file under `/data` that parses as JSON, copy it over the baked one; skip anything else. If `/data` is empty or missing, do nothing (the baked files stay). The MCP's `/health` adds `"data_refreshed": <date from /data/last_refresh.json or null>`.
`engine_fingerprint()` hashes `dora/data` as it is on disk, so after the overlay the fingerprint changes with the data. That is correct: the provenance must name the data the plan was solved with. Say it in the handoff and in the README paragraph.
`serve_mcp.py` currently ignores `observatory` in the image; the overlay may add `/app/observatory/` files: create the directory if needed.

## 5. GitHub Actions
In `.github/workflows/refresh.yml` remove the `schedule:` block and keep `workflow_dispatch:`, with a comment at the top: "The daily refresh runs on Modal (infra/modal/refresh.py, SPEC-43). This workflow is kept for a manual run once the GitHub account is unlocked." This stops the daily failure emails.

## Tests (`tests/test_spec43.py`, no network, no Modal, no LLM)
Use a temporary git repo (`git init` in `tmp_path`, plus a bare repo as `origin`), and monkeypatch `dora.feeds.refresh` and the observatory entry point with fakes that write known JSON.
1. `run_refresh(push=False)` copies exactly the allowed files into `data_out`, with relative paths; a non-allowed file written by the fake (e.g. `dora/data/other.json`) is not copied; an allowed file with invalid JSON is not copied.
2. Feeds fake raises: previous files kept, observatory still runs, status `feeds_failed`.
3. `DORA_API_KEY` set in the test environment: the observatory fake sees it unset (no paid call).
4. Push path, data changed: one commit on `origin/main`, author `dora-refresh-bot`, message `Daily refresh <date>`, only allowed paths in `git show --stat`; an unrelated dirty file in the work tree is not committed.
5. No data change: no commit, status `no_changes`.
6. Remote moved with an unrelated commit: rebase, push succeeds, both commits on `origin/main`.
7. Remote moved changing the same data file: no push, status `push_conflict`, work tree clean (rebase aborted), `data_out` has the new data.
8. `redact`: a fake token in a git error message never appears in the returned dict, `last_refresh.json` or captured logs (`caplog`).
9. `apply_data_overlay`: copies allowed valid files over the baked ones, ignores others and invalid JSON, no-op when the source is missing or empty.
10. Fingerprint: `engine_fingerprint` of a tree after the overlay equals that of a tree where the same files were written by hand (clear the fingerprint cache between calls).
11. The workflow file has no `schedule` and has `workflow_dispatch`.
12. After the suite, `git status --porcelain dora/data observatory` in the repo is empty.
Run `tests/test_spec43.py`, `tests/test_spec40.py`, `tests/test_spec41.py` and the full suite; restore price files if anything touched them.

## Live check (do it, and paste the real output in the handoff)
1. `modal run infra/modal/refresh.py::refresh_now` (push=False): the feeds run from Modal's network, the Volume `dora-data` gets the files. Paste the returned dict. If a source blocks Modal's IPs, say which and leave its previous file.
2. If the token is in `.env`: `modal run infra/modal/refresh.py::refresh_now --push --branch refresh-smoke`: a commit lands on the remote branch `refresh-smoke` (not `main`). Paste the commit sha. Leave the branch; Guillermo deletes it.
3. `modal deploy infra/modal/refresh.py`, then redeploy `serve_mcp.py` (the app `serve_app.py` too, with the same flags it has today, without `DORA_WARM`): `/health` shows `data_refreshed`.
The scheduled run pushes to `main` on its own from the next weekday at 21:30 UTC (18:30 Buenos Aires).

## Handoff (`docs/handoff/spec-43-modal-refresh.md`)
What changed, test output, the live check output, the Modal apps and secrets created (names only, never values), whether the token was present, and what Guillermo must do: create the token if missing, delete `refresh-smoke`, and check the first `Daily refresh` commit on `main`.
