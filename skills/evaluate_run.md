# Skill: evaluate_run

Use this when you are responsible for running or reading evaluator output.
Loop-driven patching agents normally should not run evaluation themselves.

## Guarded Evaluator

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/adapters/science_codeevolve/evaluator.py" \
  --case gcd_nangate45 \
  --mode single \
  --line evolve_default \
  --flow-variant <FLOW_VARIANT_WITH_3_4_PLACE_RESIZED_ODB> \
  --run-tag <RUN_TAG> \
  --skip-build \
  --openroad-binary "${OPENROAD_BINARY}" \
  --out "${DPL_EVOLVE_STATE_ROOT}/checkpoints/operations/<RUN_TAG>/eval.json"
```

For variant/family runs, always pass `--openroad-binary`.

## Status

Read `status` first:

- `ok`: metrics were produced.
- `dry_run`: command construction only.
- `locked`: another run owns the same output directory.
- `build_failed`: build step failed.
- `run_failed`: evaluator run failed.
- `missing_artifact`: expected output was absent.

If status is not `ok`, read `command_results.*.stderr_tail` and
`command_results.*.stdout_tail`.

## Primary Result

```text
flow/reports/<platform>/<design>/<FLOW_VARIANT>/dpl_evolve_baseline/<run_tag>/metrics.json
```

Compare these first:

- legality
- HPWL delta
- setup WNS/TNS
- displacement
- runtime
- memory, when recorded

## Strict Track Rule

Strict legalization-only runs require an existing:

```text
flow/results/<platform>/<design>/<FLOW_VARIANT>/3_4_place_resized.odb
```

The wrapper reuses this snapshot and should not rebuild upstream placement.

## Keep / Reject

Keep only if:

- legality is clean
- HPWL/timing/runtime frontier improves or clearly moves in the right direction
- displacement remains controlled

Reject if:

- legality fails
- `metrics.json` is missing or malformed
- runtime/displacement regresses without a clear offsetting gain
