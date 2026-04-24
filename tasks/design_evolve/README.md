# Design Evolve Prompts

These are minimal prompts for loop-driven Codex patch attempts.

They assume the outer loop already owns:

- packet refresh
- checkpoint restore
- flow variant selection
- build
- evaluation
- accept/reject

The patching agent should only read the current packet, patch rules, active
problem file, and one target source file.

Run the automated loop with:

```bash
python3 "$DPL_EVOLVE_AGENT_ROOT/scripts/run_design_evolve_loop.py" \
  --problem "$DPL_EVOLVE_AGENT_ROOT/problems/gcd_nangate45/problem.yaml" \
  --max-attempts 3
```

Prompt files are named:

```text
<platform>__<design>.md
```

The matching problem file is:

```text
$DPL_EVOLVE_AGENT_ROOT/problems/<design>_<platform>/problem.yaml
```

Do not use these prompts as manual runbooks. Manual build/evaluation commands
belong in `skills/build_openroad.md` and `skills/evaluate_run.md`.
