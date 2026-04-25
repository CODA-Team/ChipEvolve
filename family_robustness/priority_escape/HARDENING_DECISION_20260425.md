# priority_escape hardening decision - 2026-04-25

## Verdict

`priority_escape` is **not robust-base ready**.  Keep the current candidates as
repair artifacts only until a true stuck/no-valid-candidate gate exists.

The current best hardening direction is not "wider priority search"; it is
telemetry-driven escape:

- First emit real stuck telemetry inside the negotiation path: no valid
  candidate, repeated current-position best candidate, unchanged illegal state,
  per-cell stuck streak, and active-set/candidate cap hits.
- Then enable escape only for telemetry-confirmed stuck cells.
- Keep escape bounded by candidate count, displacement guard, deduplication,
  rollback, and explicit attempted/accepted/fixed counters.
- Preserve row-bucket active-set and dirty-region bystander repair as the
  scale-safe base; do not reintroduce all-cell expansion or broad bystander
  scans on large designs.

## Why the old path is not robust

- `priority01_home_stall_fast` passed aes legality but timed out on jpeg at
  `180.058s` after only two negotiation iterations.  The old comparator path
  called legality checks during sort, which is exactly the wrong scaling shape.
- `priority06_rowedge_fast` passed aes/jpeg legality but had severe HPWL
  regressions, so row-edge escape cannot be always-on policy.
- `search_wide_escape` and similar wide-window experiments were rejected on
  normal cases and did not create usable bp_quad evidence.
- R3 is normal-case safe only because diamond succeeded first: aes/jpeg both
  reported `Diamond Move Failure: 0`, so the actual priority escape fallback
  did not run.  That is a safe rollback pattern, not proof that escape repairs
  a stuck case.

## Candidate state

| Candidate | Artifact | State | Reason |
| --- | --- | --- | --- |
| `priority_escape_r3_20260425` | `priority_escape_r3_20260425.patch` | repair-only | Safe on normal aes/jpeg, but escape not exercised because diamond had zero failures. |
| `priority_escape_frontier_repair_20260425` | `priority_escape_frontier_repair_20260425.patch` | repair-only | Good scale-shape ideas, but needs real stuck/no-valid telemetry before promotion. |
| `priority01_home_stall_fast` | backup runtime patch | reject | jpeg timeout and comparator-side legality checks. |
| `priority06_rowedge_fast` | backup runtime patch | reject as base | Legal but HPWL-regressive; can only inform fallback-row-edge repair. |

## Evidence anchors

- R3 result: `family_robustness/priority_escape/WORKER_RESULT_R3_20260425.md`
- Gate result: `family_robustness/priority_escape/ROBUSTNESS_GATE_20260425.md`
- Effective-state backup: raw runtime evidence archived locally and intentionally
  not committed.
- Joint algorithm card:
  `knowledge/algorithm_cards/priority_localized_card.yaml`

## Next gates that must run

1. Telemetry-only normal smoke:

```bash
python dpl_evolve_agent/scripts/run_variant_experiment_matrix.py \
  --experiment-id priority_escape_stuck_telemetry_smoke_20260425 \
  --variants <telemetry_only_priority_escape_variant> \
  --cases aes_nangate45 jpeg_nangate45 \
  --eval-timeout-sec 180
```

Pass condition: legal, same-run baseline-safe, `escape_attempted == 0` on clean
normal cases, and stuck/no-valid counters are present in logs.

2. Real stuck/no-valid repair gate:

```bash
python dpl_evolve_agent/scripts/run_variant_experiment_matrix.py \
  --experiment-id priority_escape_real_stuck_gate_20260425 \
  --variants <telemetry_gated_priority_escape_variant> \
  --cases <known_stuck_or_synthetic_no_valid_case> \
  --eval-timeout-sec 300
```

Pass condition: `escape_attempted > 0`, `escape_accepted > 0`, stuck count
decreases, final placement legal, and HPWL/runtime/displacement stay inside the
same-run guard.

3. Large stress gate after the parent active-set path is budget-safe:

```bash
python dpl_evolve_agent/scripts/run_variant_experiment_matrix.py \
  --experiment-id priority_escape_large_stress_gate_20260425 \
  --variants <telemetry_gated_priority_escape_variant> \
  --cases ariane133_nangate45 bp_quad_nangate45 \
  --eval-timeout-sec 600
```

bp_quad must not be used to promote escape until baseline/parent negotiation is
itself under budget.
