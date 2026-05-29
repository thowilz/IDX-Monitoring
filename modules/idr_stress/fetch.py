"""idr_stress v0.2.0 — IDR / rates / external-balance stress complex.

v0.2.0 adopts the standard analytics layer (ADR-009): manual-input channel,
derived metrics (implied PD, NDF basis, forward outright/funding), a weighted
composite score -> regime verdict, and an explicit signal hierarchy. The
methodology for the composite + NDF-basis + PD analytics is ported from the
user's hand-built "IDR Stress Monitor" artifact, but here the inputs carry
provenance (live fetch or manual-with-source) instead of being trusted blind.

Sourcing reality:
  * USD/IDR spot and DXY are free (Yahoo) -> wired live.
  * SBN 10y yield and FX reserves: OECD/IMF monthly proxies via FRED (key needed).
  * CDS level + 1m/6m momentum, onshore forward points, offshore NDF points, USD
    funding rate, BI-Rate: paywalled/PDF -> MANUAL channel (data/manual_inputs.yaml),
    each with its own source + ts. Absent -> UNKNOWN (never guessed).
"""

from __future__ import annotations

from mmm.observation import Indicator, LEADING, COINCIDENT, LAGGING
from mmm.contract import Module, SectorImpact, DerivedMetric
from mmm.sources import yahoo_last_close, fred_series

# --- base indicators --------------------------------------------------------
INDICATORS = [
    Indicator(id="usdidr", label="USD/IDR spot", classification=COINCIDENT, cadence="daily",
              authority="aggregator", access="free_api", latency="T+0 (delayed)",
              url="https://finance.yahoo.com/quote/IDR=X", unit="IDR/USD",
              bound_low=8000, bound_high=25000),
    Indicator(id="dxy", label="US Dollar Index (DXY)", classification=LEADING, cadence="daily",
              authority="aggregator", access="free_api", latency="T+0 (delayed)",
              url="https://finance.yahoo.com/quote/DX-Y.NYB", unit="index",
              bound_low=70, bound_high=130,
              note="leading: USD strength front-runs EM-FX pressure"),
    Indicator(id="sbn10y", label="Govt bond yield 10y (Indonesia)", classification=COINCIDENT,
              cadence="monthly", authority="independent", access="free_api",
              latency="monthly (OECD proxy)",
              url="https://fred.stlouisfed.org/series/IRLTLT01IDM156N", unit="%",
              bound_low=3, bound_high=15, is_proxy=True,
              note="PROXY: OECD monthly 10y via FRED — validate series id."),
    Indicator(id="reserves", label="FX reserves (Indonesia)", classification=LAGGING,
              cadence="monthly", authority="independent", access="free_api",
              latency="monthly +~7d", url="https://fred.stlouisfed.org/series/TRESEGIDM052N",
              unit="USD", bound_low=5e9, bound_high=5e11, is_proxy=True,
              note="PROXY: IMF/FRED total reserves ex-gold — validate series id."),
    Indicator(id="bi_rate", label="BI-Rate (policy rate)", classification=LEADING,
              cadence="monthly", authority="official", access="manual",
              latency="monthly (RDG BI)", url="https://www.bi.go.id/en/statistik/indikator/bi-rate.aspx",
              unit="%", bound_low=0, bound_high=20, note="manual entry from RDG BI."),
    Indicator(id="usd_rate", label="USD funding rate (1m)", classification=LEADING,
              cadence="weekly", authority="aggregator", access="manual", latency="manual",
              url="https://www.global-rates.com/", unit="%", bound_low=0, bound_high=15,
              note="USD leg for implied-funding calc; manual."),
    Indicator(id="fwd_1m", label="Onshore forward points 1M", classification=LEADING,
              cadence="daily", authority="independent", access="manual", latency="manual",
              url="https://www.bi.go.id/", unit="Rp_pts", bound_low=-2000, bound_high=8000,
              note="Interbank onshore 1M forward points; manual."),
    Indicator(id="ndf1m", label="Offshore NDF points 1M", classification=LEADING,
              cadence="daily", authority="independent", access="manual", latency="manual",
              url="https://www.factset.com/", unit="Rp_pts", bound_low=-2000, bound_high=8000,
              note="Offshore 1M NDF points (vs onshore -> basis). Paywall -> manual."),
    Indicator(id="cds5y", label="Indonesia 5y CDS — level", classification=LEADING,
              cadence="daily", authority="independent", access="manual", latency="EOD",
              url="https://www.worldgovernmentbonds.com/cds-historical-data/indonesia/5-years/",
              unit="bps", bound_low=20, bound_high=600, note="manual (EOD), drives implied PD."),
    Indicator(id="cds_var1m", label="CDS 5y — Var 1m (momentum)", classification=LEADING,
              cadence="weekly", authority="independent", access="manual", latency="EOD",
              url="https://www.worldgovernmentbonds.com/", unit="%", bound_low=-100, bound_high=100,
              note="negative = tightening (risk easing); timing signal."),
    Indicator(id="cds_var6m", label="CDS 5y — Var 6m (structural)", classification=LEADING,
              cadence="weekly", authority="independent", access="manual", latency="EOD",
              url="https://www.worldgovernmentbonds.com/", unit="%", bound_low=-100, bound_high=200,
              note="structural risk direction over 6 months."),
    Indicator(id="foreign_sbn", label="Foreign ownership of SBN", classification=LAGGING,
              cadence="daily", authority="official", access="scrape", latency="T+1",
              url="https://www.djppr.kemenkeu.go.id/", unit="IDR_tn",
              note="DJPPR scrape; not wired -> UNKNOWN unless manual."),
    Indicator(id="current_account", label="Current account balance", classification=LAGGING,
              cadence="quarterly", authority="official", access="manual", latency="quarterly +~45d",
              url="https://www.bi.go.id/en/statistik/ekonomi-keuangan/npi/", unit="%_GDP",
              bound_low=-10, bound_high=10, note="BI quarterly NPI; manual."),
]

