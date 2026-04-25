# Base Family Status - 2026-04-25

This is the coordinator-facing status table for the current base-family
hardening phase.  It intentionally separates robust starting points from
exploration ideas, repair candidates, and rejected paths.

## Phase Rule

Base-family work currently prioritizes hardening a few real algorithms.  Do
not promote algobank mixtures, self-evolving prompt variants, fallback paths,
build-only variants, or `aes`-only wins.  They can be evidence, but the base
implementation must have a coherent scale-safe mechanism and must not
materially degrade HPWL, timing proxy, runtime, or displacement versus the
same-run baseline.

## Current Status

| Family / variant | Status | Reason |
| --- | --- | --- |
| `negotiation_row_bucket_active_set` | primary scale-safe candidate | Uses row-local buckets and bounded active-set growth.  `aes`/`jpeg` strict gates are legal; `bp_quad` legalizer completed without routing around negotiation, while full metrics need a longer gate. |
| `search_narrow_runtime` | safe calibration base | Useful as a low-risk first probe and runtime guard, but not the main research algorithm by itself. |
| `netaware02_history_sqrt_anchor` | safe light objective/search base | Current safe net-aware startpoint.  Use for objective/ranking work before heavier graph-aware variants. |
| `netaware03_row_guard_frontier` | quality-biased opt-in | Stronger HPWL signal than the safe base, but slower and not robust on large stress gates. |
| `netaware11_local_hpwl_anchor_cap` | quality-biased repair candidate | Strong HPWL/timing improvement on `aes` and `jpeg`, but runtime is slower and `jpeg` max displacement is too high for robust-base promotion. |
| `netaware12_prefilter_hotset_guard` | repair candidate | R4 bounds the net-aware idea with shortlist/hotset guards.  It is legal on `aes`, `jpeg`, and `ariane133`; HPWL improves by 2.07%, 6.47%, and 4.58% respectively, with runtime overhead around 18-20% and repaired max displacement.  Needs more HPWL or lower overhead before hard-base promotion. |
| `negotiation_scale_component_dirty` | reject for promotion | Legal and faster on `aes`/`jpeg`, but HPWL and displacement regress versus same-run baseline. |
| `negotiation_row_bucket_quality_guard` | repair candidate | R4 adds a lightweight net-anchor/displacement quality guard on top of row buckets.  HPWL improves strongly on `aes` and `jpeg`, but runtime gives back the row-bucket advantage, especially versus the previous active-set variant. |
| `negotiation_row_bucket_quality_frontier_r5` | flow-ready aes/jpeg candidate, needs large gate | R5 keeps the quality proxy but applies it only to a cheap-score frontier.  It is now registered as matrix variant `negotiation_row_bucket_quality_frontier_r5` and documented under `family_variants/`.  It is legal on `aes`/`jpeg`, improves HPWL by 6.09%/1.92%, and improves runtime by 8.99%/24.66% versus same-run baseline.  Next gate is `bp_quad` or `ariane133`, not more small-case tuning. |
| `priority_escape_r3_20260425` | narrow repair only | Uses a diamond-first gate, so it does not prove priority escape as the evolved algorithm.  Keep only for real stuck/no-valid-candidate failures. |
| `localized_swap_hotbucket_rollback_cap` | reject current implementation | Legal but much worse than same-run baseline on HPWL, runtime, displacement, and timing proxies.  Revisit only as opt-in polish with strict rollback. |
| `legalm_base_bounded_stage1_counterfix` | legality repair candidate | R4 telemetry found a stale maintained-overflow counter after Stage1.  The counter fix passes strict `aes` and `jpeg`, but `jpeg` HPWL and max displacement are much worse than the normal evolve baseline, so it is not a hard base. |
| `legalm_stage1_quality_guard_r5` | legality repair lineage, not base | R5 keeps LEGALM legal on `aes`/`jpeg` and slightly reduces HPWL versus R4, but `jpeg` displacement worsens and remains far worse than the known clean evolve baseline. |

## Next Algorithm Work

1. Gate `negotiation_row_bucket_quality_frontier_r5` on a large/stress case.
   Do not retune it on small cases until `bp_quad` or `ariane133` is understood.
2. Repair net-aware quality candidates by recovering more HPWL inside the
   bounded shortlist/hotset model.
3. Continue LEGALM only as a legality-repair lineage.  Do not route it as a
   base until JPEG displacement/HPWL are close to the normal evolve baseline.
4. Rebuild localized swap only after a legal parent is already strong.  Any
   swap polish must be hotset-based, transactional, and skippable when quality
   is not neutral-to-positive.
5. Use priority escape only when telemetry shows real stuck-cell or
   no-valid-candidate behavior.  Do not use fallback-to-diamond as base
   evidence.

## Context Rule

Future workers should read this file, `ROBUST_BASE_DECISION_20260425.md`, and
`knowledge/algorithm_cards/base_family_cards.yaml` before reading raw
experiment artifacts.  Before applying any family patch, also read
`family_variants/SOURCE_OF_TRUTH.md`: committed research patches are not all
clean-base patches.  Some are generator deltas, overlay-chain deltas, repair
evidence, or polish-only snippets.  Runtime JSON/logs are evidence for a
specific gate, not the default context.
