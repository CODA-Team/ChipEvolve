# Skill Note: start_evolved_negotiation_conflict

Canonical structured fields live in `knowledge/index/skill_cards.jsonl`.
Use `scripts/query_knowledge.py --q start_evolved_negotiation_conflict --show-full`
for source handles, metrics, and log signals.

## Extra Guidance

- Use negotiation starts for row scarcity, fragmented rows, cut-row stress, or
  conflict-heavy legalization where local greedy behavior fails legality,
  displacement, or runtime.
- Negotiation is a complete primary legalizer when its route really runs.  If it
  is invoked after another legalizer already produced a clean placement, first
  verify that it emits nonzero moved/conflict/frontier counters; otherwise it is
  a dead producer and should be rejected or retimed.
- `evolved_negotiation` is negotiation-primary.  It may use global/differential
  guidance only as a seed/frontier, but a successful run must execute
  negotiation as the primary legalizer rather than returning from full LEGALM
  legalization.
- The guidance objective and stop point are valid optimization knobs.  Prefer
  stopping before full LEGALM over-commitment when the goal is to create a
  negotiation-friendly basin rather than a complete LEGALM legal solution.
- Keep counters visible.  Required evidence includes a negotiation-primary route
  signal, conflict/candidate counters, final violation count, stage-wise HPWL,
  runtime, and avg/max displacement.
- Treat it as a conflict-resolution donor, not a universal HPWL winner.  If it
  improves legality/runtime but weakens final HPWL, ask for either a stronger
  negotiation objective or a bounded DPO handoff consumer.
- Ask for a handoff consumer when negotiation creates legality but final HPWL is
  weak.

## Common Failure

- Letting negotiation dominate all routes so the Student stops changing the
  core mechanism.
- Accidentally using LEGALM as the successful primary legalizer and running
  negotiation only as fallback.  That route is mislabeled and must be rejected
  or repaired before use as an `evolved_negotiation` donor.
