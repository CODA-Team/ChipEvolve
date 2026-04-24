# Variant Matrix Evidence, 2026-04-24

This note summarizes the first deterministic offline evidence-generation matrix
after the RunDB/KnowledgeDB path was added.

The run used private `dpl_evolve` source copies and private relinked OpenROAD
binaries. It did not modify the ORFS target tree during evaluation.

Artifact root:

- `$DPL_EVOLVE_STATE_ROOT/experiments/matrix_nangate45_scale_20260424_3`

Cases:

- `aes_nangate45`
- `ibex_nangate45`
- `jpeg_nangate45`
- `ariane133_nangate45`
- `bp_quad_nangate45`

## High-Confidence Signals

`search_narrow_runtime` is the strongest general first-shot family in this
matrix. It shrinks the search windows and improved the controller score on all
scored non-`bp_quad` cases:

- `aes_nangate45`: score `+0.044188`, runtime `3.391s`
- `ibex_nangate45`: score `+0.036562`, runtime `3.695s`
- `jpeg_nangate45`: score `+0.007579`, runtime `32.813s`
- `ariane133_nangate45`: score `+0.031938`, runtime `70.763s`

Use it as the preferred cheap few-shot starting point for normal Nangate45
medium and large cases before trying heavier refinement families.

`search_wide_escape` is not a good default. It regressed all scored non-`bp_quad`
cases and increased runtime. Wide search should be reserved for cases with
explicit stuck-cell evidence, not as a first move.

## Case-Specific Cost Shaping

`history_strong` is useful on some mid/large cases but not universal:

- `ibex_nangate45`: score `+0.044263`
- `jpeg_nangate45`: score `+0.004734`
- `aes_nangate45`: slight weighted regression despite HPWL improvement
- `ariane133_nangate45`: weighted regression

`history_soft` is useful on `aes_nangate45` but regressed `ibex`, `jpeg`, and
`ariane133` in this matrix:

- `aes_nangate45`: score `+0.020722`

For few-shot unseen cases, treat historical congestion scaling as
case-sensitive. Prefer `search_narrow_runtime` first; then try `history_strong`
for `ibex`/`jpeg`-like designs and `history_soft` for `aes`-like designs.

## Weak Or Risky Families

`drc_late_ramp` showed only a tiny `ibex_nangate45` improvement and otherwise
regressed or failed to improve. It is not a strong standalone family.

`disp_soft` and `disp_strong` only helped `ariane133_nangate45` slightly and
hurt smaller and medium cases through runtime/score regression. Treat
displacement pressure changes as a narrow follow-up, not a first-shot family.

`greedy1` and `greedy2` are unsafe as direct post-negotiation enables. They
caused placement check failures across the matrix. Do not enable raw
`greedyImprove` after the main pass unless the patch also repairs convergence
and legality.

## Large-Stress Handling

`bp_quad_nangate45` exceeded the 600-second strict legalizer budget for the
clean baseline and all tested variants. This should not be mixed into every
normal family sweep. Use it as a separate large-stress queue with:

- stricter timeout accounting,
- runtime-first candidate pruning,
- telemetry around candidate counts and no-valid-candidate loops,
- fewer high-risk quality-only mutations per batch.

The current evidence says the first large-stress task is not HPWL shaping; it
is making negotiation legalization observable and budget-safe on macro-heavy
large designs.

## Router Guidance

For the next few-shot experiments:

- Start normal Nangate45 medium/large cases with `search_narrow_runtime`.
- Try `history_strong` after `search_narrow_runtime` on `ibex`/`jpeg`-like
  cases if HPWL remains poor.
- Try `history_soft` on `aes`-like cases.
- Avoid raw postopt enablement.
- Avoid wide search unless telemetry shows a stuck-cell/candidate-coverage
  problem.
- Route `bp_quad`-class cases to a separate runtime-stress policy.
