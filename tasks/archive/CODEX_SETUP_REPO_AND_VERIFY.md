# CODEX TASK: Set Up the Local Repo Contract and Verify the Control Plane

## Goal
Make the current local repo runnable under the three-plane architecture **without changing legalization behavior**.

## Scope
You may edit:
- `evolve_agent/**`
- target-plane metadata/docs only if a path fix is needed

You must **not** make algorithmic changes to:
- `tools/OpenROAD/src/dpl_evolve/src/*.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/Opendp.tcl`

## Inputs
Read these first:
- `evolve_agent/AGENTS.md`
- `evolve_agent/configs/mutation_contract.yaml`
- `evolve_agent/configs/run_manifest.template.yaml`
- `evolve_agent/knowledge/stage_context/detail_place_stack.yaml`
- `evolve_agent/skills/build_openroad.md`
- `evolve_agent/skills/run_single_baseline.md`
- `evolve_agent/skills/evaluate_run.md`

## Required work
1. **Path verification**
   - Verify that the current local repo matches:
     - target plane: `tools/OpenROAD/src/dpl_evolve`
     - control plane: `evolve_agent`
     - artifact plane: `flow`
   - If a local path differs, update only control-plane references.

2. **Build verification**
   - Read the local build wrapper / documentation.
   - Determine the exact build command for OpenROAD in this repo.
   - Update `evolve_agent/skills/build_openroad.md` and `evolve_agent/adapters/science_codeevolve/evaluator.py` so both use the same command.

3. **Baseline verification**
   - Read the local baseline wrapper scripts under `evolve_agent/baseline/`.
   - Determine the exact CLI for:
     - one single baseline run
     - the baseline suite run
   - Update the relevant skill docs and `evaluator.py`.

4. **Metrics and artifact verification**
   - Run one baseline dry run on the default problem (prefer the smallest stable design already defined locally).
   - Confirm the exact paths for:
     - logs
     - reports
     - results
     - `metrics.json`
   - Emit a filled `run_manifest.yaml` under `evolve_agent/checkpoints/operations/<checkpoint_id>/`.

5. **Packet verification**
   - Run `kb_query.py` for the default problem.
   - Confirm that a packet is generated under `evolve_agent/knowledge/packets/`.

## Acceptance criteria
- OpenROAD build command is validated.
- One baseline dry run completes successfully.
- `metrics.json` is found and readable.
- A concrete `run_manifest.yaml` is emitted inside one operation directory.
- No algorithmic/legalizer behavior change has been introduced.

## Deliverables
- updated `evaluator.py`
- updated skill docs if needed
- one dry-run manifest
- a brief note listing the exact local commands discovered
