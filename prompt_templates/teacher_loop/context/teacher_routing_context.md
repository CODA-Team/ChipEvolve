# Teacher Routing Context

- case: `$case_id`
- flow_variant: `$flow_variant`
- threads: `$threads`
- start_kind: `$start_kind`
- round_id: `$round_id`
- iteration: `$iteration_name`
- full_context: `$full_context_path`
- matched_blueprint_packet: `$matched_blueprint_packet_path`
- manual_teacher_guidance: `$manual_teacher_guidance_path`

Use this file as the Teacher context entry point for initial routing.

- Start from `current_run_packet.md`, `design_characteristics.md`,
  `baseline_routing_note.md`, `peer_learning_routing_note.md`, and
  `start_seed_calibration.md`.
- Treat case-evolution and strategy insight files as validated case-feature
  method warm starts.  Use them to recognize the current design pattern and
  route Students to concrete source mechanisms; validate every route on the
  current case.
- Before assigning routes, check whether the stage metrics match a verified
  case-type blueprint in `matched_blueprint_packet`. First check whether the case is a large row-rich or
  datapath-like recoverable basin: large movable count, strong improve-stage
  recovery, nontrivial runtime, and final HPWL controlled by downstream exact
  accepts rather than legalize-only HPWL. For that signature, open
  `matched_blueprint_packet` first and route at least one Student to reconstruct
  the complete stack:
  Differential/LEGALM-style producer -> negotiation-compatible legal closure ->
  exact source-edge/global-swap consumer -> edge-critical/selected reorder ->
  bounded post-reorder exact/pair/endpoint polish.
- For low-util or Diamond-stable local residue without the large row-rich
  cumulative-chain signature, open `matched_blueprint_packet` first and route
  at least one Student to the complete chain: preserve a Diamond-compatible
  legal basin, force the
  enhanced DPO path, and implement the exact source-edge kernel in
  `DetailedGlobalSwap`: bounded source-edge target generation, exact move/swap
  scoring with `DetailedHPWL::delta`, replay through journal/rollback, and
  source-edge liveness counters.  Do not count LEGALM/negotiation-only,
  mirror-only, frontier-only, Diamond-frontier-only, or telemetry-only work as a
  hit for this blueprint.
- If `manual_teacher_guidance` is not `none`, read it before assigning
  students. It is a case-specific continuation note, not a global rule.
- Open `full_context` only with a targeted `rg` or short excerpt when those
  packet files still leave a concrete metric line, symbol, or path unresolved.
- Do not scan the full context file linearly during the initial routing pass.
