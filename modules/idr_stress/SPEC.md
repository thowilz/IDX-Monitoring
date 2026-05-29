# SPEC — idr_stress

> Authored by `architect`, audited by `redteam` (see REDTEAM.md), implemented by
> `data_engineer` in `fetch.py`. Engineering monitor — not investment advice.

## 1. Domain & version
**Domain:** IDR / rates / external-balance stress — the cross-cutting FX, rates
and capital-flow complex that transmits to nearly every IHSG sector.
**Version:** `idr_stress` v0.1.0.

## 2. Lead–lag chain
| Indicator | Class | Why |
|-----------|-------|-----|
| `bi_rate` (policy rate) | LEADING | Policy decision sets the path for the curve & IDR. |
| `dxy` (US Dollar Index) | LEADING | Broad-USD strength front-runs EM-FX pressure. |
| `cds5y` (sovereign CDS) | LEADING | Risk premium re-prices before spot/flows fully move. |
| `ndf1m` (1m NDF) | LEADING | Offshore expectations of future USD/IDR. |
| `usdidr` (spot) | COINCIDENT | The currency as it trades now. |
| `sbn10y` (10y govt yield) | COINCIDENT | Market-clearing cost of govt funding now. |
| `foreign_sbn` (foreign SBN holdings) | LAGGING | Settled flows, reported T+1. |
| `reserves` (FX reserves) | LAGGING | Monthly administrative confirmation. |
| `current_account` | LAGGING | Quarterly external-balance confirmation. |

**Chain:** DXY / BI-Rate / CDS / NDF (expectations) → **lead** → USD/IDR spot &
SBN 10y (coincident, ~days) → **lead** → foreign SBN holdings (T+1), reserves
(monthly) and current account (quarterly) as confirmation. Typical lag from a
DXY/CDS move to a reserves print: weeks to a full month.

## 3. Transmission map → IHSG
Industry codes per `data/taxonomy_catalog_baseline.xlsx`.

| Industri | Sektor | Arah | Mekanisme | Emiten sensitif |
|----------|--------|------|-----------|-----------------|
| G21 | Bank | +/− | FX / discount_rate | BBRI, BBCA, BMRI, BBNI |
| H11 | Properti & real estate | − | discount_rate / cost | BSDE, CTRA, SMRA |
| A12 | Pertambangan batubara (eksportir) | + | FX / revenue | ADRO, PTBA, ITMG |
| D21 | Makanan & minuman (importir bahan baku) | − | FX / cost | INDF, ICBP, MYOR |
| K11 | Transportasi udara | − | FX / cost | GIAA |
| I11 | Teknologi (growth) | − | discount_rate | GOTO, BUKA |

Mechanism notes: higher rates lift bank NIM but raise credit cost and pressure
FX-asset CAR; rate-sensitive property demand falls as the discount rate rises;
USD-revenue exporters *benefit* from a weak IDR; importers of USD inputs are
squeezed; long-duration tech de-rates as the discount rate rises.

## 4. Source tiering
| Indicator | authority | access | latency | source | wired? |
|-----------|-----------|--------|---------|--------|--------|
| `usdidr` | aggregator | free_api | T+0 (delayed) | Yahoo `IDR=X` | ✅ |
| `dxy` | aggregator | free_api | T+0 (delayed) | Yahoo `DX-Y.NYB` | ✅ |
| `sbn10y` | independent | free_api | monthly | FRED `IRLTLT01IDM156N` (OECD) | ⚠️ PROXY — validate id |
| `reserves` | independent | free_api | monthly +~7d | FRED `TRESEGIDM052N` (IMF) | ⚠️ PROXY — validate id |
| `bi_rate` | official | manual | monthly (RDG) | bi.go.id | ❌ UNKNOWN (PDF/press) |
| `foreign_sbn` | official | scrape | T+1 | djppr.kemenkeu.go.id | ❌ UNKNOWN (not wired) |
| `cds5y` | independent | paywall | T+0 | (paywalled) | ❌ UNKNOWN |
| `current_account` | official | manual | quarterly +~45d | bi.go.id NPI | ❌ UNKNOWN |
| `ndf1m` | independent | paywall | T+0 | (paywalled) | ❌ UNKNOWN |

Free + authoritative first. The intraday SBN/IBPA curve and the NDF curve are
paywalled; `sbn10y`/`reserves` use OECD/IMF **monthly proxies** via FRED and are
labelled as such. Indicators with no free feed are `UNKNOWN`, never faked.

## 5. Cadence
`usdidr`, `dxy` daily · `sbn10y`, `reserves`, `bi_rate` monthly · `foreign_sbn`
daily (when wired) · `cds5y`, `ndf1m` daily (when sourced) · `current_account`
quarterly.

