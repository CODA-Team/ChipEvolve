# Phase II — Experiment Context Reasoning

## Scope

Phase II answers whether evidence belongs to the requested experiment state.
The state is identified by design, run, stage, ordering, artifact ownership,
metric ownership, provenance, freshness, and comparability. A value from the
wrong stage or an older run cannot silently satisfy a current-state request.

## Contract

`ExperimentContextProvider` exposes typed run, stage, artifact, metric, and
provenance views. `ExecutionFoundationExperimentContextProvider` translates the
execution-foundation public read API into those views. The application never
imports that client or opens its database.

## Selection policy

- an explicit `run_id` wins when it exists;
- `LATEST_VALID` selects the newest completed run whose requested stage also
  completed;
- `CURRENT` only selects the newest run when it is completed; it does not reuse
  an older run while a newer run is active or failed;
- comparison requires aligned metric, stage, unit, corner, and design scope;
- every rejected candidate carries a stable reason code in the trace.

## Evidence states

An unregistered metric artifact is `PARTIAL`; it is retained for explanation
but cannot satisfy a strict current-state requirement. Incompatible values for
the same normalized fact and scope are `CONFLICTING` until an explicit authority
policy exists. Missing evidence and unsupported capabilities remain separate.

## Non-goals

No OpenDB/DEF/LEF/SPEF parsing, timing graph traversal, congestion/DRC/power
analysis, ECO, arbitrary shell execution, or autonomous write operation is part
of Phase II.
