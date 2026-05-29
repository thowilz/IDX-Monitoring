# PENDING_REVISIONS

Methodology / design changes proposed by the `watchdog` agent (or by a human)
that **await explicit approval before any SPEC.md or fetch.py is changed**.

Rule (PRINSIP INTI #5): *data* refresh is automatic; *design* changes are
human-gated. The watchdog appends proposals here under a dated heading on each
`run_refresh.py --review`. It never edits a module spec on its own.

To approve an item: implement the change in the relevant `modules/<id>/SPEC.md`
(bump semver + changelog) and `fetch.py`, then delete the item from this file.

---

## Seed items (authored at v0.1.0 — known design debts to resolve)

These are deliberate open questions from building the two reference modules,
not failures. They are the natural first things to harden.

- **[idr_stress] validate FRED series ids · `sbn10y`, `reserves`** — these are
  wired as OECD/IMF *proxies* (`IRLTLT01IDM156N`, `TRESEGIDM052N`). Confirm the
  exact series exist and represent what the labels claim, or swap to the right
  id. Until validated they are STALE-safe. *(awaiting approval)*
- **[coal] validate/replace `api2_fut` ticker** — `MTF=F` is an unconfirmed
  candidate Yahoo symbol for the API2/Newcastle future. Confirm a free,
  authoritative coal-price feed or keep it explicitly PROXY. *(awaiting approval)*
- **[idr_stress + coal] calibrate regime thresholds** — the normal/waspada/stres
  zones are provisional starting points, not derived from a historical stress
  study. Calibrate against a documented window (e.g. 2013 taper, 2018, 2022–24)
  before any zone is allowed to drive a signal. *(awaiting approval)*
- **[idr_stress] wire BI-Rate + current account** — decide between (a) a small
  BI press-release/PDF scraper, or (b) an approved manual-entry channel. Today
  they are honestly UNKNOWN. *(awaiting approval)*
- **[coal] wire official HBA scraper (ESDM minerba)** — HBA is now published
  **twice monthly and is the mandatory export reference (Permen ESDM, Mar-2025)**;
  it is the key LAGGING confirmation for the domain and worth a dedicated fetcher.
  *(awaiting approval)*

---

<!-- The watchdog appends dated review blocks below this line. -->
