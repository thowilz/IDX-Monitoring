"""The contract every module under ``modules/<id>/`` implements.

A module's ``fetch.py`` builds and exports a single ``MODULE = Module(...)``.
The orchestrator/run_refresh only ever talks to this object — it never needs to
know the internals of a domain. This is what keeps the framework > dashboard:
adding a domain = adding one ``Module``, not editing the engine.

Standard methodology (v0.2 — every MMM provides these):
  * fetched/manual indicators (live free source, or human manual-input with
    provenance, or UNKNOWN — never a guessed value);
  * derived metrics computed from those indicators (e.g. NDF basis, implied PD);
  * a weighted composite score -> regime verdict;
  * a signal hierarchy (the ordered reversal/confirmation sequence to read).
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

# A derived compute takes {id: float} of OK values -> (value, note) or None.
DeriveFn = Callable[[Dict[str, float]], Optional[Tuple[float, str]]]

# A composite takes (values, prev_values) -> verdict dict (see evaluate_composite).
CompositeFn = Callable[[Dict[str, float], Dict[str, float]], dict]


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
class DerivedMetric:
    """A metric COMPUTED from other indicators, not fetched.

    e.g. NDF basis = (offshore - onshore)/spot annualised; implied PD from CDS.
    ``compute`` returns (value, note) if all inputs are present, else None ->
    the metric reports UNKNOWN (no guessed value).
    """

    id: str
    label: str
    unit: str
    compute: DeriveFn
    classification: str = "COINCIDENT"
    note: str = ""


@dataclass
class Module:
    id: str
    version: str
    domain: str
    indicators: List[Indicator]
    fetchers: Dict[str, Optional[Fetcher]]   # id -> fetcher, or None if UNKNOWN/manual
    transmission: List[SectorImpact]
    regime: Dict[str, RegimeRule]            # indicator id -> rule
    limitations: List[str]
    # --- v0.2 standard additions (default empty so older modules still load) --
    derived: List[DerivedMetric] = field(default_factory=list)
    composite: Optional[CompositeFn] = None
    signal_hierarchy: List[str] = field(default_factory=list)

    def indicator(self, ind_id: str) -> Indicator:
        for ind in self.indicators:
            if ind.id == ind_id:
                return ind
        raise KeyError(ind_id)

    # -- the one method the engine calls for base indicators ----------------
    def run(self, overrides: Optional[Dict[str, dict]] = None,
            manual: Optional[Dict[str, dict]] = None) -> List[Observation]:
        overrides = overrides or {}
        manual = manual or {}
        return [self._fetch_one(ind, overrides, manual) for ind in self.indicators]

    def _fetch_one(self, ind: Indicator, overrides: Dict[str, dict],
                   manual: Dict[str, dict]) -> Observation:
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
            # No free feed. A human MANUAL-INPUT (with source + ts) is allowed —
            # provenance is preserved, so this is NOT a guessed value.
            m = manual.get(ind.id)
            if m and m.get("value") not in (None, ""):
                try:
                    val = float(m["value"])
                except (TypeError, ValueError):
                    return Observation(
                        module=self.id, indicator=ind.id, ts=None, value=None,
                        unit=ind.unit, source=ind.url, fetched_at=now, status=SUSPECT,
                        note=f"manual input not numeric: {m.get('value')!r}")
                ok, reason = check_bound(val, ind.bound_low, ind.bound_high)
                if not ok:
                    return Observation(
                        module=self.id, indicator=ind.id, ts=None, value=None,
                        unit=ind.unit, source=m.get("source", "manual"),
                        fetched_at=now, status=SUSPECT, note=f"manual verification: {reason}")
                return Observation(
                    module=self.id, indicator=ind.id, ts=m.get("ts") or now[:10],
                    value=val, unit=ind.unit,
                    source=m.get("source", "manual entry"), fetched_at=now,
                    status=OK, note=("manual: " + m.get("note", "")).strip(": "))
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

    # -- derived metrics computed from the latest base values ---------------
    def compute_derived(self, latest: Dict[str, dict]) -> List[Observation]:
        now = utcnow_iso()
        values = numeric_values(latest)
        out: List[Observation] = []
        for dm in self.derived:
            try:
                res = dm.compute(values)
            except Exception as exc:
                res = None
                err = f"derive error: {exc!r}"
            else:
                err = "inputs missing — not computable"
            if res is None:
                out.append(Observation(
                    module=self.id, indicator=dm.id, ts=None, value=None,
                    unit=dm.unit, source="derived", fetched_at=now,
                    status=UNKNOWN, note=err))
            else:
                val, note = res
                out.append(Observation(
                    module=self.id, indicator=dm.id, ts=now[:10], value=float(val),
                    unit=dm.unit, source="derived", fetched_at=now, status=OK,
                    note=("derived: " + note).strip(": ")))
        return out

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

    # -- composite verdict --------------------------------------------------
    def evaluate_composite(self, latest: Dict[str, dict],
                           prev: Optional[Dict[str, dict]] = None) -> Optional[dict]:
        if self.composite is None:
            return None
        values = numeric_values(latest)
        prev_values = numeric_values(prev or {})
        return self.composite(values, prev_values)


def numeric_values(latest: Dict[str, dict]) -> Dict[str, float]:
    """Pull {id: float} for every OK numeric row; skip STALE/UNKNOWN/blank."""
    out: Dict[str, float] = {}
    for ind_id, row in (latest or {}).items():
        if row.get("status") == OK and row.get("value") not in ("", None):
            try:
                out[ind_id] = float(row["value"])
            except (TypeError, ValueError):
                continue
    return out
