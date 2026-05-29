# CLAUDE.md — IHSG Macro Monitoring System

System summary + operating guide for any agent (or human) working in this repo.

## What this is
A **self-generating macro monitoring framework** for the Indonesian equity
market (IHSG). Not a static dashboard you fill by hand: a framework + agents
that design, fill, verify and revise monitoring *modules* on a schedule.

This is an **engineering / methodology** system. It does **not** give buy/sell
opinions. Default stance: skeptical, anti-cheerleader. Every number is traceable
to a source + timestamp; if a fetch fails it is marked `STALE`/`UNKNOWN`, never
guessed.

## Core principles (do not violate)
1. **Framework > dashboard.** Unit of work = one Macro Monitoring Module (MMM)
   for one domain. The system = registry of MMMs + shared methodology + agents.
2. **Uniform methodology (v0.2, 12-section template).** Every MMM follows the
   same spec (see `agents/architect.md`) AND provides the standard analytics
   layer: a manual-input channel for paywalled inputs, derived metrics, a
   weighted composite score → verdict, and a signal hierarchy. Cross-module
   consistency beats single-module completeness.
3. **Verification-first / anti-hallucination.** No value without source +
   `fetched_at`. Failed fetch → `STALE`. Enforced in code (`mmm/observation.py`).
4. **Modular + semver.** 1 module = 1 SPEC.md + 1 fetch.py + 1 registry entry.
5. **Revision autonomy (configurable).** `registry.yaml -> system.revision_autonomy`
   = `human_gated` | `low_risk` | `full`. **Currently `full`** (ADR-008, overrides
   the original human-gated principle per explicit user choice): the watchdog
   auto-applies reversible source quarantines on *structural* failures only and
   auto-escalates judgment items to `ARCHITECT_QUEUE.md`. It still never edits
   SPEC/fetch source code, and never quarantines on a network/HTTP/key failure.
6. **Lean-first.** Started with 2 reference modules (`idr_stress`, `coal`).

## Layout
```
mmm/            shared engine: data model, http, sources, verify, store,
                registry, contract (Module), render, watchdog
modules/<id>/   SPEC.md (methodology) · fetch.py (MODULE contract) · REDTEAM.md
agents/         role definitions: architect, redteam, data_engineer, watchdog, orchestrator
data/           taxonomy_catalog_baseline.xlsx (you provide) + timeseries/*.csv (generated)
render/         index.html (generated static dashboard)
scripts/        run_refresh.py (the one entrypoint)
registry.yaml   catalogue of all modules + version + status + last_refresh
PENDING_REVISIONS.md  human-gated methodology proposals
ADR.md          dated architecture decisions
```

## How to run (Phase 0 — manual)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add FRED_API_KEY (free) for the macro proxies
python scripts/run_refresh.py            # refresh active modules + rebuild render
python scripts/run_refresh.py --review   # also run watchdog -> PENDING_REVISIONS.md
open render/index.html
```
`run_refresh.py` is idempotent (append-only store) and safe to re-run.

## The module contract (how to add a domain)
A module's `fetch.py` builds one `MODULE = Module(...)` with: `indicators`
(static metadata, lead-lag class, tiering, cadence), `fetchers` (id → callable
returning `(value, ts, url)` or `None` if no free source), `transmission`
(`SectorImpact` rows using taxonomy industry codes), `regime` (id → zone rule),
`limitations`. The engine calls only `MODULE.run()` and `MODULE.evaluate_regime()`.
Follow `architect → redteam → data_engineer → register` (see `agents/`).

## Important nuances
- Live data sources are blocked unless the host network allows them. In a
  locked-down sandbox the run will show `STALE`/`UNKNOWN` for everything — that
  is correct behaviour, not a bug. On an open-network machine the same code
  pulls real values.
- `sbn10y`/`reserves` are FRED **proxies**; `api2_fut` is an unvalidated
  candidate ticker — see `PENDING_REVISIONS.md`.
- Regime thresholds are provisional and must be calibrated before they drive
  any signal.
