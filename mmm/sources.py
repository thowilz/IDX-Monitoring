"""Reusable free-source fetchers.

Each function returns ``(value, ts_iso, source_url)`` on success or raises
``FetchError``. They never return a fabricated value. These are the
"free-first, authoritative-first" primitives the data_engineer composes per
indicator. Paywalled ideals (ICI Argus, CDS, NDF curves) have no function here
on purpose — modules mark those UNKNOWN or supply an explicit proxy.
"""

from __future__ import annotations

import csv
import io
import os
from datetime import datetime, timezone
from typing import Optional, Tuple

from .http import http_get, FetchError

Result = Tuple[float, str, str]


def _epoch_to_iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).date().isoformat()


def yahoo_last_close(symbol: str, *, range_: str = "5d") -> Result:
    """Last daily close from Yahoo Finance's public chart endpoint.

    Works for FX (``IDR=X``), indices (``DX-Y.NYB``), equities (``ADRO.JK``),
    and most futures. Returns the most recent non-null close.
    """
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    resp = http_get(url, params={"range": range_, "interval": "1d"})
    try:
        data = resp.json()["chart"]["result"][0]
        ts_list = data["timestamp"]
        closes = data["indicators"]["quote"][0]["close"]
    except (KeyError, TypeError, IndexError, ValueError) as exc:
        raise FetchError(f"Yahoo payload shape changed for {symbol}: {exc}")

    for epoch, close in zip(reversed(ts_list), reversed(closes)):
        if close is not None:
            return float(close), _epoch_to_iso(epoch), url
    raise FetchError(f"Yahoo returned only null closes for {symbol}")


def stooq_last_close(symbol: str) -> Result:
    """Last daily close from stooq.com CSV (no key). e.g. ``symbol='^spx'``."""
    url = "https://stooq.com/q/d/l/"
    resp = http_get(url, params={"s": symbol, "i": "d"})
    text = resp.text.strip()
    if not text or text.lower().startswith("no data"):
        raise FetchError(f"stooq returned no data for {symbol}")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise FetchError(f"stooq empty CSV for {symbol}")
    last = rows[-1]
    try:
        return float(last["Close"]), last["Date"], url
    except (KeyError, ValueError) as exc:
        raise FetchError(f"stooq CSV shape changed for {symbol}: {exc}")


def fred_series(series_id: str, *, api_key: Optional[str] = None) -> Result:
    """Most recent observation of a FRED series.

    Needs ``FRED_API_KEY`` (free). Without it we raise FetchError so the caller
    marks the indicator STALE rather than silently skipping it.
    """
    key = api_key or os.environ.get("FRED_API_KEY")
    if not key:
        raise FetchError(f"FRED_API_KEY not set — cannot fetch {series_id}")
    url = "https://api.stlouisfed.org/fred/series/observations"
    resp = http_get(
        url,
        params={
            "series_id": series_id,
            "api_key": key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 8,
        },
    )
    try:
        obs = resp.json()["observations"]
    except (KeyError, ValueError) as exc:
        raise FetchError(f"FRED payload shape changed for {series_id}: {exc}")
    for o in obs:  # skip "." = missing
        if o.get("value") not in (".", None, ""):
            return float(o["value"]), o["date"], url
    raise FetchError(f"FRED has no recent numeric value for {series_id}")
