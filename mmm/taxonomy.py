"""Loader for the IHSG sector/industry taxonomy catalogue.

The user drops ``data/taxonomy_catalog_baseline.xlsx`` (columns at least
``sektor``, ``industri``, ``kode_emiten``). We also accept a ``.csv`` of the
same shape so the system can run before the official workbook is in place.

This is used to *validate* module transmission maps (do the industry codes a
module claims actually exist? are claimed emiten in the right industry?). If the
file is absent we return an empty catalogue and callers degrade gracefully —
they never invent a mapping.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class TaxonomyRow:
    sektor: str
    industri: str
    kode_emiten: str


class Taxonomy:
    def __init__(self, rows: List[TaxonomyRow], source: str):
        self.rows = rows
        self.source = source

    @property
    def available(self) -> bool:
        return bool(self.rows)

    def industries(self) -> set:
        return {r.industri for r in self.rows if r.industri}

    def emiten_for_industry(self, industri: str) -> List[str]:
        return [r.kode_emiten for r in self.rows if r.industri == industri]

    def has_industry(self, industri: str) -> bool:
        return industri in self.industries()


def _norm(s) -> str:
    return str(s).strip() if s is not None else ""


def load_taxonomy(root: str) -> Taxonomy:
    base = os.path.join(root, "data")
    xlsx = os.path.join(base, "taxonomy_catalog_baseline.xlsx")
    csv_real = os.path.join(base, "taxonomy_catalog_baseline.csv")
    csv_sample = os.path.join(base, "taxonomy_catalog_baseline.sample.csv")

    if os.path.exists(xlsx):
        return _load_xlsx(xlsx)
    for path in (csv_real, csv_sample):
        if os.path.exists(path):
            return _load_csv(path)
    return Taxonomy([], source="(none — taxonomy file not present)")


def _pick(headers, *candidates) -> Optional[str]:
    low = {h.lower(): h for h in headers if h}
    for c in candidates:
        if c in low:
            return low[c]
    return None


def _load_csv(path: str) -> Taxonomy:
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        headers = reader.fieldnames or []
        s = _pick(headers, "sektor", "sector")
        i = _pick(headers, "industri", "industry", "kode_industri")
        k = _pick(headers, "kode_emiten", "ticker", "emiten")
        rows = [
            TaxonomyRow(_norm(r.get(s)), _norm(r.get(i)), _norm(r.get(k)))
            for r in reader
        ]
    return Taxonomy(rows, source=path)


def _load_xlsx(path: str) -> Taxonomy:
    from openpyxl import load_workbook  # imported lazily; only dep needed for xlsx

    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    it = ws.iter_rows(values_only=True)
    headers = [(_norm(h)) for h in next(it)]
    s = _pick(headers, "sektor", "sector")
    i = _pick(headers, "industri", "industry", "kode_industri")
    k = _pick(headers, "kode_emiten", "ticker", "emiten")
    idx = {h: n for n, h in enumerate(headers)}
    rows = []
    for r in it:
        rows.append(TaxonomyRow(
            _norm(r[idx[s]]) if s else "",
            _norm(r[idx[i]]) if i else "",
            _norm(r[idx[k]]) if k else "",
        ))
    wb.close()
    return Taxonomy(rows, source=path)
