"""Append-only time-series store (CSV, stdlib only — no pandas dependency).

One CSV per module under ``data/timeseries/<module>.csv``. Append-only keeps a
full audit trail (every fetch attempt, including STALE ones, is recorded with
its ``fetched_at``), which is exactly what an anti-hallucination system wants:
you can always see when a value last refreshed and why it went stale.

Paths are resolved relative to the repo root passed in, so the whole thing is
drop-in portable to a VPS (no hardcoded /home/<user> paths).
"""

from __future__ import annotations

import csv
import os
from typing import Dict, List

from .observation import Observation, STORE_COLUMNS


class TimeSeriesStore:
    def __init__(self, root: str):
        self.dir = os.path.join(root, "data", "timeseries")
        os.makedirs(self.dir, exist_ok=True)

    def _path(self, module: str) -> str:
        return os.path.join(self.dir, f"{module}.csv")

    def append(self, observations: List[Observation]) -> None:
        if not observations:
            return
        module = observations[0].module
        path = self._path(module)
        new_file = not os.path.exists(path)
        with open(path, "a", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=STORE_COLUMNS)
            if new_file:
                writer.writeheader()
            for obs in observations:
                writer.writerow({k: obs.as_row().get(k, "") for k in STORE_COLUMNS})

    def read_all(self, module: str) -> List[dict]:
        path = self._path(module)
        if not os.path.exists(path):
            return []
        with open(path, newline="") as fh:
            return list(csv.DictReader(fh))

    def latest_per_indicator(self, module: str) -> Dict[str, dict]:
        """Most recent row (by fetched_at) for each indicator id."""
        latest: Dict[str, dict] = {}
        for row in self.read_all(module):
            ind = row["indicator"]
            cur = latest.get(ind)
            if cur is None or row["fetched_at"] >= cur["fetched_at"]:
                latest[ind] = row
        return latest
