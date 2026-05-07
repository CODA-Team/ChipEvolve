# Skill Note: handoff_residual_net_queue

Canonical structured fields live in `knowledge/index/skill_cards.jsonl`.
Use `scripts/query_knowledge.py --q handoff_residual_net_queue --show-full`
for source handles, metrics, and log signals.

## Extra Guidance

- Use this when legal HPWL improves but improve placement or final evaluation
  stages erase the gain; repair the producer/consumer handoff, not downstream
  optimize-mirroring code.
- Require both producer and consumer counters; metadata that no later stage uses
  should be treated as a no-op.
- Keep the queue bounded and focused on high-impact nets/cells/rows.

## Common Failure

- Adding handoff fields to context without changing improve-placement ordering,
  scoring, or acceptance.
