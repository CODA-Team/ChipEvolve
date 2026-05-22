# Experiment Plans

This directory contains batch plans for outer-loop DPL experiments.

The goal is to test whether a class of code changes transfers across cases and
utilization settings.  Do not treat a one-case micro-gain as proof.  Use these
plans to collect comparable baseline evidence, run Teacher/Student search, and
then inspect which mechanisms repeat.

## TSV Format

`experiments/launchers/run_aggressive_flow_knowledge_experiments.sh --plan <file>` expects tab
separated rows:

```text
enabled case core_utilization flow_variant round_id start_kind notes
```

- `enabled`: `1` to run, `0`/`false`/`skip` to ignore.
- `case`: problem id under `problems/`.
- `core_utilization`: integer value, `default`, or `-`.
- `flow_variant`: stable ORFS placement snapshot name.
- `round_id`: stable Teacher/Student output directory name.
- `start_kind`: `framework`, `diamond`,
  `evolved_diamond`, `evolved_negotiation`, or `prepared`.
  `evolved_*` rows use prepared seed sources created by
  `scripts/prepare_workspace.sh`.
- `notes`: short human intent for this experiment point.

## Recommended Pattern

1. Keep one plan per hypothesis family.
2. First run with `--baseline-only` to build placement snapshots and canonical
   baselines.
3. Then run the full plan to launch Teacher/Student loops.
4. Compare mechanisms through each student's `knowledge_card.md`, not only the
   final HPWL table.

For a frozen candidate patch, create a separate plan and seed line instead of
editing this shared runner.  The runner should stay generic.

## Fixed-Candidate Matrix

When one student produces a promising source commit, test that exact code
across the whole plan before promoting it:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/run_round_candidate_matrices.sh" \
  --round-id <round> \
  --student student_XX \
  --iteration iter_YY \
  --plan "$DPL_EVOLVE_AGENT_ROOT/configs/experiment_plans/flow_knowledge_core_util.tsv"
```

This builds one private OpenROAD binary and reuses it for every enabled plan
row.  That is the key distinction from case-by-case evolution: the code is held
constant while the design and utilization change.

## JPEG Util60 Discovery Then Full Matrix

The main large knowledge experiment is:

```bash
"$DPL_EVOLVE_AGENT_ROOT/experiments/launchers/run_jpeg_util60_discovery_then_matrix.sh"
```

Default behavior:

1. Run the full baseline matrix from `full_cross_case_core_util.tsv`.
2. Evolve only `jpeg_nangate45` at `CORE_UTILIZATION=60`.
3. Use `framework` as the student start point.
4. Run 4 students for 12 iterations.
5. Commit every generated student source revision.
6. Export each fixed candidate revision and run it on all 9 plan rows.

If all 48 candidates are produced, this yields `48 x 9 = 432` candidate-case
measurements.
