# Skill Note: dpo_neg014_quality_ceiling

Canonical structured fields live in `knowledge/index/skill_cards.jsonl`.
Use `scripts/query_knowledge.py --q dpo_neg014_quality_ceiling --show-full`
for source handles, patch names, metrics, and log signals.

## Extra Guidance

- Use this when Teacher intentionally spends more bounded runtime for a stronger
  improve-placement consumer.
- If quality is good but runtime is excessive, the next route should rewrite it
  with caches, candidate caps, or parallel scoring instead of discarding the
  mechanism.
- Compare against `neg017b` on the same legalizer start.

## Common Failure

- Promoting a quality win that comes from broad rescans or repeated unchanged
  endpoint behavior.
