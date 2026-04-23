# Skill: evaluate_run

This is the evaluation skill for `dpl_evolve` runs. It reads the canonical
`metrics.json` output and decides whether a candidate or family revision should
be kept, revised, or reverted.

## Canonical input

Read this file first:

- `flow/reports/<platform>/<design>/<flow_variant>/dpl_evolve_baseline/<run_tag>/metrics.json`

The control-plane wrapper for this skill is:

- `evolve_agent/adapters/science_codeevolve/evaluator.py`

The preferred comparison helper is:

- `evolve_agent/scripts/compare_runs.py`
- `evolve_agent/scripts/recommend_initial_family.py` for first-pass case classification

The evaluator is now the canonical guarded execution path for agent-driven
runs. It adds:

- per-run directory locking
- timeout enforcement
- optional memory ceilings
- process-group cleanup
- compact stdout/stderr tails on failure

## Primary comparison fields

Read these fields first from `metrics.json`:

- `manifest`
- `legalization`
- `hpwl_proxy`
- `displacement`
- `timing_metrics`
- `power_metrics`
- `design_metrics`
- `legality`
- `supporting_files`

## Decision order
1. legality must pass
2. compare strict-track runs first
3. for a new case, classify the baseline metrics before picking the first family
4. primary objectives: HPWL, setup WNS, setup TNS
5. displacement must remain controlled
6. runtime must remain reasonable
7. only then inspect secondary hold/power side effects

## Mandatory comparison modes
### Mode A — strict legalizer comparison
Compare only strict-track outputs when claiming legalizer improvement.

### Mode B — integrated comparison
Use reduced-flow / flow-faithful results only after Mode A succeeds.

## Keep / revert heuristic
Keep a patch only if:
- legality passes
- the candidate is on or clearly moves toward a better HPWL/WNS/TNS/runtime frontier
- displacement regression is within explicitly allowed envelope
- runtime is acceptable

Revert if:
- legality fails
- metrics file is malformed
- HPWL gain is clearly due to non-legalizer post-processing in the wrong track
- displacement or runtime regress badly without compensating benefit
- a family only improves HPWL but loses too much WNS/TNS on the same case

## Evaluator status fields

Read `status` first from the evaluator JSON:

- `ok`
- `dry_run`
- `locked`
- `build_failed`
- `run_failed`
- `missing_artifact`

## Examples

Compare a baseline and candidate run:

```bash
python3 evolve_agent/scripts/compare_runs.py \
  --left evolve_agent/checkpoints/operations/manual_gcd_round_20260422/baseline_eval.json \
  --right evolve_agent/checkpoints/operations/manual_hpwl_timing_search_before_wide_greedy/gcd_candidate8_eval.json
```

Classify a new baseline case before choosing the first family:

```bash
python3 evolve_agent/scripts/recommend_initial_family.py \
  --metrics flow/reports/nangate45/ibex/place_batch_20260421_220319/dpl_evolve_baseline/cross_ibex_baseline/metrics.json
```

Dry-run the evaluator for one evolve line:

```bash
python3 evolve_agent/adapters/science_codeevolve/evaluator.py \
  --problem evolve_agent/problems/gcd_nangate45/problem.yaml \
  --mode single \
  --line evolve_line \
  --flow-variant dpl_evolve_suite_20260422_125226 \
  --run-tag agent_eval_dryrun \
  --dry-run \
  --out /tmp/evolve_agent_eval.json
```

Evaluate an existing single-line run without rebuilding or rerunning:

```bash
python3 evolve_agent/adapters/science_codeevolve/evaluator.py \
  --problem evolve_agent/problems/gcd_nangate45/problem.yaml \
  --mode single \
  --line evolve_line \
  --flow-variant dpl_evolve_suite_20260422_125226 \
  --run-tag agent_setup_verify \
  --use-existing \
  --out evolve_agent/checkpoints/operations/setup_verify_default/agent_setup_verify_eval.json
```

Evaluate a full suite run:

```bash
python3 evolve_agent/adapters/science_codeevolve/evaluator.py \
  --problem evolve_agent/problems/gcd_nangate45/problem.yaml \
  --mode suite \
  --flow-variant dpl_evolve_suite_20260422_125226 \
  --tag-prefix agent_suite \
  --use-existing \
  --out evolve_agent/checkpoints/operations/strict_baseline_snapshot/agent_suite_eval.json
```
