"""Source overrides — the reversible, auditable layer the watchdog may write to
*autonomously* without ever editing a module's SPEC.md or fetch.py source code.

Having a cron process rewrite its own Python/spec is unsafe (it can silently
corrupt the monitor). So autonomous mechanical actions are expressed as data:
``data/source_overrides.yaml`` maps ``"<module>.<indicator>"`` to an override
the engine consults at fetch time. Today the only override is ``disabled`` —
used to auto-quarantine a confirmed-dead wired source so we stop retrying it and
the indicator honestly reports UNKNOWN with the reason. Everything here is
reversible (delete the entry) and logged.
"""

from __future__ import annotations

import os
from typing import Dict

import yaml


def _path(root: str) -> str:
    return os.path.join(root, "data", "source_overrides.yaml")


def load_overrides(root: str) -> Dict[str, dict]:
    path = _path(root)
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        return yaml.safe_load(fh) or {}


def save_overrides(root: str, data: Dict[str, dict]) -> None:
    with open(_path(root), "w") as fh:
        yaml.safe_dump(data, fh, sort_keys=True, allow_unicode=True)


def key(module: str, indicator: str) -> str:
    return f"{module}.{indicator}"


def set_disabled(root: str, module: str, indicator: str, reason: str, applied_at: str) -> bool:
    """Return True if a new disable override was written (False if already set)."""
    data = load_overrides(root)
    k = key(module, indicator)
    if data.get(k, {}).get("disabled"):
        return False
    data[k] = {"disabled": True, "reason": reason, "applied_at": applied_at}
    save_overrides(root, data)
    return True
