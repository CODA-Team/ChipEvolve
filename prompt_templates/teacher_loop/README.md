# Teacher Loop Prompt Templates

These files are human-editable prompt templates for
`scripts/optimize_case_with_codex.py`.

Rules:

- Keep agent-facing templates short.
- Keep shared facts in `iter_XX/context/iteration_context.md`; agent prompts
  should point to that file rather than embedding the whole context.
- Put exact paths, shell commands, run tags, and artifact locations in generated
  packet files under `iter_XX/packet/`, not in agent prompt prose.
- Teacher insight is appended to child prompts after Teacher runs, but only the
  assigned `### student_XX` section should be appended.
- Shared Teacher rules live in `teacher_rules.md`; shared Student rules live in
  `student_rules.md`. Teacher plan/review output and review rules live in
  `teacher_plan_output.md`, `teacher_review_rules.md`, and
  `teacher_review_output.md`. Shared per-student insight packet fields live in
  `student_insight_packet_format.md`. Do not duplicate these blocks across
  templates.
- Teacher prompts should assign concrete per-student plans requiring source-level
  work on legalization, improve placement, and mirror/orientation. Student
  prompts should enforce those stage responsibilities and execution discipline
  through `student_rules.md`.
- Prompts should favor controllable algorithm complexity, bounded candidates,
  cached touched data, and direct HPWL mechanisms.
- Keep the NoPUA-style coaching signal in `skills/teacher_peer_coaching.md`:
  autonomy, evidence, initiative, and switching perspective after repeated weak
  attempts. Do not compress it into generic encouragement.
- Use `$variable_name` placeholders.  Python fills them with `string.Template`.
- Run the prompt audit before launching a new prompt design:

```bash
python3 scripts/optimize_case_with_codex.py \
  --case jpeg_nangate45 \
  --children 2 \
  --iterations 2 \
  --skip-baseline-preflight \
  --dry-run \
  --audit-prompts \
  --fail-on-prompt-audit
```

Audit output:

- `PROMPT_AUDIT.md`
- `prompt_audit.json`

Agent prompts live under `iter_XX/prompts/`.  Generated machine packets live
under `iter_XX/packet/`.
