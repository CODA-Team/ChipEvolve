# Teacher Routing Context

- case: `$case_id`
- flow_variant: `$flow_variant`
- threads: `$threads`
- start_kind: `$start_kind`
- round_id: `$round_id`
- iteration: `$iteration_name`
- full_context: `$full_context_path`
- manual_teacher_guidance: `$manual_teacher_guidance_path`

Use this file as the Teacher context entry point for initial routing.

- Start from `current_run_packet.md`, `design_characteristics.md`,
  `baseline_routing_note.md`, `peer_learning_routing_note.md`, and
  `start_seed_calibration.md`.
- If `manual_teacher_guidance` is not `none`, read it before assigning
  students. It is a case-specific continuation note, not a global rule.
- Open `full_context` only with a targeted `rg` or short excerpt when those
  packet files still leave a concrete metric line, symbol, or path unresolved.
- Do not scan the full context file linearly during the initial routing pass.
