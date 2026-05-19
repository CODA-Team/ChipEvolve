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
- Search variables include branch/start choice, mechanism order, guidance or
  differential objective terms, heuristic weights, stop/activation policy,
  internal parameters, handoff payload, DPO scoring, and accept/rollback rules.
  Use logs and stage-wise evidence to choose which variable changes next.
- If a live/correct mechanism has extremely small full-flow HPWL movement after
  a meaningful repair attempt, preserve it as `validated-low-ROI` evidence and pivot
  to a different HPWL source.
- Follow-up rounds should use the first-round global route map as memory, then
  read less and optimize the current case more sharply. Keep donor scope clear:
  `general donor` for guard/reusable kernels, `feature-matched donor` for
  mechanisms selected because this specific design feature suggests upside.
- If the next decision needs a new feature-matched start kind or case-type
  route, open the case-type quality route insight first, then refine from
  current-run evidence.

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
- case-type quality route insight: `$case_type_quality_mechanism_insight`
- DPO mechanism insight: `$dpo_source_mechanisms_insight`
- OpenROAD-native handoff insight: `$openroad_native_handoff_insight`
- skill query: `python3 $skill_query_script --stage <stage> --q "<bottleneck or mechanism>"`
- algorithm cards: `$algorithm_cards_dir`

For Diamond/negotiation/LEGALM/Differential Guidance mixtures, query
`--stage legalization --q "diamond negotiation differential guidance liveness"`
and explicitly separate primary legalizer, guidance producer, repair/polish,
and handoff consumer roles.
Differential guidance objectives can be heuristic: when counters show no useful
moves, no frontier consumer, or DPO-hostile states, change the target
terms/weights, stop point, payload, or consumer instead of only repeating the
same objective.

Use at most a few targeted `rg`/excerpt reads around the selected stage,
mechanism, and source symbols. Pseudocode cards are inspiration contracts, not
case-level algorithm selectors. Current metrics/logs/source evidence override a
card when they conflict.

If current-run legal candidates show tiny HPWL movement, repeat the same family,
or incur runtime cost without proportional HPWL, treat it as weak-gain/over-cost
evidence. Keep a guard donor if useful, but route from the observed failure
mode: use at most one broader stage/mechanism query or card to identify a
different source-level hypothesis, then assign at least one stronger within-run
route. Current-run kept/rejected refs may be repaired with
`25_trial_source.sh begin --from-ref <ref>`; do not import cross-experiment
donors or historical results as implementation starts.
Before assigning a heavy donor, query
`--stage teacher_review --q "runtime light final HPWL mechanism priority"` and
prefer a lighter final-HPWL mechanism unless the stage evidence justifies the
extra runtime.

Do not over-optimize for universal donors in follow-up rounds. The target is
the best legal final HPWL for this specific case under the runtime gate; transfer
evidence is a secondary classification.

## Prior Iteration Delta

$prior_context

## Teacher Boundary

Output only the next routing/review decision and concise per-student mechanism
guidance. The Student workspace packet owns commands and exact helper paths.