FETCHERS = {
    "usdidr": lambda: yahoo_last_close("IDR=X"),
    "dxy": lambda: yahoo_last_close("DX-Y.NYB"),
    "sbn10y": lambda: fred_series("IRLTLT01IDM156N"),
    "reserves": lambda: fred_series("TRESEGIDM052N"),
    # everything below has no free feed -> manual channel or UNKNOWN
    "bi_rate": None, "usd_rate": None, "fwd_1m": None, "ndf1m": None,
    "cds5y": None, "cds_var1m": None, "cds_var6m": None,
    "foreign_sbn": None, "current_account": None,
}

# --- derived metrics (computed, not fetched) --------------------------------
def _implied_pd(v):
    if "cds5y" not in v:
        return None
    return v["cds5y"] / 10000 / 0.6 * 100, "PD = CDS/(1-recovery 40%)"

def _fwd_outright(v):
    if "usdidr" in v and "fwd_1m" in v:
        return v["usdidr"] + v["fwd_1m"], "spot + onshore 1M points"
    return None

def _implied_funding(v):
    if "usdidr" in v and "fwd_1m" in v and "usd_rate" in v:
        prem = (v["fwd_1m"] / v["usdidr"]) * 12 * 100
        return v["usd_rate"] + prem, f"USD {v['usd_rate']:.2f}% + fwd premi {prem:.2f}%"
    return None

def _ndf_basis_pts(v):
    if "ndf1m" in v and "fwd_1m" in v:
        return v["ndf1m"] - v["fwd_1m"], "offshore - onshore (1M points)"
    return None

def _ndf_basis_bps(v):
    if "ndf1m" in v and "fwd_1m" in v and "usdidr" in v:
        return (v["ndf1m"] - v["fwd_1m"]) / v["usdidr"] / (1 / 12) * 10000, "annualised"
    return None

DERIVED = [
    DerivedMetric("implied_pd", "Implied PD (recovery 40%)", "%", _implied_pd, LEADING),
    DerivedMetric("fwd_outright_1m", "Forward outright 1M", "IDR/USD", _fwd_outright, COINCIDENT),
    DerivedMetric("implied_funding_1m", "Implied IDR funding 1M", "%", _implied_funding, COINCIDENT),
    DerivedMetric("ndf_basis_1m", "NDF basis 1M (offshore-onshore)", "Rp_pts", _ndf_basis_pts, LEADING,
                  note="speculative-pressure thermometer: positive & widening = stress"),
    DerivedMetric("ndf_basis_1m_bps", "NDF basis 1M", "bps p.a.", _ndf_basis_bps, LEADING),
]

# --- composite score (ported from the artifact, ±7) -------------------------
def _composite(values, prev):
    score = 0
    comps = []

    def add(label, contrib, cls):
        comps.append({"label": label, "contribution": contrib, "cls": cls})

    if "cds_var1m" in values:
        s = 2 if values["cds_var1m"] < 0 else -2
        score += s; add("CDS Var 1m (momentum) ×2", f"{s:+d}", "pos" if s > 0 else "neg")
    else:
        add("CDS Var 1m ×2", "n/a", "neu")

    if "cds_var6m" in values:
        s = 1 if values["cds_var6m"] < 0 else -1
        score += s; add("CDS Var 6m (structural)", f"{s:+d}", "pos" if s > 0 else "neg")
    else:
        add("CDS Var 6m", "n/a", "neu")

    if "ndf_basis_1m" in values:
        b = values["ndf_basis_1m"]
        s = 2 if b <= 0 else (-2 if b > 50 else 0)
        score += s; add("NDF basis 1M ×2", f"{s:+d}", "pos" if s > 0 else ("neg" if s < 0 else "neu"))
    else:
        add("NDF basis 1M ×2", "n/a (need offshore NDF)", "neu")

    if "usdidr" in values and "usdidr" in prev:
        s = 1 if values["usdidr"] < prev["usdidr"] else (-1 if values["usdidr"] > prev["usdidr"] else 0)
        score += s; add("Spot momentum vs last", f"{s:+d}", "pos" if s > 0 else ("neg" if s < 0 else "neu"))
    else:
        add("Spot momentum vs last", "n/a (need history)", "neu")

    if "fwd_1m" in values and "fwd_1m" in prev:
        s = 1 if values["fwd_1m"] < prev["fwd_1m"] else (-1 if values["fwd_1m"] > prev["fwd_1m"] else 0)
        score += s; add("Forward points 1M vs last", f"{s:+d}", "pos" if s > 0 else ("neg" if s < 0 else "neu"))
    else:
        add("Forward points 1M vs last", "n/a (need history)", "neu")

    if score >= 3:
        verdict, vclass, sub = "EASING", "pos", "Reversal signals forming — risk easing."
    elif score >= 1:
        verdict, vclass, sub = "MIXED — leaning better", "neu", "Some positives, not solid yet."
    elif score >= -1:
        verdict, vclass, sub = "MIXED — leaning stress", "neu", "Pressure still dominant."
    else:
        verdict, vclass, sub = "STRESS", "neg", "No reversal yet — treat FX bounce as technical/intervention."

    return {"score": score, "max": 7, "verdict": verdict, "verdict_class": vclass,
            "subtitle": sub, "components": comps}

