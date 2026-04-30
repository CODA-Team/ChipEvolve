# Round Context

- case: `$case_id`
- flow_variant: `$flow_variant`
- threads: `$threads`
- start_kind: `$start_kind`
- round_id: `$round_id`
- iteration: `$iteration_name`
- packet: `$packet_path`

## Sources

- evolved source: `$dpl_evolve_src`
- LEGALM reference: `$legalm_guidance`
- Diamond donor: `$openroad_diamond`
- negotiation donor: `$openroad_negotiation_nblg`
- Abacus donor: `$dreamplace_abacus`
- Teacher coaching skill: `$teacher_coaching_skill`

## Objective

- canonical metric: `metrics.json:hpwl` from OpenROAD/DPL pin-based logs
- ignore `hpwl_proxy` for promotion
- final target: clean canonical HPWL at least 5% below `openroad_dpl_flow`
- Teacher stance: assume there is real 5% optimization space until the evidence
  proves otherwise.  The baseline is a reference point, not a ceiling.  Explain
  where that space may come from before assigning students.
- per-iteration target: discover mechanisms that move toward that 5% goal;
  treat `evolve_default` as an internal anchor/donor when useful, and treat
  sub-1% wins as donor evidence rather than success
- runtime does not need to match baseline.  It only needs to remain acceptable
  for the case and be justified by clear HPWL improvement or useful algorithmic
  evidence.  Avoid unbounded scans and uncontrolled complexity.
- editable flow: `detailed_placement_evolve -> improve_placement_evolve -> optimize_mirroring_evolve`
- every valid student attempt should change legalization, improve placement,
  and mirror/orientation; stage coordination is optional and should be used only
  when it improves quality or runtime

## Design Characteristics

$design_characteristics

Detailed packet: `$design_characteristics_path`

## Baseline Evidence

$metric_table

## Scoreboard

$scoreboard

## Elite Continuation

$elite_text

## Packets

- baseline artifacts: `$baseline_artifacts_path`
- peer learning: `$peer_learning_path`

## Prior Context

$prior_context

## Teacher Boundary

- output insight and per-student plans only
- do not ask students to chase optional reports that may not exist; use the
  generated packets, canonical `metrics.json:hpwl`, DPL logs, and artifacts
  listed in the packets
