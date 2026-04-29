# Teacher Review Follow-Up

Context file: `$context_path`

Read context and the Teacher peer-coaching skill referenced in context.
Review artifacts, compare students, write next-iteration feedback only.

## Generated Artifact Packet

Read exact student paths and logs:

`$review_packet_path`

Use `artifact_status` and `artifact_problems` as the validity gate. Missing
metrics, missing diff, failed returncode, or no agent message means invalid.
Read `knowledge_card` when present. Classify tiny HPWL gains as donor evidence
unless the mechanism plausibly scales.
Diagnose runtime/complexity: endpoint proliferation, full scans, repeated
import/init, full HPWL recomputation, unbounded loops, and guard clutter.
Mark any promising lineage whose `source_backup` should be frozen and tested
with `scripts/run_candidate_matrix.sh`.
Next-round feedback must not be one-stage local advice. Each student needs a
legalization directive, improve-placement directive, mirror directive, and
cross-stage co-optimization directive.
If students repeat the same weak assumption, name it and assign different
mechanism classes.  When borrowing a peer, specify what to borrow, what to
mutate, and what cost/legality risk to watch.

## Output Required

- compact review table
- mechanism changed
- build/eval status and metrics path if present
- HPWL/runtime/displacement movement
- peer mechanism to borrow or avoid
- efficiency bottleneck and concrete faster version to try
- knowledge card to preserve or reject
- fixed-source matrix candidate, if any
- best one or two lineages to continue
- next per-student legalization/improve/mirror/co-optimization directives

End with `## Next Insight Packets` and one concise `### student_XX` section per student.
