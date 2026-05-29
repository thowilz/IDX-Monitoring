"""Watchdog review pass (the ``--review`` path).

Human-gated by design: this NEVER edits a module's SPEC.md or fetch.py. It
inspects the freshly stored data + history and *proposes* methodology revisions
by appending to ``PENDING_REVISIONS.md``. A human approves before any spec
changes. Two kinds of findings:

  * source health — an indicator that is persistently STALE/UNKNOWN across the
    last N attempts probably has a broken or changed source and the spec's
    source tiering may need revisiting;
  * regime change — a key indicator crossed into a different regime zone vs the
    previous stored reading.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, List

from .contract import Module
from .observation import OK, STALE, UNKNOWN, SUSPECT
from .store import TimeSeriesStore

PERSISTENT_FAIL_N = 3  # consecutive failed attempts before we flag the source


def _recent_statuses(store: TimeSeriesStore, module: str, indicator: str, n: int):
    rows = [r for r in store.read_all(module) if r["indicator"] == indicator]
    return [r["status"] for r in rows[-n:]]


def review_module(store: TimeSeriesStore, module: Module,
                  latest: Dict[str, dict], signals: List[dict]) -> List[str]:
    proposals: List[str] = []

    # (a) source health
    for ind in module.indicators:
        statuses = _recent_statuses(store, module.id, ind.id, PERSISTENT_FAIL_N)
        if len(statuses) >= PERSISTENT_FAIL_N and all(
            s in (STALE, UNKNOWN, SUSPECT) for s in statuses
        ):
            proposals.append(
                f"- **[{module.id}] source-health · `{ind.id}`** — last "
                f"{len(statuses)} attempts were {statuses}. Source "
                f"`{ind.url}` ({ind.authority}/{ind.access}) may be broken or "
                f"changed. *Proposal:* re-validate the source tiering / find a "
                f"better free proxy; update SPEC §4. **(awaiting approval)**"
            )

    # (b) regime change vs previous reading
    history: Dict[str, List[dict]] = {}
    for r in store.read_all(module.id):
        history.setdefault(r["indicator"], []).append(r)
    for ind_id, rule in module.regime.items():
        rows = [r for r in history.get(ind_id, []) if r["status"] == OK and r["value"] not in ("", None)]
        if len(rows) >= 2:
            prev_zone = rule(float(rows[-2]["value"]))[0]
            cur_zone = rule(float(rows[-1]["value"]))[0]
            if prev_zone != cur_zone:
                proposals.append(
                    f"- **[{module.id}] regime-change · `{ind_id}`** — moved "
                    f"`{prev_zone}` → `{cur_zone}` ({rows[-2]['value']} → "
                    f"{rows[-1]['value']} {ind_id}). *Proposal:* confirm the "
                    f"threshold zones in SPEC §6 still describe reality; review "
                    f"transmission impact. **(awaiting approval)**"
                )
    return proposals


def write_pending(root: str, proposals: List[str]) -> int:
    if not proposals:
        return 0
    path = os.path.join(root, "PENDING_REVISIONS.md")
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    block = f"\n## Watchdog review {stamp}Z\n\n" + "\n".join(proposals) + "\n"
    with open(path, "a") as fh:
        fh.write(block)
    return len(proposals)
