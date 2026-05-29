"""coal v0.1.0 — thermal coal complex (export revenue + PLN cost).

The honest reality of this domain, surfaced rather than hidden:
the authoritative price marks (ICI by Argus, API5/API2 indices, and the
official HBA reference) are PAYWALLED or PDF-only. So in Fase 0 the *coal
prices themselves are mostly UNKNOWN*, and what we CAN fetch free are
Indonesian coal-miner equities as a same-day PROXY for price/demand sentiment
— clearly labelled as a proxy, never presented as the coal price.

Regulatory note baked into the spec: since Mar-2025 the HBA is published TWICE
monthly and is mandatory as the export reference price (Permen ESDM) — the
architect must keep this current (regulations change).
"""

from __future__ import annotations

from mmm.observation import Indicator, LEADING, COINCIDENT, LAGGING
from mmm.contract import Module, SectorImpact
from mmm.sources import yahoo_last_close

INDICATORS = [
    Indicator(
        id="api2_fut", label="API2/Newcastle coal future (candidate)", classification=LEADING,
        cadence="daily", authority="aggregator", access="free_api",
        latency="T+0", url="https://finance.yahoo.com/quote/MTF=F", unit="USD/t",
        bound_low=20, bound_high=600, is_proxy=True,
        note="PROXY: candidate ICE coal future ticker on Yahoo — VALIDATE/replace "
             "during architect pass; STALE-safe if the ticker is wrong.",
    ),
    Indicator(
        id="ici4", label="Indonesian Coal Index (ICI-4, ~4200 GAR)", classification=COINCIDENT,
        cadence="weekly", authority="independent", access="paywall",
        latency="weekly", url="https://www.coalindo.co.id/", unit="USD/t",
        bound_low=20, bound_high=300,
        note="Argus/Coalindo paywall -> UNKNOWN. No clean free proxy for the index level.",
    ),
    Indicator(
        id="api5", label="API5 (5500 kcal NAR) marker", classification=COINCIDENT,
        cadence="weekly", authority="independent", access="paywall",
        latency="weekly", url="https://www.argusmedia.com/en/coal", unit="USD/t",
        bound_low=20, bound_high=400, note="Argus paywall -> UNKNOWN.",
    ),
    Indicator(
        id="hba", label="Harga Batubara Acuan (HBA, official)", classification=LAGGING,
        cadence="biweekly", authority="official", access="scrape",
        latency="twice-monthly", url="https://www.minerba.esdm.go.id/harga_acuan",
        unit="USD/t", bound_low=20, bound_high=400,
        note="Official reference. Since Mar-2025: published 2x/month & mandatory "
             "export reference (Permen ESDM). ESDM scrape not wired in Fase 0 -> UNKNOWN.",
    ),
    Indicator(
        id="ptba_px", label="PTBA share price (proxy)", classification=COINCIDENT,
        cadence="daily", authority="aggregator", access="free_api", latency="T+0",
        url="https://finance.yahoo.com/quote/PTBA.JK", unit="IDR", is_proxy=True,
        bound_low=100, bound_high=10000,
        note="PROXY for domestic coal sentiment, NOT the coal price.",
    ),
    Indicator(
        id="adro_px", label="ADRO share price (proxy)", classification=COINCIDENT,
        cadence="daily", authority="aggregator", access="free_api", latency="T+0",
        url="https://finance.yahoo.com/quote/ADRO.JK", unit="IDR", is_proxy=True,
        bound_low=100, bound_high=10000,
        note="PROXY for coal export sentiment, NOT the coal price.",
    ),
    Indicator(
        id="itmg_px", label="ITMG share price (proxy)", classification=COINCIDENT,
        cadence="daily", authority="aggregator", access="free_api", latency="T+0",
        url="https://finance.yahoo.com/quote/ITMG.JK", unit="IDR", is_proxy=True,
        bound_low=1000, bound_high=60000,
        note="PROXY for coal export sentiment, NOT the coal price.",
    ),
]

FETCHERS = {
    "api2_fut": lambda: yahoo_last_close("MTF=F"),
    "ici4": None,
    "api5": None,
    "hba": None,
    "ptba_px": lambda: yahoo_last_close("PTBA.JK"),
    "adro_px": lambda: yahoo_last_close("ADRO.JK"),
    "itmg_px": lambda: yahoo_last_close("ITMG.JK"),
}

TRANSMISSION = [
    SectorImpact("A12", "Pertambangan batubara", "+", "revenue/royalti",
                 ["ADRO", "PTBA", "ITMG", "HRUM", "INDY"],
                 "Higher coal price lifts revenue; royalty (PNBP) scales with HBA."),
    SectorImpact("J41", "Listrik (PLN / IPP)", "-", "cost",
                 ["POWR"], "Coal is the dominant PLN fuel; DMO caps domestic cost at "
                 "USD70/t but global spikes squeeze IPP merchant exposure."),
    SectorImpact("D11", "Semen (kiln fuel)", "-", "cost",
                 ["SMGR", "INTP"], "Coal is a major kiln energy input; price up = cost up."),
    SectorImpact("K21", "Pelayaran / angkutan curah", "+", "demand",
                 ["TOBA", "MBSS"], "Higher coal volumes/price support bulk freight demand."),
]

# Regime on the proxy future only — flagged as provisional & proxy-based.
def _api2_zone(v):
    if v < 90:
        return "normal", "Thermal coal soft; exporter margins thin, PLN cost benign"
    if v < 130:
        return "waspada", "Coal firming; exporter margins improving, watch PLN cost"
    return "stres", "Coal spike; exporters benefit, PLN/cement cost pressure rises"

REGIME = {"api2_fut": _api2_zone}

LIMITATIONS = [
    "The authoritative coal price marks (ICI, API5, API2 index, official HBA) are "
    "PAYWALLED or PDF-only — in Fase 0 they are UNKNOWN, not estimated.",
    "Equity proxies (PTBA/ADRO/ITMG) move with coal sentiment but also with "
    "equity beta, DMO policy and company-specifics — they are NOT the coal price.",
    "DMO (domestic market obligation) and DHE export-proceeds rules change the "
    "cash economics independently of the headline price and are not modelled.",
    "The api2_fut Yahoo ticker is an unvalidated candidate; if wrong it stays "
    "STALE (safe) until the architect wires a confirmed free source.",
    "Regime thresholds are provisional and proxy-based — calibration is a "
    "PENDING_REVISIONS task before they should drive any signal.",
]

MODULE = Module(
    id="coal", version="0.1.0", domain="Thermal coal (export revenue + PLN cost)",
    indicators=INDICATORS, fetchers=FETCHERS, transmission=TRANSMISSION,
    regime=REGIME, limitations=LIMITATIONS,
)
