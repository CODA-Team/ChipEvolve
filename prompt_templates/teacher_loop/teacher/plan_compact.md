# Teacher Follow-Up Plan

Context: `$context_path`
Current run packet: `$current_run_packet_path`
Design characteristics: `$design_characteristics_path`
Baseline artifacts: `$baseline_artifacts_path`
Peer learning: `$peer_learning_path`
Start calibration: `$start_seed_calibration_path`

Use prior Teacher session memory. The context is a delta packet; do not reread
global rules or broad reference trees. Read the listed packet files directly;
do not spend time discovering them. Use small `rg`/excerpt checks around
concrete symbols only when the packet files do not already provide the needed
metric line, path, or source handle. Output only next student directions, not
build/eval procedure.

## Student Slots

$route_lines

## Student IDs

Use exactly these headers:

$student_roster

Do not create, skip, merge, or renumber students.

$teacher_rules

$teacher_plan_output
