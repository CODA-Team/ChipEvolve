# Student Follow-Up: $student_id

Iteration: `$iteration_name`

Context file: `$context_path`

Peer learning packet: `$peer_learning_path`

Use Teacher insight, change code, build, evaluate, report delta. You choose the implementation.

## Teacher Insight

- Teacher insight source: `$teacher_plan_last_message`
- your `### $student_id` insight is appended below

## Generated Workspace Packet

Read for exact paths, commands, run tag, and artifact locations:

`$workspace_packet_path`

Mandatory gate: prepare, build, evaluate, non-empty diff, exact artifacts.

## Current Iteration

- case: `$case_id`
- flow_variant: `$flow_variant`
- threads: `$threads`
- run_tag: `$run_tag`

$elite_note

## Peer Results To Use, Not Re-Analyze

$peer_context

## Programming Contract

- edit only the private `dpl_evolve` source in your workspace
- freely change objective, flow order, net-aware/size-aware scoring, legalization, repair, polish, telemetry, or data structures
- high-performance C++ only: bounded candidates, cached row/net data, no avoidable hot-loop O(n^2), deterministic parallelism when safe
- strict legality is required; HPWL is the main target
- do not claim success through fallback-to-default behavior

## Instructions

- read your `### $student_id` insight from the Teacher note appended below
- do not redo the global comparison
- inspect peer code only when it helps the concrete change you choose
- continue your private source lineage unless Teacher requested a pivot
- use the generated workspace packet for prepare/build/evaluate/diff
- final answer: touched files, mechanism, build/eval status, metrics path, HPWL/runtime/displacement delta, diff path, next risk
