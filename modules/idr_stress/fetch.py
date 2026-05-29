"""idr_stress v0.1.0 — IDR / rates / external-balance stress complex.

Cross-cutting FX & rates module: it touches almost every IHSG sector through
the currency, the discount rate and capital flows. See SPEC.md for the full
methodology. This file is the machine-readable contract + the fetchers.

Free-first sourcing reality for this domain:
  * USD/IDR spot and DXY are cleanly available free (Yahoo) -> wired.
  * SBN 10y yield and FX reserves have free OECD/IMF monthly proxies on FRED
    (needs FRED_API_KEY) -> wired as PROXY, validate series ids.
  * BI-Rate, foreign SBN ownership, 5y CDS, current account, 1m NDF have no
    free programmatic feed (policy PDFs / DJPPR scrape / paywalled curves) ->
    left as UNKNOWN until a scraper or manual entry is approved (PENDING).
"""

from __future__ import annotations

from mmm.observation import Indicator, LEADING, COINCIDENT, LAGGING
from mmm.contract import Module, SectorImpact
from mmm.sources import yahoo_last_close, fred_series

INDICATORS = [
    Indicator(
        id="usdidr", label="USD/IDR spot", classification=COINCIDENT, cadence="daily",
        authority="aggregator", access="free_api", latency="T+0 (intraday delayed)",
        url="https://finance.yahoo.com/quote/IDR=X", unit="IDR/USD",
        bound_low=8000, bound_high=25000,
    ),
    Indicator(
        id="dxy", label="US Dollar Index (DXY)", classification=LEADING, cadence="daily",
        authority="aggregator", access="free_api", latency="T+0 (intraday delayed)",
        url="https://finance.yahoo.com/quote/DX-Y.NYB", unit="index",
        bound_low=70, bound_high=130,
        note="leading: USD strength front-runs EM-FX pressure",
    ),
    Indicator(
        id="sbn10y", label="Govt bond yield 10y (Indonesia)", classification=COINCIDENT,
        cadence="monthly", authority="independent", access="free_api",
        latency="monthly (OECD proxy)",
        url="https://fred.stlouisfed.org/series/IRLTLT01IDM156N", unit="%",
        bound_low=3, bound_high=15, is_proxy=True,
        note="PROXY: OECD monthly 10y yield via FRED. Intraday SBN/IBPA curve is "
             "paywalled. VALIDATE FRED series id during architect pass.",
    ),
    Indicator(
        id="reserves", label="FX reserves (Indonesia)", classification=LAGGING,
        cadence="monthly", authority="independent", access="free_api",
        latency="monthly +~7d (FRED/IMF proxy)",
        url="https://fred.stlouisfed.org/series/TRESEGIDM052N", unit="USD",
        bound_low=5e9, bound_high=5e11, is_proxy=True,
        note="PROXY: IMF/FRED total reserves ex-gold. Official source is BI press "
             "release. VALIDATE FRED series id.",
    ),
    Indicator(
        id="bi_rate", label="BI-Rate (policy rate)", classification=LEADING,
        cadence="monthly", authority="official", access="manual",
        latency="monthly (RDG BI)", url="https://www.bi.go.id/en/statistik/indikator/bi-rate.aspx",
        unit="%", bound_low=0, bound_high=20,
        note="No free API; set at monthly RDG, published as PDF/press release. "
             "UNKNOWN until manual entry or scraper approved (PENDING_REVISIONS).",
    ),
    Indicator(
        id="foreign_sbn", label="Foreign ownership of SBN", classification=LAGGING,
        cadence="daily", authority="official", access="scrape",
        latency="T+1 (DJPPR)", url="https://www.djppr.kemenkeu.go.id/", unit="IDR_tn",
        note="DJPPR table scrape; not wired in Fase 0 -> UNKNOWN.",
    ),
    Indicator(
        id="cds5y", label="Indonesia 5y CDS", classification=LEADING,
        cadence="daily", authority="independent", access="paywall",
        latency="T+0", url="https://www.worldgovernmentbonds.com/cds-historical-data/indonesia/5-years/",
        unit="bps", note="Paywalled/scrape-fragile -> UNKNOWN. No reliable free proxy wired.",
    ),
    Indicator(
        id="current_account", label="Current account balance", classification=LAGGING,
        cadence="quarterly", authority="official", access="manual",
        latency="quarterly +~45d", url="https://www.bi.go.id/en/statistik/ekonomi-keuangan/npi/",
        unit="%_GDP", bound_low=-10, bound_high=10,
        note="BI quarterly NPI release; manual -> UNKNOWN in Fase 0.",
    ),
    Indicator(
        id="ndf1m", label="USD/IDR 1m NDF", classification=LEADING,
        cadence="daily", authority="independent", access="paywall",
        latency="T+0", url="https://www.bi.go.id/", unit="IDR/USD",
        bound_low=8000, bound_high=25000,
        note="Offshore NDF curve is paywalled; no free proxy wired -> UNKNOWN.",
    ),
]

