# Example: One `gcd` Codex Evolve Run

This file explains what happens when you use the Python loop to launch Codex on
one `gcd` experiment.

The example command is:

```bash
python3 evolve_agent/scripts/run_design_evolve_loop.py \
  --problem evolve_agent/problems/gcd_nangate45/problem.yaml \
  --loop-id gcd_example_run \
  --max-attempts 1
```

This is the current main path for:

- choose one case
- launch Codex once or a few times
- build quickly
- run one strict legalization-only evolve experiment
- compare against the current evolve baseline for that case
- keep or restore automatically

## Preconditions

Before the loop starts, these things must already be true:

1. A reusable place snapshot exists for `gcd`, specifically a
   `3_4_place_resized.odb` under:
   `flow/results/nangate45/gcd/<FLOW_VARIANT>/`
2. The repo has a buildable OpenROAD tree.
3. The user can run `codex exec`.

If the place snapshot does not exist, the loop stops in
`discover_flow_variant()` with a message telling you to run:

```bash
./evolve_agent/scripts/run_place_batch.sh
```

## What the Python loop does

The entrypoint is:

- [run_design_evolve_loop.py](/home/zhiyuzheng/Project/Agenticflow/OpenROAD-flow-scripts/evolve_agent/scripts/run_design_evolve_loop.py)

### 1. Resolve repo context

The script first resolves:

- repo root
- problem file
- prompt file
- flow variant

For `gcd`, if you do not pass `--prompt-file`, it infers:

- [nangate45__gcd.md](/home/zhiyuzheng/Project/Agenticflow/OpenROAD-flow-scripts/evolve_agent/tasks/design_evolve/nangate45__gcd.md)

If you do not pass `--flow-variant`, it scans:

- `flow/results/nangate45/gcd/*/3_4_place_resized.odb`

and picks the most recently modified one.

### 2. Create the loop operation directory

The loop creates:

- `evolve_agent/checkpoints/operations/<loop_id>/`

For the example above, that becomes:

- `evolve_agent/checkpoints/operations/gcd_example_run/`

This directory is the local record for the whole experiment.

It will contain:

- `baseline_eval.json`
- `attempt_01_eval.json` and later attempts if any
- `attempts.jsonl`
- `experience_log.jsonl`
- `experience_journal.md`
- `loop_state.json`
- `README.md`

### 3. Refresh the compact packet

The loop calls:

```bash
python3 evolve_agent/adapters/science_codeevolve/kb_query.py \
  --problem_dir evolve_agent/problems/gcd_nangate45 \
  --out_dir evolve_agent/knowledge/packets
```

This refreshes the current compact context packet used by the agent.

### 4. Run the current baseline for this loop

The loop then runs the evaluator once before asking Codex to patch anything.

That call is made by `run_evaluator()` and goes through:

- [evaluator.py](/home/zhiyuzheng/Project/Agenticflow/OpenROAD-flow-scripts/evolve_agent/adapters/science_codeevolve/evaluator.py)

Important current behavior:

- it uses the current problem file
- it uses `--mode single`
- it uses `line = evolve_line`
- it uses `--evolve-engine default` by default
- it uses the latest discovered reusable `FLOW_VARIANT`
- it uses the default config:
  [codex_design_specific.yaml](/home/zhiyuzheng/Project/Agenticflow/OpenROAD-flow-scripts/evolve_agent/configs/codex_design_specific.yaml)

That config currently sets:

- `build_mode: openroad_only`

So the build path is:

- [build_openroad_only.sh](/home/zhiyuzheng/Project/Agenticflow/OpenROAD-flow-scripts/evolve_agent/scripts/build_openroad_only.sh)

and not the heavier full local ORFS build.

The evaluator then runs the clean evolve line through:

- [run_baseline.sh](/home/zhiyuzheng/Project/Agenticflow/OpenROAD-flow-scripts/evolve_agent/baseline/run_baseline.sh)
- [run_evolve_line.sh](/home/zhiyuzheng/Project/Agenticflow/OpenROAD-flow-scripts/evolve_agent/baseline/run_evolve_line.sh)

and reads back:

- `flow/reports/nangate45/gcd/<FLOW_VARIANT>/dpl_evolve_baseline/<run_tag>/metrics.json`

### 5. Create the baseline checkpoint

If that baseline evaluator run is legal and clean, the loop creates a local
checkpoint with:

- [checkpoint.py](/home/zhiyuzheng/Project/Agenticflow/OpenROAD-flow-scripts/evolve_agent/scripts/checkpoint.py)

The checkpoint id looks like:

- `<loop_id>__baseline`

This becomes the restore point for all later rejected attempts.

### 6. Build the Codex prompt for attempt 1

For attempt 1, the loop:

- restores the current best checkpoint
- reads the base design prompt
- appends loop-specific override text
- injects the current best metrics
- injects a compact memory excerpt from prior attempts

The prompt explicitly tells Codex:

- do one bounded patch only
- do not run evaluator
- do not manage checkpoints
- stop after the patch

So the outer Python loop remains in control of build, run, accept, and restore.

### 7. Launch Codex

The loop calls:

- [run_codex_exec.py](/home/zhiyuzheng/Project/Agenticflow/OpenROAD-flow-scripts/evolve_agent/scripts/run_codex_exec.py)

That script runs:

```bash
codex exec --json -C <repo_root> -o <codex_last_message.txt> -
```

