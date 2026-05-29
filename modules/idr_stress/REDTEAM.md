# REDTEAM — idr_stress v0.1.0

Adversarial audit of SPEC.md, performed **before** build. Anti-pompom.

| # | Severity | Objection | Required resolution | Status |
|---|----------|-----------|---------------------|--------|
| 1 | **blocker** | Regime thresholds (USD/IDR 16,000/16,500 etc.) have no stated calibration basis — "threshold tanpa dasar". | Either calibrate against a documented stress window or label PROVISIONAL + open a PENDING calibration item. | ✅ downgraded: labelled PROVISIONAL in §6, PENDING item filed. |
| 2 | **major** | `sbn10y` and `reserves` wired to FRED series ids that were not verified to exist/represent the claim — risk of confidently fetching the *wrong* series. | Mark `is_proxy`, note "validate series id", and keep STALE-safe if absent. Add PENDING validation. | ✅ done (`is_proxy=True`, notes, PENDING). |
| 3 | **major** | Calling `dxy` a substitute for IDR pressure would be wrong — DXY has **no IDR weight**. | State explicitly DXY is a *leading driver*, not a proxy for USD/IDR. | ✅ §8 + indicator note. |
| 4 | **major** | `cds5y`, `ndf1m` look authoritative but are paywalled; presenting them without data risks implying coverage we don't have. | Classify `UNKNOWN` with honest notes; do not fake a proxy. | ✅ `fetchers=None`, UNKNOWN. |
| 5 | minor | `bi_rate` classified LEADING — defensible (policy sets the path) but it is also administratively *announced*; ensure it's not read as a real-time market lead. | Keep LEADING, note it's a monthly policy decision (RDG). | ✅ note added. |
| 6 | minor | Reserves unit trap: USD absolute vs "months of imports". | Bound in USD absolute; limitation noted. | ✅ §7/§8. |
| 7 | minor | Bank impact is "+/−" — risks being a non-statement. | Spell out the opposing mechanisms (NIM vs credit cost / FX CAR). | ✅ §3 mechanism notes. |

**Verdict: CLEARED WITH CONDITIONS.** Build approved. Conditions #1 and #2 are
carried as `PENDING_REVISIONS` items (threshold calibration; FRED id validation)
and as explicit `LIMITATIONS`. No fabricated data may be introduced to satisfy
any reviewer.
