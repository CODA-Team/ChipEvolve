# Skill Note: start_evolved_legalm_dense

Canonical structured fields live in `knowledge/index/skill_cards.jsonl`.
Use `scripts/query_knowledge.py --q start_evolved_legalm_dense --show-full`
for source handles, patch names, metrics, and log signals.

## Extra Guidance

- Use this start when dense/high-util legalization inflation is the visible gap.
- Let the Student continue or mutate the prepared `start/evolved_legalm` source;
  do not make them reapply OpenROAD-root patches manually.
- Pair it with an improve-placement consumer when legal HPWL improves but final
  HPWL does not.

## Common Failure

- Resetting to this start as a fallback when Teacher requested continuation
  from an existing elite source.
