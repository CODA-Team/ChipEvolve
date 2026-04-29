# Teacher Context

- case: `$case_id`
- flow_variant: `$flow_variant`
- threads: `$threads`
- start_kind: `$start_kind`
- round_id: `$round_id`
- iteration: `$iteration_name`
- ORFS root: `$orfs_root`
- agent root: `$agent_root`
- state root: `$state_root`
- packet: `$packet_path`

## Code References

- evolved framework: `$dpl_evolve_src`
- LEGALM guidance: `$legalm_guidance`
- Diamond donor: `$openroad_diamond`
- NBLG/negotiation donor: `$openroad_negotiation_nblg`
- DREAMPlace/Abacus donor: `$dreamplace_abacus`
- Teacher peer-coaching skill: `$teacher_coaching_skill`

## Objective

- anchors: `openroad_dpl_flow`, `evolve_default`
- primary target: strict legal HPWL better than `openroad_dpl_flow`
- runtime may rise if HPWL gain is meaningful and displacement is explainable
- editable flow: `detailed_placement_evolve -> improve_placement_evolve -> optimize_mirroring_evolve`
- every student attempt should modify legalization, improve placement, mirror,
  and the cross-stage handoff/objective connecting them
- goal: discover transferable code-change knowledge for large HPWL gains, not
  only preserve micro-gains

## Current Research Bias

- prefer large, explainable HPWL improvements; preserve micro-gains only as donors
- convert strong slow donors into faster algorithms using incremental metrics,
  dirty legality, sparse snapshots, predictors, checkpointing, or parallelism
- high-utilization failures usually need earlier flow/objective/assignment changes

## Design Characteristics

$design_characteristics

Detailed packet: `$design_characteristics_path`

## Build Contract

- students edit only private variant `dpl_evolve` source
- students relink a private OpenROAD binary
- do not edit evaluator, benchmark selection, root ORFS source, or classic `dpl`
- valid student attempts should produce a substantial diff across the evolved
  legalization, detailed improve, mirror/orientation, and shared flow-control
  surfaces

## Current Baseline Evidence

$metric_table

## Round Scoreboard

$scoreboard

## Elite Continuation

$elite_text

## Generated Baseline Artifacts

`$baseline_artifacts_path`

## Peer Learning Packet

`$peer_learning_path`

## Prior Iteration Context

$prior_context

## Teacher Boundary

- missing canonical baseline means no promotion decision
- do not print shell commands or private paths in Teacher output
- output algorithmic insight, peer learning, and complexity requirements
