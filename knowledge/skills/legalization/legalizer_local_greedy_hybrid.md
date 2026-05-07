# Skill Note: legalizer_local_greedy_hybrid

Canonical structured fields live in `knowledge/index/skill_cards.jsonl`.
Use `scripts/query_knowledge.py --q legalizer_local_greedy_hybrid --show-full`
for source handles, patch names, metrics, and log signals.

## Extra Guidance

- Use local greedy logic as an internal stage of a source-level hybrid, not as a
  repeated endpoint call.
- Consume residual/frontier/conflict state from the earlier legalizer so the
  local pass repairs the right cells.
- Bound the search with candidate caps, row/segment caches, and local HPWL
  scoring.

## Common Failure

- Calling unchanged local legalization more times and reporting runtime-spent
  quality as a new mechanism.
