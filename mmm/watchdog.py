"""Watchdog review pass (the ``--review`` path), with revision autonomy modes.

Autonomy is set in ``registry.yaml`` -> ``system.revision_autonomy``:

  * ``human_gated`` — every finding is written to PENDING_REVISIONS.md and waits
    for a human (the original PRINSIP INTI #5 default);
  * ``low_risk``    — reversible mechanical fixes are auto-applied; judgment
    items go to PENDING_REVISIONS.md;
  * ``full``        — mechanical fixes auto-applied; judgment items auto-escalated
    to ARCHITECT_QUEUE.md (no human gate) for the architect agent to action.

Critical safety rule for autonomous action: we ONLY auto-quarantine a source on
a **structural** failure (the payload/shape changed, or the source returned no
usable value), NEVER on a network/HTTP/config failure (host blocked, timeout,
missing API key). A transient outage must not cause the watchdog to disable a
perfectly good feed — that would be the monitor corrupting itself.

The watchdog still NEVER edits SPEC.md or fetch.py source. Mechanical actions
are expressed as reversible data overrides (see mmm/overrides.py).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List

from .contract import Module
from .observation import OK, STALE, UNKNOWN, SUSPECT, utcnow_iso
from .store import TimeSeriesStore
from .overrides import set_disabled

PERSISTENT_FAIL_N = 3

HUMAN_GATED = "human_gated"
LOW_RISK = "low_risk"
FULL = "full"

# Substrings in a STALE note that indicate the SOURCE itself changed/broke
# (safe to act on autonomously) vs an environmental failure (must NOT act on).
_STRUCTURAL = ("shape changed", "no recent numeric", "only null", "no data", "empty csv")
_ENVIRONMENTAL = ("http ", "get failed", "host_not_allowed", "timeout",
                  "api_key not set", "connection")


def _is_structural(note: str) -> bool:
    n = (note or "").lower()
    if any(e in n for e in _ENVIRONMENTAL):
        return False
    return any(s in n for s in _STRUCTURAL)


@dataclass
class Finding:
    module: str
    indicator: str
    kind: str          # source_structural | source_environmental | source_unknown | regime_change
    auto_fixable: bool
    message: str


def detect(store: TimeSeriesStore, module: Module) -> List[Finding]:
    findings: List[Finding] = []
    rows_by_ind: Dict[str, List[dict]] = {}
    for r in store.read_all(module.id):
        rows_by_ind.setdefault(r["indicator"], []).append(r)

    # (a) source health
    for ind in module.indicators:
        recent = rows_by_ind.get(ind.id, [])[-PERSISTENT_FAIL_N:]
        if len(recent) < PERSISTENT_FAIL_N:
            continue
        if not all(r["status"] in (STALE, UNKNOWN, SUSPECT) for r in recent):
            continue
        last_note = recent[-1].get("note", "")
        wired = module.fetchers.get(ind.id) is not None
        if wired and _is_structural(last_note):
            findings.append(Finding(
                module.id, ind.id, "source_structural", True,
                f"`{ind.id}` source looks STRUCTURALLY broken (last: {last_note}). "
                f"Auto-quarantine the dead feed; architect to wire a replacement."))
        elif wired:
            findings.append(Finding(
                module.id, ind.id, "source_environmental", False,
                f"`{ind.id}` failing {len(recent)}x but reason looks environmental "
                f"(network/HTTP/key): {last_note}. NOT auto-disabling — likely transient."))
        else:
            findings.append(Finding(
                module.id, ind.id, "source_unknown", False,
                f"`{ind.id}` persistently UNKNOWN (no free source wired). Architect "
                f"to find a free proxy or approve manual entry."))

    # (b) regime change
    for ind_id, rule in module.regime.items():
        ok_rows = [r for r in rows_by_ind.get(ind_id, [])
                   if r["status"] == OK and r["value"] not in ("", None)]
        if len(ok_rows) >= 2:
            prev_zone = rule(float(ok_rows[-2]["value"]))[0]
            cur_zone = rule(float(ok_rows[-1]["value"]))[0]
            if prev_zone != cur_zone:
                findings.append(Finding(
                    module.id, ind_id, "regime_change", False,
                    f"`{ind_id}` moved `{prev_zone}`->`{cur_zone}` "
                    f"({ok_rows[-2]['value']}->{ok_rows[-1]['value']}). Confirm SPEC "
                    f"§6 zones still describe reality; review transmission impact."))
    return findings


def _append(root: str, filename: str, heading: str, lines: List[str]) -> None:
    if not lines:
        return
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    block = f"\n## {heading} {stamp}Z\n\n" + "\n".join(lines) + "\n"
    with open(os.path.join(root, filename), "a") as fh:
        fh.write(block)


def process_review(root: str, store: TimeSeriesStore, module: Module,
                   autonomy: str) -> dict:
    """Apply/queue findings according to the autonomy mode. Returns a summary."""
    findings = detect(store, module)
    applied, queued_pending, queued_architect = [], [], []

    for f in findings:
        line = f"- **[{f.module}] {f.kind} · `{f.indicator}`** — {f.message}"

        if f.auto_fixable and autonomy in (LOW_RISK, FULL):
            wrote = set_disabled(root, f.module, f.indicator,
                                 reason=f"watchdog auto-quarantine: {f.message}",
                                 applied_at=utcnow_iso())
            applied.append(line + (" **(auto-applied: source quarantined)**"
                                   if wrote else " (already quarantined)"))
        elif autonomy == FULL:
            queued_architect.append(line + " **(auto-escalated to architect agent)**")
        else:  # human_gated, or low_risk judgment items
            queued_pending.append(line + " **(awaiting approval)**")

    _append(root, "REVISIONS_APPLIED.md", f"[{module.id}] auto-applied", applied)
    _append(root, "ARCHITECT_QUEUE.md", f"[{module.id}] auto-escalated", queued_architect)
    _append(root, "PENDING_REVISIONS.md", f"Watchdog review [{module.id}]", queued_pending)

    return {"applied": len(applied), "architect": len(queued_architect),
            "pending": len(queued_pending), "total": len(findings)}
