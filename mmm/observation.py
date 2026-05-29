"""Core data model shared by every module.

Two record types:

* ``Indicator`` — *static* metadata declared by a module (lead-lag class,
  source tiering, cadence, proxy flag). This never changes at fetch time.
* ``Observation`` — a *single fetched data point*, always carrying its source
  and ``fetched_at`` timestamp plus a status. An Observation with status other
  than ``OK`` MUST have ``value is None`` — we never carry a guessed value.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

# --- lead-lag classification ------------------------------------------------
LEADING = "LEADING"        # forward expectations: futures, policy, weather, curves
COINCIDENT = "COINCIDENT"  # physical run-rate: spot index, transacted price
LAGGING = "LAGGING"        # administrative/confirmation: official reference price

VALID_CLASS = {LEADING, COINCIDENT, LAGGING}

# --- statuses ---------------------------------------------------------------
OK = "OK"            # fetched + passed verification
STALE = "STALE"      # fetch failed OR source structure changed -> no fresh value
UNKNOWN = "UNKNOWN"  # we have no way to source this (e.g. hard paywall, no proxy)
SUSPECT = "SUSPECT"  # fetched but failed a sanity/verification check


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Indicator:
    """Static description of one indicator inside a module."""

    id: str
    label: str
    classification: str            # LEADING / COINCIDENT / LAGGING
    cadence: str                   # intraday / daily / weekly / biweekly / monthly / quarterly
    authority: str                 # official / independent / aggregator
    access: str                    # free_api / scrape / paywall / manual
    latency: str                   # human-readable, e.g. "T+0", "monthly +5d"
    url: str                       # canonical source URL
    unit: str = ""                 # e.g. USD/IDR, %, USD/t, index
    is_proxy: bool = False         # True if this is a free stand-in for a paywalled ideal
    # optional sanity bounds for verification (None = unbounded)
    bound_low: Optional[float] = None
    bound_high: Optional[float] = None
    note: str = ""                 # free-form, e.g. "proxy for ICI Argus"

    def __post_init__(self):
        if self.classification not in VALID_CLASS:
            raise ValueError(
                f"Indicator {self.id}: bad classification {self.classification!r}"
            )


@dataclass
class Observation:
    """A single fetched (or failed) data point, ready to persist."""

    module: str
    indicator: str
    ts: Optional[str]              # observation timestamp (ISO) — when the value is *for*
    value: Optional[float]
    unit: str
    source: str                    # url / origin actually used
    fetched_at: str                # when WE attempted the fetch (ISO, UTC)
    status: str                    # OK / STALE / UNKNOWN / SUSPECT
    note: str = ""

    def __post_init__(self):
        # Hard anti-hallucination invariant: a non-OK row may not carry a value.
        if self.status != OK and self.value is not None:
            raise ValueError(
                f"{self.module}/{self.indicator}: status={self.status} but value "
                f"is not None — refusing to persist a guessed value."
            )

    def as_row(self) -> dict:
        return asdict(self)


# Column order for the CSV time-series store. The first five match the schema
# requested in the spec (ts, value, source, fetched_at, status); indicator/unit/
# note are a superset so a single per-module file stays self-describing.
STORE_COLUMNS = [
    "ts",
    "value",
    "source",
    "fetched_at",
    "status",
    "module",
    "indicator",
    "unit",
    "note",
]
