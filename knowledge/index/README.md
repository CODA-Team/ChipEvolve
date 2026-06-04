# Knowledge Indexes

This directory contains machine-readable lookup records for Teacher and Student
agents.  The markdown knowledge files remain the source of detail; index records
are compact routing aids.

## Files

- `skill_cards.jsonl`: stage skills, paper cards, and support notes discoverable
  by stage, bottleneck, metric, source handle, or failure mode.
- `mechanism_stack_cards.jsonl`: compact blueprint stack records for mechanism
  composition.  These records name blueprints, producer/handoff/consumer roles,
  compatible follow-up stacks, failure buckets, handoff payloads, and first patch
  handles.

## Query Contract

Use the repo-local helper:

```bash
python3 scripts/repo/query_knowledge.py --stage teacher_review --q "Blueprint D+A stack" --limit 3
python3 scripts/repo/query_knowledge.py --stage improve_placement --q "source-edge top-K exact consumer" --limit 3
python3 scripts/repo/query_knowledge.py --validate
```

Stage aliases such as `detailed_placement`, `blueprint`, `routing`, `dpo`, and
`legalizer` are accepted for convenience, but prompt templates should prefer the
canonical stages listed in `knowledge/skills/README.md`.

Keep stack records short.  If a record starts to carry detailed pseudocode,
source archaeology, or measured result tables, move that material to
`knowledge/routing/`, `knowledge/support/`, or `knowledge/algorithms/` and keep
only the query-facing summary here.
