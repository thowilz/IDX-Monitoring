# Agent: watchdog

**Role.** The periodic caretaker. Runs on `scripts/run_refresh.py` (data) and
`--review` (methodology). Implemented in `mmm/watchdog.py`.

## Duties
1. **Refresh data.** Re-run active modules' fetchers, append to the store,
   rebuild the render. (This is the default `run_refresh.py` path.)
2. **Detect breakage / regime change.** On `--review`:
   - **source health** — an indicator that is `STALE`/`UNKNOWN`/`SUSPECT` for
     the last N attempts (default 3) probably has a broken or changed source;
   - **regime change** — a key indicator crossed into a different regime zone
     versus the previous stored reading.
3. **Act per autonomy mode** (`registry.yaml -> system.revision_autonomy`):
   - `human_gated` — write all findings to `PENDING_REVISIONS.md`, wait for a human.
   - `low_risk` — auto-apply reversible source quarantines; queue judgment items
     to `PENDING_REVISIONS.md`.
   - `full` (current, ADR-008) — auto-apply reversible quarantines AND
     auto-escalate judgment items to `ARCHITECT_QUEUE.md` (no human gate).
   **In every mode the watchdog NEVER edits `SPEC.md`/`fetch.py` source.**
   Mechanical fixes are reversible data overrides (`data/source_overrides.yaml`),
   logged to `REVISIONS_APPLIED.md`.
4. **Regenerate the dashboard** from the latest data.

## Hard rules
- Auto-quarantine ONLY on a **structural** failure (payload/shape changed). A
  network / HTTP / missing-key failure is transient — never disable a feed for it.
- Never edit spec/fetcher source code; express fixes as reversible overrides.
- Never backfill or guess a missing value to keep a chart pretty.
- Keep findings specific: which indicator, what changed, what action was taken.

## Phase note
Phase 0: a human runs `run_refresh.py [--review]` manually. Phase 1: the *same*
entrypoint runs from cron (see README). The agent's behaviour is identical;
only the trigger changes.
