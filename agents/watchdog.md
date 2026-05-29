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
3. **Propose, never edit.** Write findings to `PENDING_REVISIONS.md` under a
   dated heading. **Do NOT modify any `SPEC.md` or `fetch.py`.** Methodology
   changes are human-gated (PRINSIP INTI #5).
4. **Regenerate the dashboard** from the latest data.

## Hard rules
- Never silently "fix" a spec or change a threshold. Propose it.
- Never backfill or guess a missing value to keep a chart pretty.
- Keep proposals specific: which indicator, what changed, what to do, and the
  fact that it awaits approval.

## Phase note
Phase 0: a human runs `run_refresh.py [--review]` manually. Phase 1: the *same*
entrypoint runs from cron (see README). The agent's behaviour is identical;
only the trigger changes.
