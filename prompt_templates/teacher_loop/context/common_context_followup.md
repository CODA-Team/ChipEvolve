# Round Context Follow-Up

This is a delta context for `$iteration_name`. Use session memory for stable
global rules from the first iteration. Do not reread broad context top-to-bottom;
open only the current evidence or knowledge handles needed for the next
mechanism decision.

- case: `$case_id`
- flow_variant: `$flow_variant`
- threads: `$threads`
- start_kind: `$start_kind`
- round_id: `$round_id`
- packet: `$packet_path`

## Current Objective

- Promote only legal candidates by final `metrics.json:hpwl`.
- Runtime is a `$student_runtime_multiplier`x hard budget and an analysis
  signal. `G_HR` explains whether an HPWL gain is worth its runtime; it is not
  the elite selector.
- Search source-level mechanisms in detailed placement/legalization and
  improve-placement/DPO. Source-internal parameter schedules are allowed; Tcl,
  ORFS, evaluator, and baseline-script tuning are not.
- If a live/correct mechanism has extremely small full-flow HPWL movement after
  a meaningful repair attempt, preserve it as `validated-low-ROI` evidence and pivot
  to a different HPWL source.

## Current Evidence

$design_characteristics

Detailed design packet: `$design_characteristics_path`

## Scoreboard

$scoreboard

## Elite Continuation

$elite_text

## New Or Recently Useful Pointers

- start calibration: `$start_seed_calibration_path`
- peer learning: `$peer_learning_path`
- feature-to-mechanism strategy insight: `$strategy_inspiration_insight`
- DPO mechanism insight: `$dpo_source_mechanisms_insight`
- OpenROAD-native handoff insight: `$openroad_native_handoff_insight`
- skill query: `python3 $skill_query_script --stage <stage> --q "<bottleneck or mechanism>"`
- algorithm cards: `$algorithm_cards_dir`

For Diamond/negotiation/LEGALM/Differential Guidance mixtures, query
`--stage legalization --q "diamond negotiation differential guidance liveness"`
and explicitly separate primary legalizer, guidance producer, repair/polish,
and handoff consumer roles.

Use at most a few targeted `rg`/excerpt reads around the selected stage,
mechanism, and source symbols. Pseudocode cards are inspiration contracts, not
case-level algorithm selectors.

## Prior Iteration Delta

$prior_context

## Teacher Boundary

Output only the next routing/review decision and concise per-student mechanism
guidance. The Student workspace packet owns commands and exact helper paths.
