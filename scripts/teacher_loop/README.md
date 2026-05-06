# Teacher Loop Python Modules

`scripts/optimize_case_with_codex.py` is the stable CLI shim.  The implementation
is split here by responsibility:

| Module | Responsibility |
| --- | --- |
| `cli.py` | CLI arguments for the stable `optimize_case_with_codex.py` entrypoint. |
| `orchestrator.py` | Top-level prepare -> baseline -> Teacher -> Student -> review loop. |
| `common.py` | Shared constants, dataclasses, workspace paths, prompt template rendering, and round logging. |
| `evidence.py` | Baseline/candidate metrics, scoreboard generation, peer-learning packets, and artifact validity checks. |
| `prompts.py` | Prompt/context rendering, generated workspace/review packets, Student command scripts, start-kind seed parent resolution, and prompt audit. |
| `execution.py` | `codex exec` command construction, resume checks, command execution, lineage, source commits, and elite seeding. |

Keep fixed prepare/build/evaluate/commit/diff commands in generated Student
workspace scripts under `students/student_XX/.../scripts/iter_XX/`. Packet
files under `iter_XX/packet/` should point to those iteration-specific scripts
and exact artifact paths. Keep human-editable prompt prose in
`prompt_templates/teacher_loop/`.
