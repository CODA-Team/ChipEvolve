# Skill Note: dpo_neg017b_cached_runtime

Canonical structured fields live in `knowledge/index/skill_cards.jsonl`.
Use `scripts/query_knowledge.py --q dpo_neg017b_cached_runtime --show-full`
for source handles, patch names, metrics, and log signals.

## Extra Guidance

- This is the preferred first DPO donor when runtime and quality both matter.
- Start from the prepared DPO branch when available; use the generated DPO patch
  helper only for intentional continuation/hybridization.
- Mutate candidate generation or objective if the donor runs but final HPWL
  plateaus.

## Common Failure

- Applying the donor and stopping without checking whether after-improve HPWL or
  final HPWL actually moved.
