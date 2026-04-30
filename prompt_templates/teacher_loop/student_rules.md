# Student Rules

## Mission

- Execute your assigned Teacher packet appended below.
- Do not redo Teacher's global review.
- Edit only your private `dpl_evolve` source.
- Continue your lineage unless Teacher assigned an elite seed or pivot.
- Keep the evolved commands callable:
  `detailed_placement_evolve -> improve_placement_evolve -> optimize_mirroring_evolve`.
- Modify all three evolved stages: legalization, improve placement, and
  mirror/orientation. Each stage is your responsibility and should have its own
  plausible HPWL improvement path.
- If Teacher provides `HPWL source mechanism`, implement that as the primary
  mechanism.
- If Teacher provides a `plan chain`, execute it as the required implementation
  order: A legalization, B improve placement, C mirror/orientation, then D
  optional coordination/selection. If you change the chain while coding, record
  why and keep all three stages covered.
- Teacher provides insight and likely insertion points, not a complete design.
  Trust your own source-level judgment while implementing. If source evidence
  contradicts Teacher's plan, adjust the mechanism, keep the 5% HPWL target,
  and report the reason. If you find a stronger route while coding, take it and
  explain the evidence.
- You may freely change algorithm, objective, flow order inside the evolved
  commands, candidate generation, data structures, and stage handoff.
- Borrow peer code only when it directly supports your chosen mechanism.
- Constants may support the mechanism; they cannot be the mechanism.
- Optimize canonical `metrics.json:hpwl`.
- Final research target is clean canonical HPWL at least 5% below the
  `openroad_dpl_flow` baseline. Treat `evolve_default` as an internal anchor and
  donor source when it is better; sub-1% wins are donor evidence only.
- Strict final legality is mandatory.

## Required Code Surface

- legalization: global guidance, row assignment, candidate scoring, refinement,
  stage handoff, or objective
- improve placement: detailed objective, candidate generation, touched-net
  scoring, reorder/swap/shift/orient pass, or commit policy
- mirror/orientation: orientation scoring, ordering, filtering, acceptance, or
  interaction with improve placement
- optional coordination: objective, cache, snapshot, touched-net data,
  provenance, stage selection, or flow-order handoff when useful

The three evolved stages above must have source-level edits. Optional
coordination is encouraged when it improves quality or runtime, but it is not
required to make the three stage changes depend on one another.

## Function-Level Evidence Required

Your final report must include one compact table with these rows:
legalization, improve placement, mirror/orientation, and optional coordination.
For each row, name the exact function or state object changed and how that
stage's behavior changed. If optional coordination is not used, state `not used`
and briefly explain why independent stage changes were preferable.

## Implementation Standard

- aggressive case-focused change; no default-equivalent behavior
- bounded candidates and controlled complexity
- cached touched data where possible
- no avoidable hot-loop O(n^2) or full-grid inner loops
- implement the HPWL source mechanism directly; keep validation and support code
  minimal and outside hot loops
- if the first result is weak, switch to a genuinely different hypothesis rather
  than repeatedly tuning the same constants
- avoid changing public Tcl/SWIG-wrapped class layout, especially `Opendp`,
  for ordinary algorithm state; prefer `.cpp` helpers, dedicated helper
  classes, or private implementation-local state unless a header change is
  essential and smoke-tested
- runtime may be slower than baseline if the HPWL gain or algorithmic evidence
  justifies it; keep complexity controlled and report why runtime is acceptable
- no case-name hardcoding

## Execution Discipline

- Use the generated workspace packet commands.
- Do not manually delete, rename, or move build artifacts such as `.a`, `.so`,
  object files, or build directories.
- Work through the assigned mechanism concretely: plan related edits A/B/C for
  legalization, improve placement, and mirror/orientation; implement all three;
  build and evaluate; inspect canonical
  `metrics.json:hpwl` plus the relevant OpenROAD log; revise the algorithm when
  the result is weak or illegal; rebuild and re-evaluate; keep the best clean
  candidate.
- Revisions must change the algorithmic mechanism or its commit/selection
  logic, not only retune constants. Stop when the best clean candidate is
  clearly recorded, the mechanism is exhausted, or the blocker is concrete
  enough for Teacher to act on.
- After a clean `metrics.json` exists, read only the metrics needed for the
  final report. Do not inspect evaluator/helper scripts, `post_metrics` files,
  or log tails unless the command failed or metrics are missing.
- If a build looks stale, rerun the relink scripts or use their `--build-dir`
  option with an absolute build directory under your `variant_root`; do not use
  relative build directories.
- Trust generated helper commands. Do not read `run_baseline.sh`,
  `build_openroad_variant_relink.py`, evaluator code, or wrapper scripts unless
  that exact helper returned nonzero and the error text is insufficient.
- Do not dump full context files, full event logs, or generic memory registries
  by default. Use targeted `rg`/small excerpts when extra evidence is needed.
- Before the first source edit, keep exploration bounded: use `rg` first and at
  most a few small source windows around exact symbols. Keep each window small
  enough to understand the patch site; do not page through hundreds of lines,
  whole source files, donor trees, event logs, or memory registries.
- If `apply_patch` fails, reopen the exact source around the target and apply a
  smaller patch. Do not assume the seed source matches your mental model.
- Do not run `strings`, `ldd`, `readelf`, or other binary-introspection commands
  unless the binary fails to start or the relink result is demonstrably stale.
- If Tcl startup crashes before placement begins, first suspect wrapped header
  ABI/layout or static initialization changes.

## Autonomy Standard

- Teacher gives insight, not a complete design. Trust your source-level
  judgment.
- Verify before claiming success. If you are unsure, state the uncertainty and
  what evidence you checked.
- If the assigned idea stalls, stop repeating it, inspect the failure signal,
  and try a different mechanism with a clear validation criterion.
- After a fix works, check whether the same mechanism exposes a related
  opportunity in another evolved stage.

## Execute

Use the workspace packet for exact prepare/build/evaluate/diff/knowledge paths.
Before final answer, produce: private binary, evaluation metrics, non-empty diff,
and non-empty knowledge card.

Final answer: touched files, mechanism, function-level evidence table,
legalization change, improve change, mirror/orientation change, optional
coordination if used, HPWL/runtime/displacement delta, metrics path, diff path,
knowledge card path, and next uncertainty.
