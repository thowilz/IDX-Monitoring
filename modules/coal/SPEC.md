# SPEC — coal

> Authored by `architect`, audited by `redteam` (see REDTEAM.md), implemented by
> `data_engineer` in `fetch.py`. Engineering monitor — not investment advice.

## 1. Domain & version
**Domain:** Thermal coal complex — drives exporter revenue (USD) and PLN/cement
energy cost. **Version:** `coal` v0.1.0.

## 2. Lead–lag chain
| Indicator | Class | Why |
|-----------|-------|-----|
| `api2_fut` (API2/Newcastle future) | LEADING | Futures price forward expectations. |
| `ici4` (Indonesian Coal Index ~4200 GAR) | COINCIDENT | Transacted Indonesian grade now. |
| `api5` (5500 NAR marker) | COINCIDENT | Transacted higher-CV marker now. |
| `hba` (Harga Batubara Acuan) | LAGGING | Official reference; administrative confirmation. |
| `ptba_px`/`adro_px`/`itmg_px` (equities) | COINCIDENT | Same-day market read on coal names (PROXY). |

**Chain:** futures (leading) → spot indices ICI/API5 (coincident) → official HBA
(lagging; set from a trailing average of indices). Since **Mar-2025 the HBA is
published twice monthly and is the mandatory export reference price** (Permen
ESDM) — so the HBA lag tightened from monthly to ~2 weeks. Equity proxies move
intraday and are coincident sentiment, not the coal price.

## 3. Transmission map → IHSG
| Industri | Sektor | Arah | Mekanisme | Emiten sensitif |
|----------|--------|------|-----------|-----------------|
| A12 | Pertambangan batubara | + | revenue / royalti | ADRO, PTBA, ITMG, HRUM, INDY |
| J41 | Listrik (PLN / IPP) | − | cost | POWR |
| D11 | Semen (kiln fuel) | − | cost | SMGR, INTP |
| K21 | Pelayaran / angkutan curah | + | demand | TOBA, MBSS |

Mechanism notes: higher coal price lifts miner revenue and royalty (PNBP scales
with HBA); it raises PLN/IPP and cement kiln cost; DMO caps the domestic price
to PLN at USD70/t, so the cost hit lands on merchant/IPP exposure and exporters
keep the upside on volumes sold abroad.

## 4. Source tiering
| Indicator | authority | access | latency | source | wired? |
|-----------|-----------|--------|---------|--------|--------|
| `api2_fut` | aggregator | free_api | T+0 | Yahoo `MTF=F` | ⚠️ PROXY — candidate ticker, validate |
| `ici4` | independent | paywall | weekly | Coalindo/Argus | ❌ UNKNOWN |
| `api5` | independent | paywall | weekly | Argus | ❌ UNKNOWN |
| `hba` | official | scrape | twice-monthly | minerba.esdm.go.id | ❌ UNKNOWN (not wired) |
| `ptba_px` | aggregator | free_api | T+0 | Yahoo `PTBA.JK` | ✅ PROXY |
| `adro_px` | aggregator | free_api | T+0 | Yahoo `ADRO.JK` | ✅ PROXY |
| `itmg_px` | aggregator | free_api | T+0 | Yahoo `ITMG.JK` | ✅ PROXY |

**Honest reality of this domain:** the authoritative price marks (ICI, API5, the
official HBA) are paywalled or PDF-only. Fase 0 therefore has the *coal prices
themselves mostly UNKNOWN*, and the only free, reliable feeds are Indonesian
coal-miner **equities used as a sentiment proxy** — labelled PROXY, never
presented as the coal price.

## 5. Cadence
`api2_fut`, `ptba_px`, `adro_px`, `itmg_px` daily · `ici4`, `api5` weekly ·
`hba` biweekly (twice-monthly).

## 6. Regime & thresholds (PROVISIONAL — see PENDING_REVISIONS)
On the (proxy) `api2_fut` only, until a real price feed is wired:
- **normal** <90 USD/t · **waspada** 90–130 · **stres** >130.
Meaning: <90 thin exporter margins & benign PLN cost; 90–130 improving exporter
margins; >130 exporters benefit but PLN/cement cost pressure rises. Proxy-based
and uncalibrated — must not drive a signal until calibrated.

## 7. Verification protocol
- Bounds: coal markers 20–600 USD/t; equity proxies in plausible IDR ranges.
  Out-of-bound → `SUSPECT`, value dropped.
- **Calorific-basis unit trap:** ICI grades are GAR, API5 is NAR — never compare
  across bases as if equal; keep each indicator's basis in its label.
- Currency: coal markers USD/t; equity proxies IDR — never mix.
- When ICI/HBA are wired, cross-check HBA against a trailing average of the spot
  indices (HBA is derived from them).

## 7b. Manual-input channel
ICI/API5/HBA are paywall/PDF — enter them in `data/manual_inputs.yaml` (value +
ts + source) when you have marks; otherwise UNKNOWN. No derived metrics are
defined yet (real coal prices are mostly UNKNOWN in Fase 0).

## 7c. Composite score & verdict (±4, PROXY-based, PROVISIONAL)
A "coal-miner tailwind" read built from PROXIES (real coal price is UNKNOWN):
| Component | Rule | Weight |
|-----------|------|--------|
| Coal price momentum (api2 proxy) vs last | up → +2, down → −2 | ×2 |
| Miner-equity breadth (PTBA/ADRO/ITMG ↑ vs ↓) | net, capped ±2 | ×1 |

Verdict: ≥2 **MINER TAILWIND** · ≥0 **NEUTRAL** · else **MINER HEADWIND**.
Explicitly proxy-based — equity proxies ≠ coal price.

## 7d. Signal hierarchy
API2/Newcastle futures turn (leading) → ICI/API5 spot follow (coincident) →
official HBA confirms ~2 weeks later (lagging, twice-monthly since Mar-2025) →
miner equities re-rate (royalty/PNBP scales with HBA). **Caveat:** equity proxies
also move on beta, DMO policy and company specifics — not coal price alone.

## 8. Limitations
- ICI, API5 and the official HBA are paywalled/PDF-only → `UNKNOWN` in Fase 0;
  no estimate is substituted.
- Equity proxies carry equity beta, DMO policy and company-specifics — they are
  **not** the coal price.
- DMO and DHE export-proceeds rules change the cash economics independently of
  the headline price and are not modelled.
- `api2_fut` Yahoo ticker is an unvalidated candidate; STALE-safe if wrong.
- Regime thresholds are provisional and proxy-based.

## 9. Changelog
- **v0.2.0 (2026-05-29)** — adopted v0.2 standard (ADR-009): ±4 proxy-based
  "miner tailwind" composite + signal hierarchy. Manual channel available for
  ICI/API5/HBA. No derived metrics yet (coal prices mostly UNKNOWN in Fase 0).
- **v0.1.0 (2026-05-29)** — initial module: 7 indicators (3 equity proxies wired,
  1 candidate future proxy, 3 paywalled UNKNOWN), transmission map (4 industries),
  provisional proxy-based regime. Captures the Mar-2025 HBA regulatory change.
