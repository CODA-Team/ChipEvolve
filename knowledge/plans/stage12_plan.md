
# dpl_evolve: Stage 1–2 plan
## Goal
Use legalization as the first OpenROAD self-evolving code-level evolution target. The primary optimization target is legalization-stage wirelength perturbation / post-legalization HPWL, with legality as a hard gate and displacement/runtime as secondary metrics.

## Why legalization first
- The current OpenROAD `dpl` already exposes multiple runtime-selectable legalization engines and developer-facing commands.
- ORFS already isolates detailed placement as a stage (`detail_place.tcl`), making it possible to stop at a stable handoff point and compare legalizers under controlled inputs.
- The docs show that the current DPL supports **two engines**: the default **diamond search** engine and an optional **NegotiationLegalizer** based on **NBLG**, enabled by `-use_negotiation`; the NegotiationLegalizer can optionally enable an **Abacus pre-pass** via `-abacus`.
- This means we can build a clean baseline ladder before doing any code evolution.

## Repo reality to build around
### OpenROAD `dpl`
Relevant current files in `src/dpl/src/`:
- `Opendp.cpp`, `Opendp.tcl`
- `Optdp.cpp`
- `NegotiationLegalizer.cpp`, `NegotiationLegalizerPass.cpp`
- `CheckPlacement.cpp`
- `OptMirror.cpp`
- `PlacementDRC.cpp`
- `Opendp-py.i`, `Opendp.i`

### OpenROAD `rsz`
Relevant current files in `src/rsz/src/`:
- `RepairDesign.cc`, `RepairSetup.cc`, `RepairHold.cc`, `RecoverPower.cc`
- `Resizer.tcl`
- move/operator files such as `BufferMove.cc`, `CloneMove.cc`, etc.

### ORFS coupling
The current ORFS placement stack is:
1. `global_place.tcl`
2. `resize.tcl`
3. `detail_place.tcl`
4. `repair_timing_post_place.tcl`

For the primary legalization baseline, use the **flow-faithful handoff**:
- input ODB: `3_4_place_resized.odb`
- legalizer stage: `detail_place.tcl`

Optional isolation handoff for ablation:
- input ODB: `3_3_place_gp.odb`
- purpose: compare “pure legalizer” vs “legalizer after place-opt / RSZ-assisted preconditioning”.

## Stage 1 — Baseline plan
### Baseline ladder
#### B0. OpenROAD default DPL (diamond search)
- ORFS default `detail_place.tcl`
- `USE_NEGOTIATION=0`
- no code changes
- purpose: reference OpenROAD baseline

#### B1. OpenROAD NegotiationLegalizer
- `USE_NEGOTIATION=1`
- purpose: current in-tree NBLG-derived legalizer baseline

#### B2. OpenROAD NegotiationLegalizer + Abacus pre-pass
- `USE_NEGOTIATION=1`
- pass `-abacus` through `DETAIL_PLACEMENT_ARGS`
- purpose: in-tree hybrid baseline

#### B3. External DREAMPlace Abacus bridge
- do **not** replace the OpenROAD flow
- export one legalization snapshot from OpenROAD and run DREAMPlace Abacus as an external comparator
- re-import legalized coordinates into OpenDB / DEF for metric comparison
- purpose: apples-to-apples external legalizer comparison in one repo

#### B4. Evolved legalizer (later)
- new `dpl_evolve` engine or patch set
- compared against B0/B1/B2/B3

### Baseline metrics
Primary:
- post-legalization HPWL
- ΔHPWL from pre-legalization input
Secondary:
- average displacement
- maximum displacement
- legality / overlap-free check
- row/site alignment
- fence / region validity where applicable
- runtime
Optional later:
- routed WL impact
- detailed routing violations
- pin access / edge spacing proxies

### Baseline input and outputs
#### Primary benchmark handoff
Input:
- `3_4_place_resized.odb`
- `2_floorplan.sdc`

Output:
- legalized ODB / DEF
- metrics JSON
- per-cell displacement CSV
- optional cell-level before/after coordinate dump

### Recommended first benchmark modes
1. real ORFS mode: `3_4_place_resized.odb -> detail_place`
2. isolated mode: `3_3_place_gp.odb -> custom legalization runner`
3. small fast regression mode:
   - 1–2 small designs for code/debug loop
4. design-specific mode:
   - later, once the engine is stable

### Baseline execution scripts to prepare
- `dpl_evolve/baseline/run_openroad_negotiation.sh`
- `dpl_evolve/baseline/run_or_nblg.sh`
- `dpl_evolve/baseline/run_or_nblg_abacus.sh`
- `dpl_evolve/baseline/run_dreamplace_bridge.py`
- `dpl_evolve/baseline/collect_metrics.py`
- `dpl_evolve/baseline/dump_placement_snapshot.tcl`
- `dpl_evolve/baseline/import_legalized_coords.tcl`

### Important implementation note
Because OpenROAD’s design philosophy is “one tool, one process, one database”, the long-term in-tree engine should prefer OpenDB-native integration rather than loose file-based glue. But for the **first external comparator baseline**, a Python/DEF bridge is acceptable if it reduces startup cost.

