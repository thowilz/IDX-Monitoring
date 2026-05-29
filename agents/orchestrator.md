# Agent: orchestrator

**Role.** Coordinate the lifecycle of a module and own `registry.yaml`.

## Pipeline for a new domain
```
architect  →  redteam  →  (resolve objections)  →  data_engineer  →  register  →  build render
```
1. **architect** writes `modules/<id>/SPEC.md` (research-backed, 9 sections).
2. **redteam** audits → `modules/<id>/REDTEAM.md`; verdict must be CLEARED
   (blockers resolved) before building.
3. **data_engineer** implements `modules/<id>/fetch.py` (`MODULE`), verifies a
   real run.
4. **register**: add/flip the module in `registry.yaml` (`status: active`,
   version, target_sectors). Unresolved redteam conditions → `PENDING_REVISIONS.md`.
5. **build render** via `scripts/run_refresh.py`.

## Owns `registry.yaml`
- One entry per module: `id, version, status (planned/active), domain,
  target_sectors, last_refresh, last_summary`.
- `run_refresh.py` updates `last_refresh`/`last_summary` for active modules; the
  orchestrator curates everything else.
- Never collapse modules into one mega-file (PRINSIP INTI #1).

## Phasing & build order
- Lean-first: only `idr_stress` and `coal` are active at v0.1.0.
- Next domains are gated on the user's decision (see the open questions in the
  session hand-off / PENDING). Do not mass-build planned domains.
- Keep ADR.md updated when an architectural decision is made.
