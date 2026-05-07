# Skill Note: legalm_global_frontier_guidance

Canonical structured fields live in `knowledge/index/skill_cards.jsonl`.
Use `scripts/query_knowledge.py --q legalm_global_frontier_guidance --show-full`
for source handles, patch names, metrics, and log signals.

## Extra Guidance

- The important property is a connected path from global/differential guidance
  to the committed legal refined solution.
- If the current code converts guidance into isolated greedy interval polish,
  assign repair to the guidance-to-refinement connection.
- Expose residual or frontier state to improve placement when legal-stage wins
  fail to survive.

## Common Failure

- Adding a global-looking score that is computed but not used by the committed
  legal placement.
