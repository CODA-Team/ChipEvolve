# Full-Opt Timeout And JPEG Plan

## Current Repository State

The active project line is the constrained `detailed_placement_evolve`
framework plus lightweight private variant relink.  The repo should be read in
this order for normal work:

1. `README.md`
2. `AGENTS.md`
3. `knowledge/CONTEXT_AUDIT.md`
4. `baseline/canonical_lines.yaml`
5. `family_variants/REFERENCE_INDEX.yaml`

The historical family-tree path is no longer the main workflow.  The durable
experiment boundary is:

- keep classic OpenROAD DPL and evaluator logic unchanged,
- edit only private `tools/OpenROAD/src/dpl_evolve` variant sources,
- relink private OpenROAD binaries,
- compare against `openroad_dpl_flow`,
- store runtime artifacts under ignored `.dpl_evolve_state/` and ORFS
  `flow/{logs,reports,results}`.

## bp_quad Full-Opt Observation

`bp_quad_nangate45` showed that the strict full-opt path can exceed a 1200s
outer timeout even after legalization and placement checks have succeeded.
The timeout happened during final metrics reporting, not inside LEGALM or
Diamond legalization.

Observed full-opt main-flow comparison:

| line | legalize | improve | mirror | main elapsed | legal HPWL | post-mirror HPWL |
|---|---:|---:|---:|---:|---:|---:|
| evolve LEGALM r2 | 19s | 635s | 11s | 13:24 | 48,789,999.6 | 45,091,609.9 |
| OpenROAD DPL flow | 16s | 834s | 11s | 16:42 | 48,792,890.2 | 45,012,402.3 |

Interpretation:

- LEGALM r2 legalizer-only is close to Diamond/OpenROAD DPL on bp_quad.
- After `improve_placement` and mirroring, OpenROAD DPL still wins HPWL by
  about 0.18%.
- LEGALM r2 reaches the same downstream strict check path faster, mostly
  because its starting placement makes `improve_placement_evolve` cheaper.
- A 1200s wrapper is too tight for bp_quad full-opt plus final metrics.  Use at
  least 2400s for smoke-style guarded evaluation and a larger design-specific
  budget when timing/power metrics must finish.

## JPEG Next Boundary

Use `jpeg_nangate45` as the next primary iteration case because it is large
enough to expose real runtime and quality tradeoffs while still much faster
than bp_quad.

For each student/Teacher round:

- collect or refresh the `openroad_dpl_flow` and `evolve_default` rows first,
- require strict legality and independent metrics,
- allow moderate runtime increase if HPWL meaningfully improves,
- report both legalizer-stage HPWL and post-`improve_placement` HPWL,
- preserve displacement tail and max displacement as guard metrics,
- prefer mechanisms that can explain their effect through stage telemetry.

Do not treat "faster but same HPWL" as the main success criterion for JPEG.
The near-term goal is to test whether aggressive case-specific algorithm
changes can beat the OpenROAD DPL flow anchor without changing the evaluator.

## JPEG Evolution Calibration

Recent Teacher/Child runs showed that JPEG can beat the OpenROAD DPL flow
anchor, but the winning signal is fragile:

- a middle iteration found a strict final HPWL improvement over the baseline,
  even though the legalizer-stage handoff was not clearly better,
- later iterations regressed when they continued weaker lineages or trusted
  local proxies too much,
- higher row-assignment coverage or more LEGALM seeds did not by itself predict
  final HPWL,
- local window/proxy HPWL improvements can be erased or reversed by the
  complete flow.

Therefore JPEG rounds must preserve the best-so-far evolved artifact as an
elite parent.  At least one child should continue from that artifact each
iteration.  Other children can explore aggressively, but they should be judged
against both the baseline and the elite parent.

Use legalizer-stage HPWL, seed counts, local proxy deltas, and Stage3 move
counts to explain behavior.  Do not promote a candidate on those numbers unless
the final strict evaluator result also improves.
