# Matrix Scripts

Owns fixed-source cross-case replay:

- `run_candidate_matrix.sh` builds one candidate source once and evaluates it
  across a TSV plan.
- `run_round_candidate_matrices.sh` exports committed Student sources from a
  Teacher round and launches one candidate matrix per source.

Use `scripts/workspace/` for build/relink actions, `scripts/evaluator/` for
flow and metrics helpers, and `scripts/analysis/` for source export/reporting.
