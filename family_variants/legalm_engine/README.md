# legalm_engine

`legalm_engine` is a family-specific `dpl_evolve` variant.

It is not part of the clean initial evolve base. Materialize it into its own
source tree, build a dedicated OpenROAD binary, and run it through the strict
legalization-only evolve flow.

Current status: legality repair lineage only.  `legalm_counterfix_r4` fixed a
real stale-overflow-counter failure and made AES/JPEG legal, but JPEG quality is
still too poor and BP has no strict LEGALM pass.  `legalm_stage1_quality_guard_r5`
is not a base candidate because it only slightly improves JPEG HPWL versus R4
while worsening JPEG displacement.  Fallback-to-diamond/default OpenDP results
are diagnostic only and must not be counted as `legalm_engine` success.

Materialize:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/materialize_family_variant.sh" \
  --family legalm_engine \
  --output-dir "$DPL_EVOLVE_STATE_ROOT/family_variants/legalm_engine/dpl_evolve" \
  --force
```

Configure and build:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant_relink.sh" \
  --variant-root "$DPL_EVOLVE_STATE_ROOT/variants/legalm_engine" \
  --dpl-src "$DPL_EVOLVE_STATE_ROOT/family_variants/legalm_engine/dpl_evolve"

source "$DPL_EVOLVE_STATE_ROOT/variants/legalm_engine/variant_env.sh"

"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_variant_relink.sh" --threads 10
```

Run:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/run_canonical_line.sh" \
  --line evolve_default \
  --openroad-binary "${OPENROAD_BINARY}" \
  --case gcd_nangate45 \
  --flow-variant smoke_legalm_variant
```

For matrix-style family variants, the harness keeps the common
`detailed_placement_evolve -use_negotiation` command and routes that private
materialized source to LEGALM internally.  For direct checks, use the dedicated
variant binary with the same `evolve_default` line.  Do not change the central
evaluator command to make a LEGALM result look successful.

The canonical family metadata lives in:

- `manifest.yaml`
- `../../knowledge/family_components/legalm_engine.yaml`

Current hardening artifacts:

- `../../family_robustness/legalm_engine/WORKER_RESULT_R4_20260425.md`
- `../../family_robustness/legalm_engine/WORKER_RESULT_R5_20260425.md`
- `research_patches/legalm_counterfix_r4.patch`
- `research_patches/legalm_stage1_quality_guard_r5.patch`
- `../../family_robustness/legalm_engine/NEXT_ALGORITHM_DIRECTION_20260425.md`

Next required gate before promotion:

- Build/materialize the next algorithm-level candidate, expected direction
  `legalm_r6_row_segment_batch_assignment`.
- Run strict `aes_nangate45`, `jpeg_nangate45`, and `bp_quad_nangate45` through
  the same detailed-placement evolve line with no fallback.
- Report HPWL delta, average displacement, max displacement, runtime, RSS,
  timing proxy, placement violations, LEGALM entry logs, and per-stage
  complexity telemetry.
