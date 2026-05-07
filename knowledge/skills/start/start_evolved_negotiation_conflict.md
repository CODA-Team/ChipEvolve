# Skill Note: start_evolved_negotiation_conflict

Canonical structured fields live in `knowledge/index/skill_cards.jsonl`.
Use `scripts/query_knowledge.py --q start_evolved_negotiation_conflict --show-full`
for source handles, patch names, metrics, and log signals.

## Extra Guidance

- Use negotiation starts for row scarcity, cut-row stress, or conflict-heavy
  legalization where Diamond fails legality or displacement.
- Keep counters visible; a strong negotiation fallback can hide that later
  legalizer/DPO edits are no-ops.
- Ask for a handoff consumer when negotiation creates legality but final HPWL is
  weak.

## Common Failure

- Letting negotiation dominate all routes so the Student stops changing the
  core mechanism.
