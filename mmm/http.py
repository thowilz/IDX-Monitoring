"""Thin HTTP helper with bounded retries.

Deliberately small. Fetch retries here are kept LOW and fast (default 2
attempts) — this is *data* fetching, where a blocked/unavailable host should
fail quickly and let the caller mark the indicator STALE. (This is separate
from the git push retry policy in the README, which uses longer backoff.)
"""

from __future__ import annotations

import time
from typing import Optional

import requests

DEFAULT_UA = (
    "Mozilla/5.0 (compatible; IHSG-MacroMonitor/0.1; "
    "+https://github.com/thowilz/idx-monitoring)"
)


class FetchError(RuntimeError):
    """Raised when a source cannot be retrieved or parsed. Caller -> STALE."""


def http_get(
    url: str,
    *,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    timeout: float = 12.0,
    attempts: int = 2,
    backoff: float = 1.5,
) -> requests.Response:
    """GET with a couple of quick retries. Raises FetchError on final failure."""
    hdrs = {"User-Agent": DEFAULT_UA, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)

    last_exc: Optional[Exception] = None
    for i in range(attempts):
        try:
            resp = requests.get(url, params=params, headers=hdrs, timeout=timeout)
            if resp.status_code >= 400:
                raise FetchError(
                    f"HTTP {resp.status_code} for {resp.url} "
                    f"({resp.headers.get('x-deny-reason', resp.reason)})"
                )
            return resp
        except FetchError:
            raise  # a 4xx/5xx is not worth retrying for our purposes
        except Exception as exc:  # network/timeout/DNS
            last_exc = exc
            if i < attempts - 1:
                time.sleep(backoff * (i + 1))
    raise FetchError(f"GET failed for {url}: {last_exc}")