and stores everything under a second operation directory:

- `evolve_agent/checkpoints/operations/<loop_id>__codex_attempt_01/`

For one attempt, the important files are:

- `codex_prompt.md`
- `codex_events.jsonl`
- `codex_stderr.log`
- `codex_last_message.txt`
- `codex_invocation.json`
- `codex_usage_summary.json`
- `README.md`

`codex_usage_summary.json` is the main structured artifact for Codex usage.

It records:

- `thread_id`
- `turn_count`
- `agent_message_count`
- `last_agent_message`
- `usage.input_tokens`
- `usage.cached_input_tokens`
- `usage.output_tokens`
- `returncode`
- `started_at`
- `finished_at`
- `elapsed_seconds`

### 8. Read Codex’s summary

After Codex returns, the loop reads:

- `codex_last_message.txt`

and extracts a compact mechanism summary from it. That summary is saved into the
attempt record and later into the experience journal.

### 9. Run the evaluator on the patched tree

The outer loop then runs the evaluator again, on the same:

- problem
- `FLOW_VARIANT`
- evolve line
- the clean default evolve engine

but with a fresh `run_tag`, for example:

- `gcd_example_run_attempt_01`

This second evaluator run produces:

- `attempt_01_eval.json`

inside the loop directory.

### 10. Score the patch

If the evaluator result is legal and complete, the loop builds a metric vector
from:

- `hpwl_delta_micron`
- `runtime_seconds`
- `peak_rss_bytes`
- `setup_ws`
- `setup_tns`
- `hold_ws`
- `hold_tns`

It computes a weighted composite score relative to the original baseline
metrics. The weights are defined at the top of
[run_design_evolve_loop.py](/home/zhiyuzheng/Project/Agenticflow/OpenROAD-flow-scripts/evolve_agent/scripts/run_design_evolve_loop.py).

Current default weights are:

- HPWL delta: `0.35`
- runtime: `0.20`
- peak RSS: `0.15`
- setup WNS: `0.10`
- setup TNS: `0.10`
- hold WNS: `0.05`
- hold TNS: `0.05`

### 11. Accept or reject

There are two branches.

If the patch improves the best score:

- a new accepted checkpoint is created
- the patched code becomes the new best state
- the loop stops immediately unless `--continue-after-improvement` is set

If the patch does not improve the score:

- the loop restores the previous best checkpoint
- the patch is discarded from the workspace

### 12. Update memory

After the decision, the loop appends:

- one JSON record to `experience_log.jsonl`
- one human-readable section to `experience_journal.md`
- one JSON record to `attempts.jsonl`

This is what lets later attempts avoid repeating the same rejected idea
blindly.

### 13. Write final loop state

At the end, the loop writes:

- `loop_state.json`
- `README.md`

These now include:

- `problem`
- `problem_path`
- `prompt_path`
- `flow_variant`
- `best_checkpoint`
- `best_score`
- `best_metrics`
- `stop_reason`
- `started_at`
- `finished_at`
- `elapsed_seconds`

## What the current `gcd` flow uses by default

If you run the example command above today, the default behavior is:

- case: `gcd / nangate45`
- prompt: [nangate45__gcd.md](/home/zhiyuzheng/Project/Agenticflow/OpenROAD-flow-scripts/evolve_agent/tasks/design_evolve/nangate45__gcd.md)
- evaluator line: `evolve_line`
- evolve family inside the evaluator: `default`
- build mode: `openroad_only`
- evaluation track: `strict`

So this loop is currently testing:

- one bounded patch on the clean evolve line
- compared against the current clean evolve baseline for the same case

It is not comparing directly against all four canonical baseline lines inside
the loop. Those canonical baselines are still available separately through:

- [run_canonical_line.sh](/home/zhiyuzheng/Project/Agenticflow/OpenROAD-flow-scripts/evolve_agent/scripts/run_canonical_line.sh)
- [run_baseline_suite.sh](/home/zhiyuzheng/Project/Agenticflow/OpenROAD-flow-scripts/evolve_agent/baseline/run_baseline_suite.sh)

## Example artifact layout

For a one-attempt run with:

- `--loop-id gcd_example_run`

you should expect these two local directories:

```text
evolve_agent/checkpoints/operations/
  gcd_example_run/
    baseline_eval.json
    attempt_01_eval.json
    attempts.jsonl
    experience_log.jsonl
    experience_journal.md
    loop_state.json
    README.md

  gcd_example_run__codex_attempt_01/
    codex_prompt.md
    codex_events.jsonl
    codex_stderr.log
    codex_last_message.txt
    codex_invocation.json
    codex_usage_summary.json
    README.md
```

And one new run directory under the chosen reusable `FLOW_VARIANT`:

```text
flow/reports/nangate45/gcd/<FLOW_VARIANT>/dpl_evolve_baseline/gcd_example_run_attempt_01/
  metrics.json
  ...
```

## What is currently recorded well

This flow now records clearly:

- Codex token usage
- Codex elapsed time per attempt
- evaluator build/run elapsed time
- accept/reject outcome
- checkpoint lineage
- best score and best metrics

## Current limitation to know

The loop currently defaults to the clean `evolve_line` with
`evolve_engine=default`. Project-level docs should still treat that as
implementation detail, not the main conceptual model. The conceptual model is
still:

- baseline lines
- clean evolve line
- family variants
- strict legalization-only comparison
