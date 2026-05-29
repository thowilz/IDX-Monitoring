#!/usr/bin/env python3
"""Single entrypoint for the IHSG Macro Monitor (Fase 0: run manually).

    python scripts/run_refresh.py            # refresh active modules + rebuild render
    python scripts/run_refresh.py --review   # also run watchdog -> PENDING_REVISIONS.md
    python scripts/run_refresh.py --module coal   # restrict to one module
    python scripts/run_refresh.py --render-only   # rebuild HTML from stored data only

Idempotent and safe to call repeatedly (the store is append-only; each run adds
a fresh dated set of observations). All paths are relative to the repo root, so
this is drop-in for a VPS crontab later (Fase 1) with no code changes.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from datetime import datetime, timezone

# Make the repo root importable regardless of where we're invoked from.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from mmm.registry import load_registry, save_registry, active_modules, update_module
from mmm.store import TimeSeriesStore
from mmm.taxonomy import load_taxonomy
from mmm.render import build_render, assemble_module_payload
from mmm.watchdog import process_review
from mmm.overrides import load_overrides
from mmm.observation import OK, STALE, UNKNOWN, SUSPECT, utcnow_iso

STATUS_GLYPH = {OK: "OK   ", STALE: "STALE", UNKNOWN: "UNKWN", SUSPECT: "SUSPCT"}


def load_module(module_id: str):
    mod = importlib.import_module(f"modules.{module_id}.fetch")
    return mod.MODULE


def main() -> int:
    ap = argparse.ArgumentParser(description="IHSG Macro Monitor refresh")
    ap.add_argument("--review", action="store_true",
                    help="run watchdog methodology review -> PENDING_REVISIONS.md")
    ap.add_argument("--module", help="restrict to a single module id")
    ap.add_argument("--render-only", action="store_true",
                    help="skip fetching; rebuild HTML from stored data")
    args = ap.parse_args()

    reg = load_registry(ROOT)
    store = TimeSeriesStore(ROOT)
    taxonomy = load_taxonomy(ROOT)
    overrides = load_overrides(ROOT)
    autonomy = (reg.get("system", {}) or {}).get("revision_autonomy", "human_gated")

    targets = active_modules(reg)
    if args.module:
        targets = [m for m in targets if m["id"] == args.module]
        if not targets:
            print(f"[!] module '{args.module}' is not active in registry.yaml")
            return 2

    print(f"== IHSG Macro Monitor refresh @ {utcnow_iso()} ==")
    print(f"   root={ROOT}")
    print(f"   taxonomy: {taxonomy.source} "
          f"({len(taxonomy.rows)} rows)" if taxonomy.available
          else f"   taxonomy: NOT PRESENT — transmission codes shown unvalidated")
    print()

    payloads = []
    total_pending = 0

    for entry in targets:
        mid = entry["id"]
        module = load_module(mid)
        print(f"-- {mid} v{module.version} : {module.domain}")

        if not args.render_only:
            observations = module.run(overrides=overrides)
            store.append(observations)
            counts = {}
            for o in observations:
                counts[o.status] = counts.get(o.status, 0) + 1
                val = "" if o.value is None else o.value
                print(f"   [{STATUS_GLYPH.get(o.status, o.status):6}] "
                      f"{o.indicator:16} {str(val):>14} {o.unit:8} "
                      f"{('· ' + o.note) if o.note and o.status != OK else ''}")
            summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
            update_module(reg, mid, last_refresh=utcnow_iso(), last_summary=summary)
            print(f"   summary: {summary}")

        latest = store.latest_per_indicator(mid)
        signals = module.evaluate_regime(latest)
        for s in signals:
            print(f"   regime[{s['indicator']}] -> {s['zone']}: {s['meaning']}")

        if args.review and not args.render_only:
            summ = process_review(ROOT, store, module, autonomy)
            total_pending += summ["pending"]
            if summ["total"]:
                print(f"   watchdog[{autonomy}]: {summ['total']} finding(s) -> "
                      f"applied={summ['applied']} architect={summ['architect']} "
                      f"pending={summ['pending']}")

        payloads.append(assemble_module_payload(
            module, latest, signals, taxonomy, entry.get("last_refresh", "")))
        print()

    if not args.render_only:
        save_registry(ROOT, reg)

    out = build_render(ROOT, payloads, taxonomy)
    print(f"== render written: {os.path.relpath(out, ROOT)} ==")
    if args.review:
        print(f"== watchdog autonomy={autonomy}: {total_pending} item(s) left for "
              f"human approval (applied/escalated items are logged) ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
