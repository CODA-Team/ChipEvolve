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
- Diamond reference baseline: `$openroad_diamond`
- negotiation donor: `$openroad_negotiation_nblg`
- Abacus donor: `$dreamplace_abacus`
- evolved legalizer patch catalog: `$evolved_legalizers_readme`
- evolved legalizer manifest: `$evolved_legalizers_manifest`
- evolved legalizer validation: `$evolved_legalizers_validation`
- dense evolved-legalizer routing insight: `$dense_legalizer_routing_insight`
- Teacher coaching skill: `$teacher_coaching_skill`

Use these paths as precise search handles. Do not require broad source or donor
tree reading; cite exact functions/state only when they are useful insertion
points.

## Objective

- canonical metric: `metrics.json:hpwl` from OpenROAD/DPL pin-based logs
- ignore `hpwl_proxy` for promotion
- research belief: clean canonical HPWL at least 5% below the best clean
  canonical line is achievable, but 5% is not a hard gate and not a ceiling
- Teacher stance: assume there is real optimization space at and beyond 5%
  until the evidence proves otherwise. Explain where that space may come from
  before assigning students.
- route design stance: convert the 5% belief into at least one concrete
  explore/aggressive route per round.  That route should widen or reshape a
  bounded search space, not merely retune a small donor.
- plateau stance: when the best result repeats or only improves by a tiny
  amount, do not overfit the next round to that donor's local repair knobs.
  Keep the donor as a guardrail, but deliberately search for a new large HPWL
  source in the stage interaction, objective, candidate generator, or data
  structure.
- per-iteration target: discover mechanisms that move toward or beyond that 5%
  research target;
  compare `openroad_dpl_flow`, `openroad_dpl_negotiation`, and
  `evolve_default` together, and treat sub-1% wins as donor evidence rather
  than success
- runtime budget is a usable resource. The generated DPL flow runner kills only
  the OpenROAD legalize/improve/mirror flow at ${student_runtime_multiplier}x
  the canonical `openroad_dpl_flow` reported runtime from
  `metrics.json:runtime_seconds`; metrics/evaluator collection is not
  timeout-wrapped. Students should use that budget to explore stronger bounded
  donors and mechanisms.
- runtime tiers: `fast` is near-baseline donor preservation, `explore` spends
  moderate extra runtime on a bounded stronger search, and `aggressive` spends
  a larger but timeout-safe budget on a mechanism that could materially change
  final HPWL.  Do not interpret all runtime growth as bad; judge whether the
  extra time is useful bounded search or wasted repetition.
- report runtime for the full evaluated flow:
  `detailed_placement_evolve -> improve_placement_evolve -> optimize_mirroring_evolve`.
  Do not call this pure algorithm-internal time.
- high-performance requirement: do not pursue tiny incremental wins through
  endpoint stacking, repeated random tails, or broad rescans.  Prefer bounded
  structural mechanisms that can plausibly reach or exceed the 5% research
  target.
- use the available runtime budget for stronger bounded mechanisms: deeper
  legalizer scoring, broader capped candidate search, better donor
  hybridization, or a stronger legalization/improve-placement handoff. The
  constraint is bounded complexity and canonical metric proof, not matching
  baseline runtime.
- under-exploration signal: repeated near-baseline runtime with only sub-1%
  HPWL gains means the loop is probably preserving donors rather than testing
  a large source mechanism.  Assign at least one route to spend more of the
  available budget on a cached/capped/parallel search with stage-wise proof.
- high-performance exploration may use parallel candidate evaluation, OpenMP,
  thread-local scratch buffers, and deterministic reductions when the work is
  independent and the result remains reproducible. Spend threads on deeper
  bounded search or more accurate local HPWL scoring, not on repeated unchanged
  endpoint runs.
- callable flow: `detailed_placement_evolve -> improve_placement_evolve -> optimize_mirroring_evolve`
- editable patch surface for this track: source-level
  `detailed_placement_evolve` and `improve_placement_evolve`, including their
  internal algorithm flow, endpoint sequencing, candidate generation,
  parameterization, and handoff state. External evaluator/ORFS/workspace helper
  scripts are locked.
- optimize mirroring remains a downstream evaluation pass, but current evidence
  shows too little headroom to make it a Student patch target.  Do not assign
  downstream optimize-mirroring edits unless a future task explicitly reopens that scope.
- final HPWL depends mainly on legalization/improve-placement interaction for
  this track. Useful changes should create and consume stage handoff state
  rather than betting all quality on one isolated stage.
- required Student skills for ordinary source edits:
  `skills/patch_rules.md`, `skills/source_git_workflow.md`,
  `skills/build_openroad.md`, `skills/evaluate_run.md`, and
  `skills/trace_logging.md` when counters/logs are needed
- generated Student workspace scripts are the normal way to prepare source,
  build, evaluate, commit, and export diffs; Teacher should not ask Students to
  reconstruct CMake, relink, evaluator, git, or diff commands
- this generated packet is self-contained for the Teacher task. Do not open
  `~/.codex/memories`, rollout summaries, child event logs, or session archives
  during planning. Use only this packet, the listed knowledge/insight files,
  peer-learning packet, canonical metrics, and targeted source handles.
- Diamond/openroad_dpl_flow, negotiation, and evolve_default are all valid
  donor/start-point evidence. Students may explore any of them, but should
  explain the source behavior they reuse or change. Do not buy quality by
  rerunning unchanged improve placement from outside; improve placement itself,
  including its internal source-level flow and endpoint policy, is an editable
  research stage.
- Evolved legalizer patches under `patches/evolved_legalizers/` are active
  donor/start-point evidence, not stale backups. `evolved_diamond`,
  `evolved_legalm`, and `evolved_negotiation` are prior iter30 donor starts
  with measured wins on some archetypes. Teacher should decide whether a
  student should start from the clean route seed, start from a prepared local
  evolved start branch, or use another start kind while borrowing a specific
  evolved mechanism, and should justify that choice with current stage evidence.
- Patch base matters. `*_from_clean.patch` applies to the clean OpenROAD anchor
  recorded in `metadata/anchors.json`; `*_framework_delta.patch` applies only
  after `openroad_dpl_evolve_base.patch` and
  `openroad_dpl_evolve_framework.patch`. Student private source trees are
  normally produced from materialized seed sources, not by manually applying
  OpenROAD-root patches during a round.

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
- do not include memory citations, shell/build/eval/git command blocks, or
  long file inventories in the Teacher plan. The Student workspace packet owns
  execution procedure and exact command paths.
