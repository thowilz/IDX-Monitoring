"""The contract every module under ``modules/<id>/`` implements.

A module's ``fetch.py`` builds and exports a single ``MODULE = Module(...)``.
The orchestrator/run_refresh only ever talks to this object — it never needs to
know the internals of a domain. This is what keeps the framework > dashboard:
adding a domain = adding one ``Module``, not editing the engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .observation import (
    Indicator,
    Observation,
    OK,
    STALE,
    UNKNOWN,
    SUSPECT,
    utcnow_iso,
)
from .http import FetchError
from .verify import check_bound

# A fetcher returns (value, ts_iso, source_url) or raises FetchError.
Fetcher = Callable[[], Tuple[float, str, str]]

# A regime rule maps an indicator value -> (zone, human meaning).
RegimeRule = Callable[[float], Tuple[str, str]]


@dataclass
class SectorImpact:
    """One row of the transmission map (domain -> IHSG sector)."""

    industri: str          # taxonomy industry code, e.g. "J41", "D23"
    sektor: str            # human sector label
    direction: str         # "+", "-", or "+/-"
    mechanism: str         # revenue / cost / royalty / demand / FX / discount_rate
    sensitive_emiten: List[str] = field(default_factory=list)
    note: str = ""


@dataclass
class Module:
    id: str
    version: str
    domain: str
    indicators: List[Indicator]
    fetchers: Dict[str, Optional[Fetcher]]   # id -> fetcher, or None if UNKNOWN/no free source
    transmission: List[SectorImpact]
    regime: Dict[str, RegimeRule]            # indicator id -> rule
    limitations: List[str]

    def indicator(self, ind_id: str) -> Indicator:
        for ind in self.indicators:
            if ind.id == ind_id:
                return ind
        raise KeyError(ind_id)

    # -- the one method the engine calls -----------------------------------
    def run(self, overrides: Optional[Dict[str, dict]] = None) -> List[Observation]:
        overrides = overrides or {}
        out: List[Observation] = []
        for ind in self.indicators:
            out.append(self._fetch_one(ind, overrides))
        return out

    def _fetch_one(self, ind: Indicator, overrides: Dict[str, dict]) -> Observation:
        now = utcnow_iso()
        fetcher = self.fetchers.get(ind.id)

        # Autonomous, reversible override: a source the watchdog has quarantined
        # reports UNKNOWN with the recorded reason — never a guessed value.
        ov = overrides.get(f"{self.id}.{ind.id}")
        if ov and ov.get("disabled"):
            return Observation(
                module=self.id, indicator=ind.id, ts=None, value=None,
                unit=ind.unit, source=ind.url, fetched_at=now, status=UNKNOWN,
                note=f"auto-disabled by watchdog: {ov.get('reason', 'no reason')}",
            )

        if fetcher is None:
            # No free/authoritative source wired up (e.g. hard paywall, no proxy).
            return Observation(
                module=self.id, indicator=ind.id, ts=None, value=None,
                unit=ind.unit, source=ind.url, fetched_at=now, status=UNKNOWN,
                note=ind.note or "no free source wired — paywall/manual only",
            )
        try:
            value, ts, src = fetcher()
        except FetchError as exc:
            return Observation(
                module=self.id, indicator=ind.id, ts=None, value=None,
                unit=ind.unit, source=ind.url, fetched_at=now, status=STALE,
                note=f"fetch failed: {exc}",
            )
        except Exception as exc:  # defensive — never let a module kill the run
            return Observation(
                module=self.id, indicator=ind.id, ts=None, value=None,
                unit=ind.unit, source=ind.url, fetched_at=now, status=STALE,
                note=f"unexpected fetcher error: {exc!r}",
            )

        # Verification: sanity bounds. Failing -> SUSPECT (kept, but flagged).
        ok, reason = check_bound(value, ind.bound_low, ind.bound_high)
        if not ok:
            return Observation(
                module=self.id, indicator=ind.id, ts=None, value=None,
                unit=ind.unit, source=src, fetched_at=now, status=SUSPECT,
                note=f"verification: {reason}",
            )
        return Observation(
            module=self.id, indicator=ind.id, ts=ts, value=value,
            unit=ind.unit, source=src, fetched_at=now, status=OK,
            note=ind.note,
        )

    # -- regime read-out from the latest stored values ---------------------
    def evaluate_regime(self, latest: Dict[str, dict]) -> List[dict]:
        signals = []
        for ind_id, rule in self.regime.items():
            row = latest.get(ind_id)
            if not row or row.get("status") != OK or row.get("value") in ("", None):
                signals.append({
                    "indicator": ind_id, "zone": "no-data",
                    "meaning": "latest value is STALE/UNKNOWN — regime not assessable",
                })
                continue
            zone, meaning = rule(float(row["value"]))
            signals.append({"indicator": ind_id, "zone": zone, "meaning": meaning})
        return signals
