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
- Use `$variable_name` placeholders.  Python fills them with `string.Template`.
- Run the prompt audit before launching a new prompt design:

```bash
python3 scripts/optimize_case_with_codex.py \
  --case jpeg_nangate45 \
  --children 2 \
  --iterations 2 \
  --compact-after-first \
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