## 6. Regime & thresholds (PROVISIONAL — see PENDING_REVISIONS)
Zones describe a *signal*, not a price target. Starting points only:
- `usdidr`: **normal** <16,000 · **waspada** 16,000–16,500 · **stres** >16,500.
- `dxy`: **normal** <103 · **waspada** 103–107 · **stres** >107.
- `sbn10y`: **normal** <6.8% · **waspada** 6.8–7.5% · **stres** >7.5%.

These are *not* calibrated to a historical stress study yet — calibration is a
PENDING item and the redteam flagged it (blocker downgraded to condition).

## 7. Verification protocol
- Sanity bounds per indicator (`bound_low/high` in `fetch.py`): USD/IDR
  8,000–25,000; DXY 70–130; yields 3–15%; reserves 5e9–5e11 USD. Out-of-bound →
  `SUSPECT`, value dropped.
- **Unit care:** yields are percent (e.g. 6.9), not decimal — `verify.py` can
  flag a 0–1 value where a percent is expected. Reserves: USD absolute, not
  "months of imports" — don't conflate.
- Cross-source: when a second USD/IDR feed is added, require agreement within 5%.

## 7b. Manual-input channel
Paywalled/PDF inputs are entered in `data/manual_inputs.yaml` with `value + ts +
source`: `cds5y`, `cds_var1m`, `cds_var6m`, `fwd_1m` (onshore forward points),
`ndf1m` (offshore NDF points), `usd_rate`, `bi_rate`, `current_account`. Each is
shown with `access=manual` + its source; absent entries stay UNKNOWN.

## 7c. Derived metrics (computed, not fetched)
- **implied_pd** = CDS / 10000 / (1 − 0.4 recovery) × 100  → needs `cds5y`.
- **fwd_outright_1m** = spot + onshore 1M points → needs `usdidr`, `fwd_1m`.
- **implied_funding_1m** = USD rate + (points/spot)×12×100 → `usd_rate`,`fwd_1m`,`usdidr`.
- **ndf_basis_1m** = offshore − onshore (1M points) → needs `ndf1m`, `fwd_1m`.
  *The speculative-pressure thermometer.* Also annualised to **ndf_basis_1m_bps**.

## 7d. Composite score & verdict (±7, PROVISIONAL)
Ported from the user's IDR Stress Monitor artifact:
| Component | Rule | Weight |
|-----------|------|--------|
| CDS Var 1m (momentum) | <0 → +2, else −2 | ×2 |
| CDS Var 6m (structural) | <0 → +1, else −1 | ×1 |
| NDF basis 1M | ≤0 → +2, >50pts → −2, else 0 | ×2 |
| Spot momentum vs last | strengthen → +1, weaken → −1 | ×1 |
| Forward points vs last | narrow → +1, widen → −1 | ×1 |

Verdict: ≥3 **EASING** · ≥1 **MIXED↑** · ≥−1 **MIXED↓** · else **STRESS**.

## 7e. Signal hierarchy (reversal sequence)
DXY softens → CDS Var 1m turns negative → NDF basis narrows → foreign flow
returns → reserves stop falling → THEN USD/IDR strengthens & holds. **Caveat:**
if spot strengthens but CDS Var & basis have *not* turned, treat as technical
bounce / intervention — not a reversal.

## 8. Limitations
- BI-Rate, current account and 1m NDF are not auto-fetched in Fase 0 → `UNKNOWN`.
- `sbn10y`/`reserves` are OECD/IMF **monthly proxies**, not the intraday IBPA
  curve or BI's exact reserves release; FRED ids must be validated.
- DXY excludes IDR — it's a driver, not a substitute for USD/IDR.
- No holder-type breakdown of foreign SBN; DHE/DMO cash-flow effects sit outside
  any price index here.
- Regime zones are provisional, not calibrated.

## 9. Changelog
- **v0.2.0 (2026-05-29)** — adopted v0.2 standard analytics (ADR-009): manual-input
  channel (CDS/NDF/forward/USD-rate/BI-rate), 5 derived metrics (implied PD, NDF
  basis pts+bps, forward outright, implied funding), ±7 composite score → verdict,
  and the signal hierarchy — all ported from the user's IDR Stress Monitor artifact
  but with provenance on every input. Added `usd_rate`, `fwd_1m`, `cds_var1m`,
  `cds_var6m`; `ndf1m` redefined as offshore points.
- **v0.1.0 (2026-05-29)** — initial module: 9 indicators (2 free-wired, 2 FRED
  proxies, 5 UNKNOWN), transmission map (6 industries), provisional regimes.
