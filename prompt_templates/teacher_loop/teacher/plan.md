# Teacher Plan

Context: `$context_path`
Current run packet: `$current_run_packet_path`
Design characteristics: `$design_characteristics_path`
Baseline artifacts: `$baseline_artifacts_path`
Peer learning: `$peer_learning_path`
Start calibration: `$start_seed_calibration_path`

Treat `Context` as a backing evidence file, not the first thing to read. Start
from the packet files listed above. Do not open `student_XX_workspace.md`
during initial routing; that packet is for Student execution unless a later
review needs a concrete workspace path. Do not spend time discovering these
paths. Open the context file only with small `rg`/excerpt checks when a packet
does not already pin down a concrete metric line, symbol, or path. Treat source
and reference paths as targeted search handles, not required reading. Produce
concise per-student plans; do not include build/eval procedure.

## Student Slots

$route_lines

## Student IDs

Use exactly these headers:

$student_roster

Do not create, skip, merge, or renumber students.

$teacher_rules

$teacher_plan_output
