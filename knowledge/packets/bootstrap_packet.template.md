# Bootstrap Packet Template

## Objective
Set up and verify the local control-plane / target-plane contract without changing legalization behavior.

## Read First
- evolve_agent/AGENTS.md
- evolve_agent/configs/mutation_contract.yaml
- evolve_agent/knowledge/stage_context/detail_place_stack.yaml

## Allowed Scope
- control plane files under `evolve_agent/`
- target-plane metadata only if needed for path correction
- no algorithmic changes to legalizer behavior

## Required Actions
1. Verify local repo paths and script entrypoints.
2. Verify exact build command and exact baseline wrapper invocation.
3. Patch `evaluator.py` and skill docs to match local CLI.
4. Produce one successful dry-run manifest.

## Success
- build command is validated
- one baseline run completes
- `metrics.json` is found
- `run_manifest.yaml` is emitted
