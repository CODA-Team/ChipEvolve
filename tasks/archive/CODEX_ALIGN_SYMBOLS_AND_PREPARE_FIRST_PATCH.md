# CODEX TASK: Align Symbol Cards to the Local Repo and Prepare the First Bounded Patch

## Goal
Align the knowledge layer to the **actual local code symbols** and prepare the repo for the first strict-track legalizer patch.

## Scope
You may edit:
- `evolve_agent/knowledge/**`
- `evolve_agent/adapters/science_codeevolve/patch_surface.py` or YAML equivalent
- target-plane code **only for behavior-preserving seam extraction**, if truly necessary

## Read first
- `evolve_agent/configs/mutation_contract.yaml`
- `evolve_agent/knowledge/symbol_cards/*.yaml`
- `evolve_agent/knowledge/seam_design/seams_v1.yaml`
- `evolve_agent/knowledge/delta_ledger/nblg_to_openroad.yaml`
- `evolve_agent/knowledge/delta_ledger/legalm_to_openroad.yaml`

## Required work
1. Inspect local files:
   - `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizer.cpp`
   - `tools/OpenROAD/src/dpl_evolve/src/Opendp.cpp`
   - `tools/OpenROAD/src/dpl_evolve/src/Opendp.tcl`

2. For each symbol card:
   - replace locator hints with the exact local function / command name
   - add exact signature if visible
   - add line-range or anchor hints if helpful
   - mark cards as `aligned: true`

3. Update patch surface:
   - restrict it to the exact local symbols/functions that exist
   - keep the initial scope bounded

4. Decide whether one small seam extraction is required before mutation.
   - If the code is too monolithic, extract **at most one** seam from `seams_v1.yaml`
   - The extraction must be behavior-preserving and separately testable

5. Produce a recommendation for the first patch:
   - chosen file
   - chosen symbol
   - chosen patch mode
   - chosen mutation playbook family
   - expected metric movement
   - main risk

## Acceptance criteria
- symbol cards match the local repo
- patch surface reflects real symbols, not guesses
- seam extraction (if any) is behavior-preserving
- a first-patch recommendation note exists

## Deliverables
- updated symbol cards
- updated patch surface
- optional one-seam extraction patch
- `first_patch.md`
