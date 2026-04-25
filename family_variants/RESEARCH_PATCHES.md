# Research Patches

This file indexes committed family code deltas that are useful to research
agents but are not all promotion-ready base families.

Rules:

- Treat these patches as code evidence and idea sources.
- Do not auto-enable a repair or polish family unless its manifest says it is
  flow-ready.
- Keep all candidates on the same detailed-placement evolve entrypoint unless a
  family manifest explicitly marks a dedicated materialized path.
- Do not count fallback-to-diamond or fallback-to-default behavior as family
  success.

## Current Artifacts

| Family | Patch | Patch Kind | Status | Intended Use |
| --- | --- | --- | --- | --- |
| `negotiation_row_bucket_quality_frontier_r5` | `negotiation_row_bucket_quality_frontier_r5/research_patches/negotiation_row_bucket_quality_frontier_r5.patch` | generator delta evidence | flow-ready candidate needs large gate | Inspect current row-bucket frontier implementation and evolve the generator toward R6 true two-pass frontier. |
| `netaware_objective` | `netaware_objective/research_patches/netaware12_prefilter_hotset_guard.patch` | overlay over netaware11 parent | repair candidate | Use as concrete code evidence for bounded local HPWL scoring; collapse the parent chain before promotion. |
| `legalm_engine` | `legalm_engine/research_patches/legalm_counterfix_r4.patch` | sidecar hardening lineage | legality repair evidence | Keep the stale-overflow counter fix when building the next LEGALM implementation. |
| `legalm_engine` | `legalm_engine/research_patches/legalm_stage1_quality_guard_r5.patch` | sidecar hardening lineage | rejected as base | Learn why scalar Stage1 quality scoring is insufficient before designing row-segment batch assignment. |
| `priority_escape` | `priority_escape/research_patches/priority_escape_r3_20260425.patch` | repair evidence | repair-only evidence | Inspect bounded escape/row-bucket mechanics; do not use as base without stuck/no-valid telemetry. |
| `priority_escape` | `priority_escape/research_patches/priority_escape_frontier_repair_20260425.patch` | repair evidence | repair-only evidence | Inspect frontier repair logic for future telemetry-gated escape. |
| `localized_swap` | `localized_swap/research_patches/localswap01_bounded_local_polish.patch` | polish hook evidence | polish evidence only | Inspect minimal post-legal polish hook; future implementation must be transactional and opt-in after a legal parent. |