SIGNAL_HIERARCHY = [
    "DXY softens (broad USD turns)",
    "CDS Var 1m turns negative (risk premium tightening)",
    "NDF basis narrows toward / below zero (offshore pressure fades)",
    "Foreign flow returns to equities/SBN",
    "FX reserves stop falling",
    "THEN USD/IDR strengthens and holds — confirmed reversal",
    "⚠ If spot strengthens but CDS Var & basis have NOT turned → technical bounce / intervention, not a reversal",
]

TRANSMISSION = [
    SectorImpact("G21", "Bank", "+/-", "FX/discount_rate", ["BBRI", "BBCA", "BMRI", "BBNI"],
                 "Higher rates lift NIM but raise credit cost; IDR weakness pressures FX-asset CAR."),
    SectorImpact("H11", "Properti & real estate", "-", "discount_rate/cost", ["BSDE", "CTRA", "SMRA"],
                 "Rate-sensitive demand; USD-linked construction inputs."),
    SectorImpact("A12", "Pertambangan batubara (eksportir)", "+", "FX/revenue", ["ADRO", "PTBA", "ITMG"],
                 "USD revenue vs IDR cost: weak IDR is margin-positive."),
    SectorImpact("D21", "Makanan & minuman (importir)", "-", "FX/cost", ["INDF", "ICBP", "MYOR"],
                 "Imported USD inputs: weak IDR raises COGS."),
    SectorImpact("K11", "Transportasi udara", "-", "FX/cost", ["GIAA"],
                 "USD fuel + lease + USD debt vs IDR revenue."),
    SectorImpact("I11", "Teknologi (growth)", "-", "discount_rate", ["GOTO", "BUKA"],
                 "Long-duration names de-rate as discount rate rises."),
]

def _usdidr_zone(v):
    if v < 16000:
        return "normal", "IDR orderly"
    if v < 16500:
        return "waspada", "IDR under pressure; watch intervention & reserves"
    return "stres", "Acute IDR weakness (threshold PROVISIONAL — calibrate)"

def _dxy_zone(v):
    if v < 103: return "normal", "Broad USD soft; supportive of EM flows"
    if v < 107: return "waspada", "USD firming; EM-FX & SBN inflows at risk"
    return "stres", "Strong-USD regime; outflow pressure"

def _sbn10y_zone(v):
    if v < 6.8: return "normal", "Yields contained"
    if v < 7.5: return "waspada", "Yields rising; rate-sensitive sectors pressured"
    return "stres", "High yields; de-rating risk"

REGIME = {"usdidr": _usdidr_zone, "dxy": _dxy_zone, "sbn10y": _sbn10y_zone}

LIMITATIONS = [
    "CDS, NDF, forward points, USD rate, BI-Rate, current account come via MANUAL "
    "channel (data/manual_inputs.yaml) — each carries source+ts; if absent they are "
    "UNKNOWN and the composite degrades gracefully (component = n/a).",
    "NDF basis needs BOTH offshore NDF and onshore forward points; without offshore "
    "NDF the basis (the speculative thermometer) is not computed — not faked.",
    "sbn10y/reserves are OECD/IMF monthly PROXIES via FRED; series ids to validate.",
    "Composite weights & regime thresholds are PROVISIONAL (ported from the artifact) "
    "— calibration is a PENDING item before they should drive decisions.",
    "Spot/forward momentum needs ≥2 stored snapshots; first run shows n/a.",
    "No holder-type breakdown of foreign SBN; DHE/DMO cash effects sit outside index.",
]

MODULE = Module(
    id="idr_stress", version="0.2.0",
    domain="IDR / rates / external-balance stress",
    indicators=INDICATORS, fetchers=FETCHERS, transmission=TRANSMISSION,
    regime=REGIME, limitations=LIMITATIONS,
    derived=DERIVED, composite=_composite, signal_hierarchy=SIGNAL_HIERARCHY,
)
