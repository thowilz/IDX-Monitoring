"""Read/update ``registry.yaml`` — the catalogue of all MMM modules.

The orchestrator owns this file. ``run_refresh`` updates ``last_refresh`` and
``status`` for active modules after each run; everything else (planned domains,
target sector mapping) is authored by humans/architect and left untouched.
"""

from __future__ import annotations

import os
from typing import Optional

import yaml


def registry_path(root: str) -> str:
    return os.path.join(root, "registry.yaml")


def load_registry(root: str) -> dict:
    path = registry_path(root)
    with open(path) as fh:
        return yaml.safe_load(fh)


def save_registry(root: str, data: dict) -> None:
    path = registry_path(root)
    with open(path, "w") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True, width=100)


def active_modules(reg: dict) -> list:
    return [m for m in reg.get("modules", []) if m.get("status") == "active"]


def update_module(
    reg: dict,
    module_id: str,
    *,
    last_refresh: Optional[str] = None,
    last_summary: Optional[str] = None,
) -> None:
    for m in reg.get("modules", []):
        if m.get("id") == module_id:
            if last_refresh is not None:
                m["last_refresh"] = last_refresh
            if last_summary is not None:
                m["last_summary"] = last_summary
            return
    raise KeyError(f"module {module_id} not in registry")
