# Skill: patch_rules

## Principle

Codex edits only the bounded `dpl_evolve` framework surface unless a task
explicitly expands the scope.  The current Teacher/Student loop optimizes two
active responsibilities: legalization/detailed placement and improve
placement.  `optimize_mirroring_evolve` must remain callable but is not an
active optimization target in this track.

## Preferred Surfaces

In Student rounds, `private_dpl_evolve_source` is already the `dpl_evolve`
module root. Do not append `tools/OpenROAD/src/dpl_evolve` under it. Use these
module-relative paths:

- `src/EvolveLegalizer.cpp`
- `src/EvolveLegalizer.h`
- `src/EvolveContext.h`
- `src/EvolveTelemetry.h`
- `src/StudentAlgorithm.cpp`
- LEGALM-stage files under `src/Legalm*.{h,cpp}`
- detailed-improvement and objective files under
  `src/optimization/` and `src/objective/`
- `src/Optdp.cpp`
- existing `src/Place.cpp` or
  `NegotiationLegalizer*` files only when borrowing a specific donor mechanism.

Do not edit classic `tools/OpenROAD/src/dpl/`.

## Reference Inputs

Reference inputs are optional and must be opened only through absolute paths
provided by the workspace packet or Teacher plan.  `private_dpl_evolve_source`
is a source-only git repo and does not contain `family_variants/`.

If donor evidence is needed, use repo-root references such as:

- `<agent_root>/knowledge/index/skill_cards.jsonl`
- `<agent_root>/knowledge/skills/`
- `<agent_root>/scripts/query_knowledge.py`
- `<agent_root>/family_variants/REFERENCE_INDEX.yaml`
- `<agent_root>/family_variants/legalm_guidance/README.md`
- `<agent_root>/family_variants/openroad_diamond/README.md`
- `<agent_root>/family_variants/openroad_negotiation_nblg/README.md`
- `<agent_root>/family_variants/openroad_negotiation_nblg/mechanism_deltas/`
  only when assigned to negotiation-history mechanisms.
- `<agent_root>/patches/evolved_legalizers/README.md`
- `<agent_root>/patches/evolved_legalizers/generation_manifest.tsv`
- `<agent_root>/patches/evolved_legalizers/validation.tsv`
- `<agent_root>/patches/evolved_legalizers/openroad_dpl_evolve_*_iter30_framework_delta.patch`
- `<agent_root>/knowledge/insights/dpo/source_level_mechanisms.md`

If an absolute donor path is missing, skip it and continue from Teacher-named
source symbols. Do not search for donor files relative to the private source
repo.
Use the generated `08_query_knowledge.sh` helper when Teacher names a LEGO-lite
skill id. Open only the matching skill note and current source handles; do not
bulk-read all skill records.
Do not broad-read external archives or ignored local backups unless the task
explicitly asks for old family-flow evidence.
Do not open `~/.codex/memories`, rollout summaries, checkpoint event logs, or
old transcripts during ordinary Student source edits. The generated Teacher
packet and repo-local knowledge files are the evidence boundary.

## DPO Mechanism Use

- Improve-placement mechanisms belong in the current private source, especially
  `src/Optdp.cpp`, `src/optimization/`, `src/objective/`, and compact handoff
  structs.
- Useful mechanism families include bounded source-edge scoring, top-K exact
  candidate reduction, transaction accept/rollback, selective fallback
  descent, scoped LSMC-style basin escape, and legalization-to-DPO handoff
  consumers.
- Implement only the selected mechanism, with compact counters/logs, bounded
  candidate sets, exact affected-net scoring, and full-flow validation. LSMC is
  allowed only as a scoped basin escape, not as broad repeated random/descent
  passes.
- Handoff payloads should be OpenROAD-native and compact. Use
  `odb::dbInst*`, `odb::dbNet*`, `odb::dbGroup*`, `odb::dbRegion*`, dense ids,
  vectors, bitsets, and current detailed-placement mappings. Do not duplicate
  current coordinates or route hot state through files, JSON, log scraping,
  string-keyed maps, or public Tcl/SWIG ABI layout changes.

## Patch Style

- Change one coherent route/mechanism at a time.  For Teacher/Student rounds,
  that route may include multiple related code changes spanning
  legalization/detailed placement, improve placement, and their shared
  objective/handoff.
