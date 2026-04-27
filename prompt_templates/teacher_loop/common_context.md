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

## Objective

- anchors: `openroad_dpl_flow`, `evolve_default`
- primary target: strict legal HPWL better than `openroad_dpl_flow`
- runtime may rise if HPWL gain is meaningful and displacement is explainable
- editable flow: `detailed_placement_evolve -> improve_placement_evolve -> optimize_mirroring_evolve`

## Build Contract

- students edit only private variant `dpl_evolve` source
- students relink a private OpenROAD binary
- do not edit evaluator, benchmark selection, root ORFS source, or classic `dpl`

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
- output algorithmic insight, peer learning, and risk controls
