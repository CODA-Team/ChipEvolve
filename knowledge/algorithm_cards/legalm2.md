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
