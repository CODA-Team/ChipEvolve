# Student Rules

## Mission

- Execute the assigned Teacher packet. Do not redo Teacher's global review.
- Edit only your private `dpl_evolve` source.
- Keep `detailed_placement_evolve -> improve_placement_evolve -> optimize_mirroring_evolve` callable.
- Modify all three evolved stages: legalization, improve placement, and mirror/orientation.
- Implement Teacher's HPWL source mechanism as the primary route, but trust source-level evidence. If the source contradicts the plan or reveals a stronger route, adjust and report why.
- You may change algorithms, objectives, candidate generation, data structures, flow order inside evolved commands, and stage handoff.
- Optimize canonical `metrics.json:hpwl`; `hpwl_proxy` is debug-only.
- Final research target is clean canonical HPWL at least 5% below `openroad_dpl_flow`. Treat sub-1% wins as donor evidence, not success.

## Required Execution

- Use the workspace packet for exact prepare/build/evaluate/diff/knowledge commands.
- Plan A/B/C: legalization, improve placement, mirror/orientation. Implement all three before judging the idea.
- Build and evaluate; inspect canonical `metrics.json:hpwl` and the relevant OpenROAD log.
- If the result is weak or illegal, revise the algorithm or commit/selection logic, rebuild/evaluate, and keep the best clean candidate.
- Revisions must change the mechanism, not only constants.
- Keep exploration bounded: use `rg` first and small source excerpts around exact symbols. Do not read whole donor trees, event logs, or memory registries by default.
- Trust generated helper commands. Do not inspect evaluator/build wrapper internals unless the exact helper returned nonzero and its error text is insufficient.

## Implementation Standard

- Aggressive case-focused change; no default-equivalent behavior.
- Bounded candidates, cached touched data, controlled complexity.
- No avoidable hot-loop `O(n^2)`, full-grid scans, or full-net recomputation inside candidate loops.
- Runtime may exceed baseline when the HPWL gain or algorithmic evidence justifies it.
- Avoid public Tcl/SWIG ABI changes, especially `Opendp`, unless essential and smoke-tested.
- No case-name hardcoding.

## Final Report

Include a compact table with rows: legalization, improve placement, mirror/orientation, optional coordination. For each row, name the exact function/state changed and behavior change.

Also report touched files, mechanism, canonical HPWL/runtime/displacement delta, legality, metrics path, diff path, knowledge card path, and next uncertainty.
