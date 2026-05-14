# Skill Note: differential_guidance_stop_target

Canonical structured fields live in `knowledge/index/skill_cards.jsonl`.
Use `scripts/query_knowledge.py --q differential_guidance_stop_target --show-full`
when Teacher wants a mechanism-level route that uses global/differential
guidance without turning it into a complete legalizer replacement.

## Mechanism

Differential or LEGALM-style guidance can be useful as a seed/frontier producer:
it estimates globally useful movement directions, row pressure, target misses,
and high-impact nets before the final legalizer commits a placement.

The key search variables are:

- `objective`: which pressure/HPWL/displacement/recoverability terms define the
  target field.
- `stop point`: when the guidance should stop before over-committing a full
  legal solution that downstream negotiation, Diamond-style repair, or DPO
  cannot recover.
- `handoff payload`: which bounded in-process frontier facts are handed to the
  next stage, such as guided target misses, touched-net priorities, pressure
  windows, or residual conflict components.
- `consumer`: which legalizer or DPO mechanism consumes the frontier and proves
  it changed candidate ordering, scoring, or acceptance.

## Good Use

- Run guidance only far enough to create a better basin, then hand off to the
  route's primary legalizer.
- Use stage-wise metrics to check whether the guidance improved legal HPWL but
  hurt final HPWL; if so, tune the stop point or consumer instead of assuming
  the global signal is wrong.
- Keep route semantics explicit.  For an `evolved_negotiation` line, guidance
  can seed negotiation, but negotiation must still be the primary successful
  legalizer.
- Log compact counters: guided cells, target misses, frontier size, consumer
  attempts, consumer accepts, and elapsed time.

## Bad Use

- Returning from full LEGALM legalization in a line that is supposed to be
  negotiation-primary.
- Writing a target field but discarding it before the committed legal placement
  or DPO consumer.
- Stopping only after all cells are self-legal if the downstream objective needs
  a different local structure.
- Emitting broad logs or files that DPO cannot consume in-process.

## Review Questions

- Did guidance change the committed placement or only produce unused counters?
- Did the primary downstream legalizer or DPO consumer execute with nonzero
  counters?
- Did the final full-flow HPWL improve, or only the legalizer-stage HPWL?
- If final HPWL regressed, is the fix a different guidance objective, an earlier
  stop point, or a stronger frontier consumer?
