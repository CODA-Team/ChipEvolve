# LEGALM 2.0 — Human-Readable Card

## Core thesis
LEGALM 2.0 treats legalization as a staged optimization problem:

1. scanline-based initial legalization
2. ALM-based overflow elimination
3. zero-overflow refinement

It also adds:
- connectivity-based local optimum escape
- routability-aware penalties
- strong parallelization ideas

## Why it matters for OpenROAD
LEGALM is **not** the closest code donor for the current OpenROAD legalizer,
but it is an excellent **idea donor** for:
- initialization
- escape from stuck local regions
- explicit refinement after legality is reached

## Current calibration

Treat a LEGALM-style implementation as a donor or ablation until strict final
metrics prove otherwise.  A self-legal LEGALM path can be useful and
inspectable, but legality and paper fidelity do not by themselves mean it is
the best parent for a case.

Do not replace the active `detailed_placement_evolve` parent with a full
LEGALM route only because it is more paper-faithful.  Promote it only when the
complete flow beats the active case baseline and the best-so-far evolved
artifact.

## Mechanisms worth borrowing first
- better initialization
- overflow-stagnation detection
- connected-component / plate aware escape
- no-overflow refinement stage

## Mechanisms to postpone
- full ALM variable formulation
- GPU / TP / BGD full rewrite

Treat these as hypotheses to port and test.  The current framework does not
fix the exact LEGALM objective, partitioning scheme, or stage order.
