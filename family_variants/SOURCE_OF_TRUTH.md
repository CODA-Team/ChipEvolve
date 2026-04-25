# Family Source Of Truth

This page prevents a common research-agent mistake: treating every committed
patch as a clean-base, flow-ready family.  The current family records have
different shapes and must be consumed differently.

## Taxonomy

| Source kind | Meaning | Safe consumption |
| --- | --- | --- |
| `generated_matrix_variant` | Source is produced by a generator or mutator script. | Edit the generator or add a new generator variant; do not assume the research patch is complete. |
| `clean_base_patch` | Patch applies directly over the clean `dpl_evolve` base. | Can be materialized as a family after gates pass. |
| `overlay_chain` | Patch applies over another generated or materialized parent. | Reconstruct the parent first or collapse the chain into a standalone patch/generator. |
| `materialized_sidecar` | Family has a complete sidecar source patch and materializer path. | Use the materializer and keep hardening patches as lineage evidence. |
| `repair_candidate` | Patch is evidence for a repair mechanism, not a default parent. | Add telemetry and proof gates before enabling. |
| `polish_only` | Patch is useful only after a legal parent already exists. | Run as opt-in post-legal polish with transaction and rollback. |

## Current Families

| Family | Source kind | Source-of-truth | Research patch role | Current action |
| --- | --- | --- | --- | --- |
| `negotiation_row_bucket_quality_frontier_r5` | `generated_matrix_variant` | `scripts/run_variant_experiment_matrix.py` plus manifest | Frontier delta evidence; not the full r5 implementation by itself. | Build R6 in the generator: true two-pass top-K frontier plus row index and large gate. |
| `netaware12_prefilter_hotset_guard` | `overlay_chain` | Overlay over `netaware11_local_hpwl_anchor_cap` | Concrete code delta for bounded local HPWL, but not a clean-base patch. | Collapse netaware11+12 into a standalone materializer/generator before promotion. |
| `legalm_engine` | `materialized_sidecar` | `family_variants/legalm_engine/dpl_evolve.patch` | R4/R5 patches are hardening lineage; R4 counterfix is required, R5 is rejected as base quality. | Implement LEGALM R6 row-segment batch assignment from the sidecar base plus R4 fix. |
| `priority_escape` | `repair_candidate` | Manifest plus repair patches | Escape mechanics evidence; not base proof because current evidence lacks stuck/no-valid trigger closure. | Add telemetry-first stuck/no-valid gate before any enablement. |
| `localized_swap` | `polish_only` | Manifest plus thin polish patch | Shows a post-legal hook, not a bounded transactional implementation. | Rebuild as legal-parent-only transactional polish. |

## Required Metadata For New Family Artifacts

Every new family artifact must state:

- whether it is a clean-base patch, overlay chain, generator variant,
  materialized sidecar, repair candidate, or polish-only evidence;
- exact parent source or generator;
- command entrypoint and whether it remains on the common strict evolve path;
- target symbols and intended mechanism;
- telemetry that proves the mechanism executed;
- gate cases and promotion blockers.

If this metadata is missing, do not promote the artifact as a base family.
