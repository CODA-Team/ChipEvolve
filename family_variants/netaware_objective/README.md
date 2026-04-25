# netaware_objective

This directory packages the current best usable net-aware repair state:
`netaware12_prefilter_hotset_guard`.

It is intentionally not marked as a hard base. R4 evidence shows legal
AES/JPEG/ariane runs with repaired runtime and displacement behavior, but the
HPWL signal is weaker than the original `netaware11_local_hpwl_anchor_cap`, and
the R5 quality-recovery attempt does not have clean post-tightening evaluator
evidence.

## Artifact Contents

- `manifest.yaml`: family metadata, evidence summary, and gate requirements.
- `research_patches/netaware12_prefilter_hotset_guard.patch`: normalized code
  delta from `netaware11_local_hpwl_anchor_cap` to
  `netaware12_prefilter_hotset_guard`.

The patch touches only:

- `src/NegotiationLegalizer.h`
- `src/NegotiationLegalizerPass.cpp`

## Materialization

This directory is a compact evidence card plus committed research overlay, not
a ready-to-apply standalone source package. The next clone-ready step is to
encode the mechanism as a variant mutator or export a standalone patch against
the recorded OpenROAD anchor. Until then, future agents should inspect the
patch as concrete design guidance and not auto-load it as a runnable base.

## Evidence Summary

R4 `netaware12_prefilter_hotset_guard` is the current best repair candidate:

- AES: legal, HPWL delta -2.07%, runtime +17.65%, max displacement unchanged.
- JPEG: legal, HPWL delta -6.47%, runtime +17.87%, max displacement +0.92%.
- Ariane133: legal, HPWL delta -4.58%, runtime +20.20%, max displacement unchanged.

R5 `netaware13_quality_recover_r5` is not packaged as base: the initial build
improved HPWL more, but AES runtime was +21.09% and JPEG max displacement was
+13.50%. The later tightened rebuild succeeded but has no post-tightening eval
JSON, so it remains unclaimed.

## Next Big Change

The next candidate should not be another constant-only reward/cap tune. The
more promising direction is `netaware14_rowedge_shortlist_hpwl`:

- Use algobank's `current_blend + history_runtime_trim + row_edge_probe` as the
  cheap candidate frontier.
- Apply net-aware local HPWL only to a small eligible shortlist inside that
  frontier.
- Keep R4's fanout caps, net-eval caps, displacement outlier guard, and
  fallback-only anchor behavior.
- Optionally fork a JPEG-biased branch using `soft_threshold + overflow_only +
  row_edge_probe`, but do not make it the default until ariane/bp gates pass.

## Required Gates

Before promotion, run a fresh materialized private build and strict same-run
baseline comparison on `aes_nangate45`, `jpeg_nangate45`, and
`ariane133_nangate45`. Only then run `bp_quad_nangate45` as a two-stage
stress gate: first legalizer return, then full metrics completion.