## Stage 2 — Knowledge base plan
The knowledge base should not be “paper summaries”; it should be **algorithm cards** that map paper ideas to:
1. objective terms
2. constraints
3. move / search policies
4. hyperparameters
5. code touch points in OpenROAD
6. design regimes where the idea is likely useful
7. expected failure modes
8. validation rules

### Knowledge schema
Each card should have:
- `name`
- `source`
- `problem_scope`
- `objective_terms`
- `hard_constraints`
- `soft_constraints`
- `initialization_strategy`
- `candidate_generation`
- `cost_function`
- `move_policy`
- `ordering_policy`
- `region_policy`
- `history_or_multiplier_schedule`
- `post_optimization`
- `parallelization`
- `design_regime`
- `openroad_mapping`
- `low_risk_mutations`
- `high_risk_mutations`
- `telemetry_needed`
- `hard_gates`

## Paper-to-algorithm mapping
### 1) Current OpenROAD DPL (repo knowledge)
#### What exists already
- default **diamond search** legalizer
- optional **NegotiationLegalizer**
- optional **Abacus pre-pass** inside NegotiationLegalizer
- `improve_placement`
- `optimize_mirroring`
- developer/debug commands

#### Why this matters
You are not adding legalization to OpenROAD from scratch. You are evolving an existing stack with:
- a simple default baseline,
- an in-tree NBLG-like engine,
- an in-tree Abacus hybrid mode.

This reduces the barrier to code evolution and makes ablations cleaner.

### 2) NBLG card
Core idea:
- formulate legalization as a **resource allocation task** on placement-site grids.
- use a negotiation-style iterative rip-up and relocate process.

High-value ideas to reuse:
- negotiation object = cell
- negotiation cost = displacement target cost + history cost × penalty
- adaptive penalty `pf`
- isolation point `I`
- local surrounding search window, but allow accumulated movement across iterations
- negotiation order based on overflow / cell size
- post-optimization = greedy search + cell swapping
- deterministic multithreading by region partitioning

Mapping to current OpenROAD:
- `NegotiationLegalizer.cpp` / `NegotiationLegalizerPass.cpp`
- possible extensions:
  - better ordering policy
  - adaptive penalty schedule
  - dynamic window policy
  - stronger post-optimization
  - multithreaded negotiation

Most promising design-specific knobs:
- search-window geometry
- history cost update rate
- isolation threshold
- overflow-based ordering
- tradeoff weight on max displacement vs average displacement vs WL perturbation

### 3) LEGALM 2.0 card
Core idea:
- formulate mixed-height legalization with a **linearized augmented Lagrangian** objective.
- optimize displacement while eliminating overflow through multiplier updates.

High-value ideas to reuse:
- scanline-based initial legalization
- weighted average displacement + max displacement objective
- overflow as an explicit constrained signal
- linearized projected gradient cost
- routability penalty term
- connectivity-based local optimum escape
- refinement stage with no-overflow hard constraint
- triplefold/block partitioning for parallel updates

Mapping to OpenROAD:
Short-term, use as a **knowledge donor**, not a full transplant.
Best low-risk transfers:
- better initialization
- overflow-aware cost augmentation
- local optimum escape heuristics
- separate refinement pass after legality
- better partition / candidate region policies

High-risk transfers:
- full ALM/BGD engine
- full GPU path
- full mixed-height + hybrid-region machinery

### 4) DREAMPlace Abacus card
Core idea:
- expose an **Abacus legalizer operator** callable from Python/C++.
- input consists of reference position + current position + geometry + region metadata.

Why it matters:
- gives an external, self-contained comparator
- easy to bridge through Python for a first experiment
- provides an alternative “row-compaction + clustering” behavior different from current OpenROAD diamond/NBLG modes

Mapping:
- first as an external baseline through `dpl_evolve/dreamplace_bridge`
- later, selected Abacus-like ideas can be internalized

## Proposed `dpl_evolve/` scaffold
dpl_evolve/
  README.md
  baseline/
    run_openroad_negotiation.sh
    run_or_nblg.sh
    run_or_nblg_abacus.sh
    run_dreamplace_bridge.py
    collect_metrics.py
    dump_placement_snapshot.tcl
    import_legalized_coords.tcl
  knowledge/
    openroad_repo_map.md
    algorithm_cards/
      openroad_dpl.md
      nblg.md
      legalm2.md
      dreamplace_abacus.md
    schemas/
      algorithm_card_template.yaml
      design_feature_schema.yaml
  adapters/
    odb_export/
    dreamplace_bridge/
  experiments/
    configs/
    logs/
    metrics/
  patches/
    candidates/
    accepted/
  notebooks/
  docs/

## Recommended immediate next step after Stage 1–2
1. Make B0/B1/B2 reproducible inside ORFS.
2. Dump one stable legalization snapshot (`3_4_place_resized.odb`).
3. Build B3: external DREAMPlace Abacus comparator.
4. Freeze metrics and file formats.
5. Only then start agent-facing prompt/tool design.
