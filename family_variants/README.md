# Family Variants

This directory stores reusable family-specific `dpl_evolve` source variants.

The model is:

- `tools/OpenROAD/src/dpl_evolve` is the clean initial evolve base
- each family variant is a patch over that base
- a materialized variant source tree is built into its own OpenROAD binary

Use:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/materialize_family_variant.sh" \
  --family legalm_engine \
  --output-dir "$DPL_EVOLVE_STATE_ROOT/family_variants/legalm_engine/dpl_evolve" \
  --force
```

Then build that source tree with the lightweight relink path:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant_relink.sh" \
  --variant-root "$DPL_EVOLVE_STATE_ROOT/variants/legalm_engine" \
  --dpl-src "$DPL_EVOLVE_STATE_ROOT/family_variants/legalm_engine/dpl_evolve"

source "$DPL_EVOLVE_STATE_ROOT/variants/legalm_engine/variant_env.sh"

"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_variant_relink.sh" --threads 10
```

Run family variants with an explicit binary. Do not rely on the root
`tools/install/OpenROAD/bin/openroad` once a family variant is involved.

## Family Status

Flow-ready generated candidates:

- `negotiation_row_bucket_quality_frontier_r5/`

Materialized structural families:

- `legalm_engine/`

Candidate/status manifests:

- `netaware_objective/`
- `priority_escape/`
- `localized_swap/`

Only flow-ready generated candidates should be added to default matrix groups.
Candidate/status manifests are evidence and routing guidance until their
required gates pass.

## Research Patch Artifacts

Some families are not flow-ready yet, but their current local code deltas are
still useful for research agents.  Those deltas live under each family
directory as `research_patches/*.patch`.

These patches are committed so future agents can inspect concrete code, reuse
mechanisms, and materialize the next implementation without relying on private
local archives.  They are not automatically enabled as base families unless the
family manifest says so.

Current committed research patches:

- `negotiation_row_bucket_quality_frontier_r5/research_patches/negotiation_row_bucket_quality_frontier_r5.patch`
- `netaware_objective/research_patches/netaware12_prefilter_hotset_guard.patch`
- `legalm_engine/research_patches/legalm_counterfix_r4.patch`
- `legalm_engine/research_patches/legalm_stage1_quality_guard_r5.patch`
- `priority_escape/research_patches/priority_escape_r3_20260425.patch`
- `priority_escape/research_patches/priority_escape_frontier_repair_20260425.patch`
- `localized_swap/research_patches/localswap01_bounded_local_polish.patch`
