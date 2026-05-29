# Architecture Decision Record

Dated, append-only. Each entry: context → decision → consequences.

## 2026-05-29 — ADR-001: Build at repo root, not a nested `macro-monitor/`
**Context.** The bootstrap brief sketched a `macro-monitor/` top folder, but the
actual repository is `thowilz/idx-monitoring`.
**Decision.** Treat the repo root *as* the system root. The structure
(`mmm/`, `modules/`, `agents/`, `data/`, `render/`, `scripts/`) lives at the top.
**Consequences.** No redundant nesting. All paths resolve relative to the repo
root (`scripts/run_refresh.py` computes it from `__file__`), keeping it VPS-portable.

## 2026-05-29 — ADR-002: Framework = `mmm/` engine + per-domain `Module` contract
**Context.** Principle #1: framework > dashboard; never hardcode "all indicators".
**Decision.** Shared methodology lives in package `mmm/`. Each domain is a
`modules/<id>/fetch.py` that exports one `MODULE = Module(...)` object
(indicators + fetchers + transmission + regime + limitations). The engine only
talks to that object.
**Consequences.** Adding a domain = adding a folder, never editing the engine.
Consistency across modules is enforced by the dataclass contract.

## 2026-05-29 — ADR-003: Anti-hallucination is a hard invariant, not a convention
**Context.** Principle #3: no number without source + timestamp; failure → STALE.
**Decision.** `Observation.__post_init__` *raises* if a non-`OK` row carries a
value. Fetchers return `(value, ts, url)` or raise `FetchError`; the contract
converts any failure into `STALE`/`UNKNOWN` with a reason. Bound checks demote to
`SUSPECT` and drop the value.
**Consequences.** It is structurally impossible to persist a guessed value. The
store is append-only so every attempt (incl. failures) is auditable.

## 2026-05-29 — ADR-004: CSV time-series store (stdlib), openpyxl only for taxonomy
**Context.** Principle #6: lean-first. Avoid heavy deps until needed.
**Decision.** Per-module append-only CSV via the stdlib `csv` module — no pandas
in the core. `openpyxl` is used *only* to read the `.xlsx` taxonomy (a `.csv`
fallback exists so the system runs before the workbook arrives).
**Consequences.** Tiny dependency surface (`requests`, `PyYAML`, `Jinja2`,
`openpyxl`). Easy to swap the store for parquet/sqlite later behind `mmm/store.py`.

## 2026-05-29 — ADR-005: Free-first sourcing; paywalled ideals → labelled proxy or UNKNOWN
**Context.** Principle on source tiering: free + authoritative first; proxy if the
ideal is paywalled, and say so.
**Decision.** Yahoo (FX/equities/futures) and FRED (OECD/IMF macro) are the free
primitives. ICI/Argus/CDS/NDF have no free feed → `UNKNOWN` (never faked). Equity
prices used as commodity sentiment carry `is_proxy=True` and render as `PROXY`.
**Consequences.** The dashboard never disguises a proxy as the real mark; gaps are
visible, which is the point of a skeptical monitor.

## 2026-05-29 — ADR-006: Phase 0 manual entrypoint, designed drop-in for cron
**Context.** Deploy phases: run locally now, VPS+cron later with zero refactor.
**Decision.** One idempotent entrypoint `scripts/run_refresh.py` (`--review`,
`--module`, `--render-only`). Secrets via `.env`. No cron installed; an example
crontab is commented in the README.
**Consequences.** Phase-1 migration is "clone, venv, set `.env`, add the commented
crontab line" — no code change.

## 2026-05-29 — ADR-007: Locked decisions after the 2 reference modules
**Context.** Four decisions were put to the user at the v0.1.0 stop point.
**Decisions.**
1. **Next 3 domains:** `cpo` → `crude_oil` → `nickel` (largest sector weights).
2. **Sourcing:** free-first NOW (FRED/BI/BPS/ESDM/yfinance + labelled proxies),
   paid feeds LATER — keep clean seams so paid marks (ICI/Argus/CDS/NDF) drop in
   without refactor.
3. **Render:** static HTML (keep the current renderer).
4. **Revision autonomy:** user selected *fully autonomous* — **NOT yet applied.**
   It contradicts PRINSIP INTI #5 (human-gated methodology revisions), which the
   user labelled "jangan dilanggar". Held pending an explicit override
   confirmation. Recommended middle path: auto-apply only low-risk mechanical
   fixes (e.g. swap a confirmed-dead ticker for a validated one) and keep
   threshold/transmission/source-tier changes human-gated.
**Consequences.** Build order set; sourcing seams kept paid-ready; watchdog stays
human-gated until #4 is confirmed.
