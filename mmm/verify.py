"""Verification protocol helpers (section 7 of the MMM methodology).

These are intentionally conservative: they downgrade a value to SUSPECT (with a
reason) rather than dropping it, except for hard impossibilities. The big real
lesson baked in here: never assume a "percent" field's unit — a value that
looks like a ratio (0–1) where a percent (0–100) is expected, or vice-versa, is
flagged, not silently rescaled.
"""

from __future__ import annotations

from typing import Iterable, Optional, Tuple


def check_bound(
    value: float, low: Optional[float], high: Optional[float]
) -> Tuple[bool, str]:
    """Return (ok, reason). ok=False means the value is outside sane bounds."""
    if low is not None and value < low:
        return False, f"value {value} below sane bound {low}"
    if high is not None and value > high:
        return False, f"value {value} above sane bound {high}"
    return True, ""


def detect_percent_unit_ambiguity(value: float, *, expect: str) -> Tuple[bool, str]:
    """Guard against the percent-vs-decimal trap (e.g. NPL/NPF tagging).

    ``expect`` is "percent" (0–100) or "ratio" (0–1). We only *flag*; we never
    auto-convert, because the right fix depends on the source's documented unit.
    """
    if expect == "percent" and 0 < value < 1:
        return False, f"expected percent but got {value} — looks like a ratio (0–1)?"
    if expect == "ratio" and value > 1:
        return False, f"expected ratio (0–1) but got {value} — looks like a percent?"
    return True, ""


def cross_check(values: Iterable[float], *, rel_tol: float = 0.05) -> Tuple[bool, str]:
    """Cross-source agreement: all values within rel_tol of their mean."""
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return True, ""  # nothing to cross-check
    mean = sum(vals) / len(vals)
    if mean == 0:
        return True, ""
    worst = max(abs(v - mean) / abs(mean) for v in vals)
    if worst > rel_tol:
        return False, f"cross-source disagreement {worst:.1%} > {rel_tol:.0%}"
    return True, ""
