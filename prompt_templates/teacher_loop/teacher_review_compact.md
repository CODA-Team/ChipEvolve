# Teacher Review Follow-Up

Context file: `$context_path`

Review artifacts, compare students, write next-iteration feedback only.

## Generated Artifact Packet

Read exact student paths and logs:

`$review_packet_path`

Use `artifact_status` and `artifact_problems` as the hard validity gate.  Missing
metrics, missing diff, failed returncode, or no agent message means invalid.

## Output Required

- compact review table
- mechanism changed
- build/eval status and metrics path if present
- HPWL/runtime/displacement movement
- peer mechanism to borrow or avoid
- best one or two lineages to continue

End with `## Next Insight Packets` and one concise `### student_XX` section per student.
