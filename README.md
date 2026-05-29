# IHSG Macro Monitoring System

A self-generating **macro monitoring framework** for the Indonesian stock market
(IHSG). It is a framework + agents that design, fill, verify and revise
per-domain monitoring **modules** — not a hand-filled dashboard.

> This is an engineering / methodology tool. **It does not give buy/sell advice.**
> Every number is traceable to a source + timestamp; failed fetches are marked
> `STALE`/`UNKNOWN`, never guessed.

See **CLAUDE.md** for the system overview and **ADR.md** for design decisions.

## Requirements
- Python 3.11+
- Network access to your data sources (Yahoo Finance, FRED, …). In a restricted
  network only `STALE`/`UNKNOWN` will appear — that is the intended fail-safe.

## Setup on a fresh machine
```bash
git clone <repo> && cd idx-monitoring
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                 # then edit .env
# add a free FRED key: https://fred.stlouisfed.org/docs/api/api_key.html
```
Drop the taxonomy workbook at `data/taxonomy_catalog_baseline.xlsx`
(columns: `sektor`, `industri`, `kode_emiten`). A `.sample.csv` ships so the
system runs before you add it — see `data/README.md`.

Load `.env` before running (e.g. `set -a; source .env; set +a`, or use
`direnv`/`python-dotenv` in your shell).

## Run (Phase 0 — manual)
**macOS / Linux one-liner** (handles venv + deps + `.env` + opens the dashboard):
```bash
./run.sh            # refresh + build + open render/index.html
./run.sh --review   # also run the watchdog
```
Or run the steps manually:
```bash
python scripts/run_refresh.py            # refresh active modules + rebuild render/index.html
python scripts/run_refresh.py --review   # also run the watchdog methodology review
python scripts/run_refresh.py --module coal     # one module only
python scripts/run_refresh.py --render-only      # rebuild HTML from stored data
```
Open `render/index.html` in a browser. The store is append-only CSV under
`data/timeseries/`; the script is idempotent and safe to re-run.

## What you get out of the box
Two fully-built reference modules demonstrating the methodology:
- **`idr_stress`** — IDR/rates/external-balance stress (USD/IDR, DXY, SBN 10y,
  reserves, BI-Rate, foreign SBN, CDS, current account, NDF).
- **`coal`** — thermal coal complex (API2/Newcastle, ICI, API5, official HBA,
  + Indonesian coal-miner equity proxies).

All other domains in `registry.yaml` are `planned` and built incrementally.

## Phase 1 — VPS + cron (later, drop-in; **do not enable yet**)
The system is already structured for this: relative paths, venv, `.env`,
idempotent entrypoint. To migrate: clone, create the venv, set `.env`, then add
a crontab entry. Example (commented — **do not enable until you've verified
Phase 0**):
```cron
# m h  dom mon dow   command
# Daily data refresh at 18:30 (after market close), logged:
# 30 18 * * 1-5  cd /opt/idx-monitoring && . .venv/bin/activate && set -a && . ./.env && set +a && python scripts/run_refresh.py >> logs/refresh.log 2>&1
# Weekly methodology review, Monday 07:00:
# 0 7 * * 1      cd /opt/idx-monitoring && . .venv/bin/activate && set -a && . ./.env && set +a && python scripts/run_refresh.py --review >> logs/review.log 2>&1
```

## Git push retry policy
Network blips on push: retry up to 4× with exponential backoff (2s, 4s, 8s, 16s).
(Separate from the fast data-fetch retries in `mmm/http.py`.)

## Revision autonomy
Set in `registry.yaml -> system.revision_autonomy`: `human_gated` | `low_risk` |
`full`. **Currently `full`** (ADR-008): on `--review` the watchdog auto-applies
reversible source quarantines (only on *structural* source breakage, never a
network/HTTP/key blip), logs them to `REVISIONS_APPLIED.md`, and auto-escalates
judgment items (thresholds, transmission, new sources) to `ARCHITECT_QUEUE.md`.
It never edits SPEC/fetcher source code. Set the value to `human_gated` to
restore the propose-and-approve workflow via `PENDING_REVISIONS.md`.

## Known design debts
Seeded in `PENDING_REVISIONS.md` (FRED series-id validation, the `api2_fut`
candidate ticker, regime-threshold calibration, BI/ESDM scrapers).
