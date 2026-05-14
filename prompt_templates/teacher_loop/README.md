# Teacher Loop Prompt Templates

These files are human-editable prompt templates for
`scripts/optimize_case_with_codex.py`.

## Directory Layout

- `context/`: shared round context visible to Teacher and Students.
- `teacher/`: Teacher planning/review prompts, Teacher rules, and Teacher
  output contracts.
- `student/`: Student initial/follow-up prompts, Student rules, and small
  Student-only prompt fragments.
- `shared/`: reusable schema fragments embedded by both Teacher plan and review
  prompts.
- `packets/`: generated packet templates. These are still agent-facing, but
  Python only fills paths, ids, and measured values.

Rules:

- Keep agent-facing templates short.
- Keep shared facts in `iter_XX/context/iteration_context.md`; agent prompts
  should point to that file rather than embedding the whole context.
- Put exact paths, shell commands, run tags, and artifact locations in generated
  packet files under `iter_XX/packet/`, not in agent prompt prose.
- Teacher insight is appended to child prompts after Teacher runs, but only the
  assigned `### student_XX` section should be appended.
- Shared Teacher rules live in `teacher/rules.md`; shared Student rules live in
  `student/rules.md`. Teacher plan/review output and review rules live in
  `teacher/plan_output.md`, `teacher/review_rules.md`, and
  `teacher/review_output.md`. Shared per-student insight packet fields live in
  `shared/student_insight_packet_format.md`. Do not duplicate these blocks
  across templates.
- Teacher prompts should assign concrete per-student plans with route emphasis:
  `legalizer-emphasis`, `DPO-emphasis`, or `co-optimization-emphasis`.
  Emphasis is a priority label, not a three-way exclusive choice. Students
  should inspect and improve legalization, improve placement, and handoff when
  they can make high-quality mechanism changes, then validate the full
  legalize/improve/mirror flow. Student prompts should keep optimize mirroring
  callable for evaluation but outside the active patch surface unless a future
  task explicitly reopens it.
- LEGO-lite mechanism lookup lives in `knowledge/index/skill_cards.jsonl`,
  `knowledge/skills/`, and `knowledge/algorithm_cards/`. Teacher packets should
  select relevant stage skills and the smallest useful algorithm/pseudocode
  card; Student reports should prove selected mechanisms with source, metrics,
  and log evidence.
- Prompts should favor controllable algorithm complexity, bounded candidates,
  cached touched data, and direct HPWL mechanisms.
- Keep the NoPUA-style coaching signal in `skills/teacher_peer_coaching.md`:
  autonomy, evidence, initiative, and switching perspective after repeated weak
  attempts. Do not compress it into generic encouragement.
- Use `$variable_name` placeholders. Python fills them with `string.Template`.
- Keep new prompt prose in this directory. Python should only choose templates,
  compute values, and fill placeholders. If a generated packet needs new
  instructions, add or update a file under `packets/` instead of embedding the
  prose in Python.
- Run the prompt audit before launching a new prompt design:

```bash
python3 scripts/optimize_case_with_codex.py \
  --case <case_id> \
  --children 2 \
  --iterations 2 \
  --skip-baseline-preflight \
  --dry-run \
  --audit-prompts
```

Audit output:

- `PROMPT_AUDIT.md`
- `prompt_audit.json`

Agent prompts live under `iter_XX/prompts/`.  Generated machine packets live
under `iter_XX/packet/`.
