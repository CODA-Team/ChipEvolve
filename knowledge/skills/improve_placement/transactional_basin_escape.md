# Skill Note: dpo_transactional_basin_escape

Canonical structured fields live in `knowledge/index/skill_cards.jsonl`.
Use `scripts/query_knowledge.py --q dpo_transactional_basin_escape --show-full`
for source handles, metrics, and log signals.

## Extra Guidance

- Use a local journal for candidate moves: proposed positions, affected rows,
  affected nets, exact HPWL delta, legality result, and accept/rollback.
- Escalate from cheap moves to stronger reorder, swap, multi-row repair, or
  scoped LSMC only when active frontier evidence predicts useful HPWL gain.
- Bound the mechanism with window size, candidate caps, failed-window caps, and
  accepted-gain thresholds.
- A good first step is a lightweight post-DPO basin donor.  Deeper pass growth,
  larger candidate windows, and wider row radius should be treated as a second
  mechanism only after the light donor is proven live.
- If legalization already exposes frontier or residual guidance, prefer
  frontier-aware basin ranking over a pure displacement-only basin schedule.

## Common Failure

- Large descent or randomized perturbation consumes runtime without scope,
  accept/reject counters, or accepted-gain evidence.  Fix this by binding the
  search to handoff/frontier signals and by stopping on gain rate, not by
  assuming the search family is forbidden.
- A perturbation improves a proxy but fails canonical after-improve/final HPWL.
