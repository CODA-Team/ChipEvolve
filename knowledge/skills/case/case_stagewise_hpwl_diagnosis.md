# Skill Note: case_stagewise_hpwl_diagnosis

Canonical structured fields live in `knowledge/index/skill_cards.jsonl`.
Use `scripts/query_knowledge.py --q case_stagewise_hpwl_diagnosis --show-full`
when Teacher needs the exact metrics/log checklist.

## Extra Guidance

- Start every route decision from the stage table, not from final HPWL alone.
- Preserve a stage donor even when a later stage erases it; assign the next
  route to repair the consumer or handoff.
- Treat runtime-only wins as evidence only if HPWL, displacement, and legality
  stay comparable.

## Common Failure

- Promoting the best final donor while discarding a stronger legalization-stage
  donor that only needs improve-placement repair.