- Start from Teacher-named exact symbols and inspect only nearby code before
  patching. Avoid full-file reads, full-tree archaeology, and donor-source
  sweeps unless exact-symbol lookup fails.
- Use `apply_patch` for source edits. Do not rewrite source files with Python,
  heredocs, `sed -i`, `perl -pi`, or broad formatter-driven edits.
- Patch only current file contents from the private source tree. Before each
  nontrivial patch, confirm the module-relative file with `rg --files`, locate
  the exact function/state with targeted `rg -n`, and inspect a small nearby
  line-numbered excerpt.
- Do not patch against remembered snippets, Teacher-plan prose, donor examples,
  old checkpoints, or another student's workspace. Those are evidence, not
  current patch anchors.
- Keep hunk anchors narrow and unique. Prefer one function body, one state
  declaration, one include list, or one build-list edit per hunk. Large
  mechanisms should be decomposed into several verified small patches.
- After a successful patch, verify the changed symbol with targeted `rg -n` or a
  small excerpt, then run `git diff --check` before building.
- If `apply_patch` fails, do not retry the same stale hunk. Re-open the current
  local source around the intended function/state, reduce the edit to the
  smallest semantic insertion or replacement, and apply a fresh patch based only
  on the refreshed text.
- For donor-derived edits or Teacher-prose-derived hunks, run the generated
  source-context helper first and patch against current local source text only.
  Never reuse donor line numbers or old hunk context as the patch anchor.
- Run the generated source-preparation script before code inspection. After
  reading the workspace packet, required skills, and nearby Teacher-named
  symbols, patch a coherent mechanism and move to generated build/evaluate
  scripts. Do not spend the iteration on broad source exploration.
- If Teacher assigns a prepared start point (`framework`, `diamond`,
  `evolved_diamond`, `evolved_legalm`, or `evolved_negotiation`), use the generated
  `switch_start_branch_script` immediately after source preparation and before
  edits. Do not copy seed directories or manually apply OpenROAD-root patches to
  emulate a start-point switch.
- If Teacher assigns an evolved patch application rather than an evolved
  start-kind, use the generated `apply_evolved_legalizer_patch_script`.
  First run it with `--check-only`, then apply exactly one line
  (`diamond`, `legalm`, or `negotiation`). Do not manually run `git apply` on
  OpenROAD-root patches inside the private source tree.
- Keep `detailed_placement_evolve` as the primary evolved placement command.
- Keep external evaluator, baseline Tcl, ORFS flow, workspace helper, and
  benchmark-selection scripts locked. Inside `private_dpl_evolve_source`, it is
  valid to change the source-level implementation of `improve_placement_evolve`,
  including internal endpoint order, pass gating, candidate scoring,
  parameterization, and legalization/improve handoff state, when runtime remains
  bounded and canonical stage metrics prove the effect.
- Hybrid legalizer work should be source-level staged algorithm composition,
  not a case/scenario selector that switches among complete legalizers. Borrow
  ideas such as global guidance, resource prices, local compaction, or exact
  DPO transactions as mechanisms and wire them together with explicit
  producer/consumer state.
- Parameter tuning belongs in source code: constants, thresholds, scoring
  weights, pass schedules, adaptive policies, or compact internal config
  structs inside `private_dpl_evolve_source`. Do not implement a white-box
  route by adding or sweeping Tcl command options, changing ORFS flow scripts,
  changing evaluator scripts, or repeatedly invoking unchanged endpoints.
- Add telemetry when a new stage or repair operator executes.
- Add lightweight counters/logs for the mechanism when they help Teacher check
  whether the logic actually executed.

## Required Patch Note

For each patch, record:

- touched files,
- stage or mechanism name,
- expected HPWL/runtime/displacement/legality effect,
- expected failure mode,
- repair or failure-handling policy inside the algorithm.
- key counters/logs that prove the mechanism ran.

## Forbidden Behaviors

- simultaneous evaluator and algorithm edits,
- moving target-plane code into the control plane,
- adding third-party source directly into target code without explicit approval,
- claiming success without comparing against the current baseline,
- using fallback-to-default behavior as evidence of algorithm quality.
