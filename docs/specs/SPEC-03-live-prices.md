# SPEC-03: Live price feeds

**Status:** to implement after SPEC-02. **Branch:** `spec-03-live-prices`. Do not merge into `main`; it gets reviewed first.

## Why
DORA is an agent: prices must update themselves. Nobody should paste quotes by hand. SPEC-01 left the price curves as static snapshot files. This spec adds feeds that refresh those snapshots automatically, with a safe fallback to the last good snapshot.

## Sources (checked on 2026-10-27)
| Source | Access | Use |
|---|---|---|
| CBOT futures via Yahoo Finance chart API: `https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d` | Works without a key. Each contract by symbol, e.g. `ZCZ26.CBT`; the price is in cents/bu (`currency: USX`). | US curve (corn, soybean, wheat) |
| Bolsa de Comercio de Rosario, pizarra prices | **The page has a CAPTCHA. Do not scrape it and do not try to get around it.** | Not used automatically. Argentine prices = CBOT + basis until there is an allowed source (see below). |
| Bolsa de Cereales de Buenos Aires | **Blocks automated access (Cloudflare, HTTP 403 on every page). Not used.** | — |
| Argentina's open-data series API (apis.datos.gob.ar) | Works, but grain price series stop in 2017–2025: not current. | Not used for prices. |

Allowed options for live Argentine prices, to pursue after the hackathon: MAGyP's official daily FOB prices (find the current page), Matba-Rofex's market data API (needs an account), or a data agreement with the Bolsa de Comercio de Rosario or the Bolsa de Cereales.

Yahoo's terms allow personal, non-commercial use. That is fine for the hackathon demo, with the source shown on every price. A commercial version needs a licensed feed (CME DataMine, Barchart, or Matba-Rofex's API for Argentina); leave the adapter interface ready for that.

## Scope
1. `dora/feeds.py` with a small adapter interface: `fetch() -> snapshot dict` (the same format as the files in `dora/data/price_curves/`).
2. A **CBOT adapter** (`YahooCbotFeed`) that builds the contract symbols for the next months and fetches each one:
   - Month codes: F=Jan, H=Mar, K=May, N=Jul, Q=Aug, U=Sep, X=Nov, Z=Dec.
   - Corn listed months: H, K, N, U, Z. Soybean: F, H, K, N, Q, U, X. Wheat (ZW): H, K, N, U, Z.
   - Symbols: `ZC`, `ZS`, `ZW` + month code + two-digit year + `.CBT`.
   - Take `regularMarketPrice` from `chart.result[0].meta`. Skip contracts that return no data. Fetch up to 18 months ahead.
   - The snapshot gets `"source": "CBOT futures via Yahoo Finance (delayed)"`, `"as_of"` = date of the fetch, `"unit": "cents/bu"`, `"placeholder": false`.
3. **Cache and fallback**:
   - `refresh(feed, max_age_hours=24)` writes `dora/data/price_curves/cbot_latest.json` only if the existing file is older than `max_age_hours`.
   - It never overwrites a good file with an empty or partial fetch (fewer than 2 contracts per crop counts as partial).
   - On any network error it keeps the last file and returns a status saying so.
4. **Argentine basis**: a new data file `dora/data/basis_argentina.json` with a default basis per crop against CBOT (USD/t, negative), its source and date, marked `"placeholder": true` until a real source is found. The tools use it when `price_curve_source` is `cbot_latest` and `region` is Argentina.
5. **Tool**: a new tool `refresh_prices` (no arguments) that runs the CBOT refresh and returns `{"status": "updated" | "fresh" | "kept_last", "as_of": ..., "contracts": n}`. `build_scenario` also calls `refresh` silently when `price_curve_source` is `cbot_latest`.
6. **Command line**: `python -m dora.feeds` refreshes and prints the curve, for a daily scheduled task.

## Rules for network access
- Timeout 10 seconds per request, user agent `"DORA-farm-agent/0.1 (+https://github.com/GuillermoSiaira/dora-farm-agent)"`, at most one request per contract per refresh, and a 0.5 s pause between requests.
- Respect HTTP errors and rate limits: on 429 stop and keep the last file.
- Never bypass CAPTCHAs, logins or bot protection. If a source blocks automated access, it is not used.

## Acceptance tests (`tests/test_feeds.py`)
**No network in tests:** mock the HTTP function.
1. Symbols built for corn from Oct 2026: the first ones are `ZCZ26.CBT`, `ZCH27.CBT`, `ZCK27.CBT`, `ZCN27.CBT`…
2. A mocked response with `regularMarketPrice` 454.25 for `ZCZ26.CBT` gives `curve.corn["2026-12"] == 454.25` and, through `load_curve`, 178.83 USD/t (rel 1e-4).
3. Partial fetch (one contract) does not overwrite an existing good file.
4. Network error → status `kept_last`, the file is unchanged.
5. Fresh file (age < 24 h) → status `fresh`, no HTTP calls made.
6. `refresh_prices` through `run_tool` returns valid JSON with `status`.
7. All existing tests still pass.

An optional live test, marked `@pytest.mark.live` and skipped by default, fetches `ZCZ26.CBT` for real.
