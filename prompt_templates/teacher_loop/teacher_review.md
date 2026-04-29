# Teacher Review Task

Context file: `$context_path`

Read context and the Teacher peer-coaching skill referenced in context.
Review code, logs, metrics, and peer effects. Produce next-round insights only.

## Generated Artifact Packet

Read exact student paths and logs:

`$review_packet_path`

Checks:

- use `artifact_status`, `artifact_problems`, and existence flags from the packet
- never promote a candidate with missing metrics, missing diff, failed returncode,
  or no agent message
- read `codex_last_message`, metrics, `implementation_diff`, and
  `knowledge_card`; inspect changed source only where needed
- compare HPWL/runtime/displacement/legality to anchors and peers
- classify real mechanism vs parameter tweak vs default-equivalent/no-op behavior
- classify tiny HPWL gains as micro-gain donor evidence unless the mechanism
  plausibly scales to a much larger improvement
- diagnose runtime/complexity: endpoint proliferation, full scans, repeated
  import/init, full HPWL recomputation, unbounded loops, or guard clutter
- prefer donors that combine HPWL gain with an implementable efficiency path
- include the full evolved flow, not only first legalization
- reject next-round plans that only ask for one-stage local tweaks; each next
  student insight must include legalization, improve-placement, mirror, and
  cross-stage co-optimization directives
- if multiple students fail in the same way, name the failed assumption and
  force different mechanism classes instead of retuning the same idea
- when a peer is better, teach others what mechanism to borrow, what evidence
  supports it, and what inefficiency or brittleness to fix
- mark any promising lineage whose `source_backup` should be frozen and tested
  with `scripts/run_candidate_matrix.sh`

## Output Required

- compact review table
- best one or two lineages
- peer mechanisms to borrow/avoid
- efficiency bottleneck and concrete faster version to try
- knowledge cards worth preserving
- fixed-source matrix candidates, if any
- one short next insight per student with four directives:
  legalization, improve placement, mirror, and cross-stage co-optimization

End with `## Next Insight Packets` and one concise `### student_XX` section per student.
