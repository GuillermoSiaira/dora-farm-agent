# SPEC-11: Ready to publish (Hugging Face Space, daily refresh, observatory page)

**Status:** to implement after SPEC-09. **Branch:** `spec-11-deploy`. Do not merge into `main`; it gets reviewed first. Publishing to the accounts is done later by Guillermo; this spec only prepares the files.

## 1. Hugging Face Space (the demo)
- Add the Space metadata block at the top of `README.md` (YAML front matter: `title: DORA Farm Agent`, `sdk: gradio`, `app_file: app.py`, `pinned: false`, `license` to be decided by Guillermo; leave it out for now).
- `app.py` must read the port and host from the environment when present (`GRADIO_SERVER_NAME`, `GRADIO_SERVER_PORT`), and default to `0.0.0.0:7860` on a Space.
- The API key comes only from the Space's secrets (`DORA_API_KEY`, `DORA_API_BASE`, `DORA_MODEL`), never from files.
- A `docs/deploy.md` with the steps for Guillermo: create the Space, link the GitHub repo or push to it, add the three secrets, check the logs.

## 2. Daily refresh with GitHub Actions (free for public repos)
- `.github/workflows/refresh.yml`, scheduled once a day after the CBOT close (21:30 UTC on weekdays) and runnable by hand (`workflow_dispatch`). It:
  1. sets up Python and installs `requirements.txt`;
  2. runs `python -m dora.feeds` and `python -m dora.observatory`;
  3. commits `dora/data/price_curves/*_latest.json`, `dora/data/basis_*.json` and `observatory/*.json` only if they changed, with the message "Daily refresh <date>", authored as `github-actions[bot]`;
  4. never fails the repo state: if a feed fails, the scripts already keep the last good file, so the job succeeds and notes it.
- The workflow needs `permissions: contents: write` and nothing else. It uses no secrets: the feeds are public, and the observatory commentary stays off in the workflow.

## 3. Observatory page (static, for Vercel)
- `site/index.html`: one self-contained page (inline CSS and JS, Leaflet 1.9.4 from cdnjs) that fetches `../observatory/latest.json` at load and shows:
  - the date and the price sources;
  - a map with one marker per region, colored by return on capital (both returns from SPEC-10 once available);
  - the comparison table;
  - "provisional data" badges where a region's data is a placeholder.
- `site/vercel.json` (or a `vercel.json` at the root) so Vercel serves `site/` and the `observatory/` folder.
- Spanish and English, with a toggle, as in the demo.
- Guillermo may later redesign it with v0; the data contract (`observatory/latest.json`) is what matters, so document its fields in `docs/observatory-format.md`.

## Acceptance tests (`tests/test_deploy.py`), no network
1. The README front matter parses as YAML and has `sdk: gradio` and `app_file: app.py`.
2. `app.py` picks host and port from the environment variables when set (test the function that resolves them, without launching).
3. The workflow file parses as YAML, has a `schedule` and a `workflow_dispatch` trigger, and its run steps call `dora.feeds` and `dora.observatory`.
4. `site/index.html` exists, references `observatory/latest.json`, and loads Leaflet from cdnjs with an exact version.
5. `docs/observatory-format.md` lists every top-level and per-region field present in `observatory/latest.json`.
6. All existing tests still pass.
