"""Manual-input channel — human-entered values WITH provenance.

The honest answer to paywalled indicators (CDS, NDF, onshore forward points):
let a human paste the number, but require it to carry a ``source`` and a ``ts``
just like an auto-fetched value. That keeps PRINSIP INTI #3 intact — every
number is traceable to a source + timestamp — while unlocking the analytics
(composite score, NDF basis) that need these inputs.

File: ``data/manual_inputs.yaml``
    <module_id>:
      <indicator_id>:
        value: 90.48
        ts: "2026-05-28"
        source: "worldgovernmentbonds.com/cds/indonesia"
        note: "EOD"

Indicators with no manual entry (and no free fetcher) stay UNKNOWN.
"""

from __future__ import annotations

import os
from typing import Dict

import yaml


def _path(root: str) -> str:
    return os.path.join(root, "data", "manual_inputs.yaml")


def load_manual(root: str) -> Dict[str, Dict[str, dict]]:
    path = _path(root)
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        data = yaml.safe_load(fh) or {}
    # normalise: drop the optional top-level "_meta" / comments keys
    return {k: v for k, v in data.items()
            if isinstance(v, dict) and not k.startswith("_")}


def for_module(manual: Dict[str, Dict[str, dict]], module_id: str) -> Dict[str, dict]:
    return manual.get(module_id, {}) or {}
