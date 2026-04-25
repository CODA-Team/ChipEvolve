# localized_swap hardening decision - 2026-04-25

## Verdict

`localized_swap` must remain **opt-in polish after a legal parent**, not a base
family and not an illegal-parent repair path.

The reasonable direction is a small, bounded, transactional post-legalization
polish that runs only after a selected parent has already produced a legal,
runtime-safe placement.  If the parent is illegal, timed out, or quality-bad,
localized polish must skip and report skip, not claim success.

## Why the old path is not robust

- The old `localswap*` routes mostly combined postopt enablement, target/cost
  tweaks, congestion tweaks, and sort policies while leaning on the same swap
  primitive.  That did not prove a distinct localized algorithm.
- Full same-shape pair enumeration and broad greedy/swap-greedy postopt have
  repeated placement-check failures or runtime risk.
- `localswap_hotbucket_rollback_cap_20260425` was legal but failed quality
  badly: aes HPWL +147.0% and runtime +127.2%; jpeg HPWL +118.1% and runtime
  +433.8% versus same-run default.
- `localswap_skip_polish_budget_r3_20260425` skipped the worst polish, but the
  remaining path was still far worse than same-run default.  It is a narrowing
  safety signal, not a promotion candidate.
- `localswap01_bounded_local_polish` showed small aes/jpeg smoke wins, but
  bp_quad still timed out.  That is polish evidence only, not base robustness.

## Required contract for any next localized candidate

- Parent must already be legal.
- Parent runtime and quality must already be inside guard.
- Candidate set must be hotset/bucket/window bounded.
- Exact pair enumeration is allowed only for small same-shape groups.
- Candidate cap, accepted-move cap, and wall-clock budget must be hard stops.
- Every accepted swap must be transactional with rollback on row/fence/DRC or
  quality regression.
- Metrics must include parent baseline, post-polish delta, candidates,
  accepted, cap hits, rollback count, elapsed milliseconds, and skip reason.

## Candidate state

| Candidate | Artifact | State | Reason |
| --- | --- | --- | --- |
| `localswap_hotbucket_rollback_cap_20260425` | `WORKER_RESULT_R3_20260425.md` | reject for promotion | Legal but severe HPWL/runtime/displacement regression. |
| `localswap_skip_polish_budget_r3_20260425` | runtime-state patch | reject for promotion | Safety narrowing only; remaining path still worse than default. |
| `localswap01_bounded_local_polish` | backup runtime patch | repair/polish evidence | Small aes/jpeg wins, but no large-case proof and saved patch is not standalone full implementation. |
| greedy and swap-greedy postopt | prior matrix rows | reject | Repeated placement-check failures. |

## Evidence anchors

- R3 result: `family_robustness/localized_swap/WORKER_RESULT_R3_20260425.md`
- Bounded polish decision: `family_robustness/localized_swap/ROBUSTNESS_DECISION_20260425.md`
- Backup patch: raw runtime diff archived locally and intentionally not
  committed because it is not a standalone clone-ready implementation.
- Joint algorithm card:
  `knowledge/algorithm_cards/priority_localized_card.yaml`

## Next gates that must run

1. Legal-parent opt-in smoke:

```bash
python dpl_evolve_agent/scripts/run_variant_experiment_matrix.py \
  --experiment-id localized_swap_legal_parent_optin_smoke_20260425 \
  --variants <bounded_localized_polish_variant> \
  --cases aes_nangate45 jpeg_nangate45 \
  --eval-timeout-sec 180
```

Pass condition: parent is legal and measured, post-polish is legal, runtime is
within `1.15x` parent unless the score win justifies the cost, and no
displacement/timing outlier appears.

2. Broader legal-parent gate:

```bash
python dpl_evolve_agent/scripts/run_variant_experiment_matrix.py \
  --experiment-id localized_swap_parent_quality_gate_20260425 \
  --variants <bounded_localized_polish_variant> \
  --cases aes_nangate45 ibex_nangate45 jpeg_nangate45 ariane133_nangate45 \
  --eval-timeout-sec 300
```

Pass condition: all cases legal, all parent and post-polish metrics are
recorded, and each polish delta is neutral-to-positive or auto-rolled back.

3. Large stress queue only after parent is budget-safe:

```bash
python dpl_evolve_agent/scripts/run_variant_experiment_matrix.py \
  --experiment-id localized_swap_bp_quad_stress_20260425 \
  --variants <bounded_localized_polish_variant> \
  --cases bp_quad_nangate45 \
  --eval-timeout-sec 600
```

bp_quad timeout should keep localized_swap as polish-only; it must not be used
to blame or promote localized_swap if the parent negotiation path is still over
budget.
