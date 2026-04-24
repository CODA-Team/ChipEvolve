# First Bounded Patch Protocol

This protocol is the minimal safe path for the first bounded mutation on the
negotiation legalizer.

## Scope

- target symbol:
  `dpl_evolve::NegotiationLegalizer::legalize()`
- target anchor:
  post-optimisation gate block around lines `269-277`
- validation track:
  `strict`

## Preconditions

Before changing behavior, confirm all of the following:

1. the repo builds with:
   `./build_openroad.sh --local`
2. the negotiation path has been verified with:
   `agent_setup_verify_negotiation`
3. the strict champion table is available:
   [strict_champion_table.md](../checkpoints/operations/strict_baseline_snapshot/strict_champion_table.md)
4. the packet and contract are current:
   - `evolve_agent/knowledge/packets/current_run_packet.md`
   - `evolve_agent/configs/mutation_contract.yaml`

## Step 0: no-op sanity patch

Do one tiny patch first:

- add a new optional gate or marker
- keep default behavior unchanged
- keep the gate default-off
- do not change legality, displacement, or HPWL

Purpose:

- validate patch surface
- validate build path
- validate evaluator and manifest plumbing

## Step 1: build

```bash
./build_openroad.sh --local
```

## Step 2: strict single-line validation

Run only the evolve negotiation line:

```bash
./evolve_agent/baseline/run_evolve_line.sh \
  --design-config ./designs/nangate45/gcd/config.mk \
  --flow-variant dpl_evolve_suite_20260422_125226 \
  --run-tag first_patch_negotiation_trial \
  --threads 8 \
  --engine negotiation
```

## Step 3: evaluate

```bash
python3 evolve_agent/adapters/science_codeevolve/evaluator.py \
  --problem evolve_agent/problems/gcd_nangate45/problem.yaml \
  --mode single \
  --line evolve_line \
  --flow-variant dpl_evolve_suite_20260422_125226 \
  --run-tag first_patch_negotiation_trial \
  --evolve-engine negotiation \
  --use-existing \
  --out evolve_agent/checkpoints/operations/first_patch_negotiation_trial/first_patch_negotiation_trial_eval.json
```

## Step 4: accept / reject rule

Keep the patch only if all are true:

- `engine_path_confirmed = negotiation`
- `legalization_status = ok`
- `placement_violations` stays empty
- `hpwl_delta_micron` improves or stays convincingly neutral
- `avg_displacement_micron` stays controlled
- runtime does not exceed the gate in
  [first_patch.yaml](../tasks/archive/first_patch.yaml)

Reject or revert if any are true:

- engine path falls back to `diamond_default`
- legality fails
- metrics are malformed or missing
- runtime or displacement regresses without a compensating benefit

## Step 5: only then consider broader comparison

Do not expand to reduced-flow or suite runs until the strict negotiation line
shows a clear, repeatable positive signal.
