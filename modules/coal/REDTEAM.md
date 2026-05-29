# REDTEAM — coal v0.1.0

Adversarial audit of SPEC.md, performed **before** build. Anti-pompom.

| # | Severity | Objection | Required resolution | Status |
|---|----------|-----------|---------------------|--------|
| 1 | **blocker** | Using equity prices (PTBA/ADRO/ITMG) as if they were the coal price is a category error — they carry equity beta and company-specifics. | They must be flagged `is_proxy` and labelled "sentiment proxy, NOT coal price" everywhere they surface. | ✅ `is_proxy=True`, PROXY badge in render, notes + §8. |
| 2 | **blocker** | `api2_fut` wired to `MTF=F` without confirming the ticker maps to the API2/Newcastle future — risk of fetching the wrong instrument confidently. | Mark PROXY/candidate, STALE-safe if wrong, PENDING validation. | ✅ `is_proxy`, note, PENDING item. |
| 3 | **major** | Stale regulatory knowledge: HBA cadence/role. | Confirm current rule. Architect: since Mar-2025 HBA is **twice-monthly & mandatory export reference** (Permen ESDM). | ✅ §2/§9 updated. |
| 4 | **major** | Calorific-basis trap: ICI is GAR, API5 is NAR — comparing levels across bases is wrong. | Keep basis in each label; never cross-compare as equal. | ✅ §7 + labels. |
| 5 | **major** | ICI/API5/HBA presented as if monitorable when they're paywalled/PDF — implies coverage we lack. | Classify `UNKNOWN`, honest notes; surface the gap as a limitation. | ✅ `fetchers=None`, §8. |
| 6 | minor | "DMO caps cost" needs the mechanism, else it's a slogan. | State the USD70/t PLN cap and where the merchant/IPP exposure lands. | ✅ §3 notes. |
| 7 | minor | Regime zones on a proxy future risk implying we track the real price. | Label PROVISIONAL + proxy-based; PENDING calibration. | ✅ §6 + PENDING. |

**Verdict: CLEARED WITH CONDITIONS.** Build approved. The domain is honestly
"price mostly UNKNOWN + labelled equity proxies" in Fase 0 — that is the correct,
non-hallucinating representation. Conditions #2 (ticker validation) and #7
(threshold calibration) are carried in `PENDING_REVISIONS`.