FETCHERS = {
    "usdidr": lambda: yahoo_last_close("IDR=X"),
    "dxy": lambda: yahoo_last_close("DX-Y.NYB"),
    "sbn10y": lambda: fred_series("IRLTLT01IDM156N"),
    "reserves": lambda: fred_series("TRESEGIDM052N"),
    "bi_rate": None,
    "foreign_sbn": None,
    "cds5y": None,
    "current_account": None,
    "ndf1m": None,
}

TRANSMISSION = [
    SectorImpact("G21", "Bank", "+/-", "FX/discount_rate",
                 ["BBRI", "BBCA", "BMRI", "BBNI"],
                 "Higher rates lift NIM but raise credit cost; IDR weakness pressures CAR via FX assets."),
    SectorImpact("H11", "Properti & real estate", "-", "discount_rate/cost",
                 ["BSDE", "CTRA", "SMRA"],
                 "Rate-sensitive demand; USD-linked construction inputs."),
    SectorImpact("A12", "Pertambangan batubara (eksportir)", "+", "FX/revenue",
                 ["ADRO", "PTBA", "ITMG"],
                 "USD revenue vs IDR cost: weak IDR is margin-positive for exporters."),
    SectorImpact("D21", "Makanan & minuman (importir bahan baku)", "-", "FX/cost",
                 ["INDF", "ICBP", "MYOR"],
                 "Imported wheat/dairy/sugar in USD: weak IDR raises COGS."),
    SectorImpact("K11", "Transportasi udara", "-", "FX/cost",
                 ["GIAA"], "USD fuel + lease + USD debt against IDR revenue."),
    SectorImpact("I11", "Teknologi", "-", "discount_rate",
                 ["GOTO", "BUKA"], "Long-duration growth names de-rate as discount rate rises."),
]

# Regime zones are STARTING POINTS for ~2025-2026 levels and need calibration.
# Redteam explicitly flags these as provisional (see REDTEAM.md).
def _usdidr_zone(v):
    if v < 16000:
        return "normal", "IDR orderly; no acute FX stress signal"
    if v < 16500:
        return "waspada", "IDR under pressure; watch BI intervention & reserves"
    return "stres", "Acute IDR weakness; FX-cost sectors at risk, importers squeezed"

def _dxy_zone(v):
    if v < 103:
        return "normal", "Broad USD soft; supportive of EM flows"
    if v < 107:
        return "waspada", "USD firming; EM-FX & SBN inflows at risk"
    return "stres", "Strong-USD regime; outflow pressure on IDR & SBN"

def _sbn10y_zone(v):
    if v < 6.8:
        return "normal", "Yields contained; equity discount rate manageable"
    if v < 7.5:
        return "waspada", "Yields rising; rate-sensitive sectors pressured"
    return "stres", "High yields; risk premium elevated, de-rating risk"

REGIME = {"usdidr": _usdidr_zone, "dxy": _dxy_zone, "sbn10y": _sbn10y_zone}

LIMITATIONS = [
    "BI-Rate, current account and 1m NDF are NOT auto-fetched in Fase 0 (no free "
    "API / paywall) — they show UNKNOWN, not a guess.",
    "sbn10y and reserves are OECD/IMF monthly PROXIES via FRED, not the intraday "
    "IBPA curve or BI's exact reserves release; FRED series ids must be validated.",
    "DXY ≠ USD/IDR: DXY excludes IDR; it is a leading driver, not a substitute.",
    "Foreign SBN ownership breakdown by holder type is not captured (DJPPR scrape "
    "not wired); DHE/DMO cash-flow effects sit outside any price index here.",
    "Regime thresholds are provisional starting points, not calibrated to a "
    "historical stress study — see PENDING_REVISIONS for the calibration task.",
]

MODULE = Module(
    id="idr_stress", version="0.1.0",
    domain="IDR / rates / external-balance stress",
    indicators=INDICATORS, fetchers=FETCHERS, transmission=TRANSMISSION,
    regime=REGIME, limitations=LIMITATIONS,
)
