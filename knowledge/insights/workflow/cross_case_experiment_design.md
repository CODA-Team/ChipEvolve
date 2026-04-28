# Cross-Case Experiment Design

Single-case Teacher/Student evolution is useful for finding mechanisms, but it
is not enough to prove that a DPL change is valuable.  Use an outer experiment
matrix to separate three questions:

1. Does the mechanism beat the canonical `openroad_dpl_flow` baseline on the
   discovery line?
2. Does it still help when placement density or whitespace changes?
3. Does it transfer to designs with different population, density, technology,
   and HPWL sensitivity?

## Preferred Pattern

1. Define a TSV plan under `configs/experiment_plans/`.
2. Generate or reuse placement snapshots for every matrix row.
3. Refresh `openroad_dpl_flow` and `evolve_default` baselines for every row.
4. Run Teacher/Student loops on one discovery line to produce candidate source
   snapshots.
5. Freeze each promising `source_backup`.
6. Run `scripts/run_candidate_matrix.sh` so the same code is tested unchanged
   on every matrix row.
7. Compare `metrics.json`, `implementation.diff`, and each student's
   `knowledge_card.md`.

## Matrix Shape

Use rows that cover:

- the discovery design at low, medium, and high utilization,
- small smoke designs,
- medium wirelength-sensitive designs,
- large row-rich designs,
- at least one alternate technology or library setting.

The exact case ids belong in the experiment plan, not in this insight card.
Round ids should describe design class and utilization class rather than
hard-coding a benchmark name when possible.

## Promotion Rule

Do not call tiny HPWL gains a strategic win.  Preserve them as donor evidence
when they reveal a mechanism, but use the outer matrix to decide whether the
mechanism is worth turning into a stronger patch.

The key control is fixed-source validation.  If a student improves only after
rewriting for each target, that is search evidence.  If the same source backup
improves multiple density classes and design families without edits, that is
algorithm knowledge.

## Expected Scale

A 4-student by 12-iteration discovery round produces 48 fixed source trees.  A
9-row transfer matrix gives 432 candidate-case measurements.  This scale is
large enough to identify donor mechanisms and reject overfit changes.
