# Teacher Review Task

Context file: `$context_path`

Review code, logs, metrics, and peer effects. Produce next-round insights only.

## Generated Artifact Packet

Read exact student paths and logs:

`$review_packet_path`

Checks:

- use `artifact_status`, `artifact_problems`, and existence flags from the packet
- never promote a candidate with missing metrics, missing diff, failed returncode,
  or no agent message
- read `codex_last_message`, usage/stderr hints, metrics path, and `implementation_diff`
- inspect changed source only where needed
- compare HPWL/runtime/displacement/legality to anchors and peers
- classify real mechanism vs parameter tweak vs fallback
- name useful peer mechanisms and harmful mechanisms
- include the full evolved flow, not only first legalization

## Output Required

- compact review table
- best one or two lineages
- peer mechanisms to borrow/avoid
- one short next insight per student

End with `## Next Insight Packets` and one concise `### student_XX` section per student.
