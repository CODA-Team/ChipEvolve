# ADR-008: Typed experiment context provider and selection policies

## Context

Phase I retrieves registered evidence, but selecting the correct experiment
state also requires lifecycle, stage, artifact ownership, metric lineage,
freshness, and comparability semantics. Putting those rules in an adapter or
`QueryService` would make one concrete provider the architecture.

## Decision

Introduce a small `ExperimentContextProvider` port and frozen domain models for
runs, stages, artifacts, metrics, provenance, conflicts, and context selection.
Keep run/stage selection, freshness, conflict, and comparison as independent
application policies. The execution-foundation adapter consumes only the public
read client. `QueryTrace` records selection and reason codes.

An explicit run wins. Latest-valid requires a successful run and successful
requested stage. Current never falls back to an older run while the newest run
is active or failed. Partial metric lineage is not an authoritative conflict;
incompatible complete values for one normalized scope are unresolved conflict.

## Alternatives considered

- Keep all context rules in `RunEvidenceProvider`: rejected because retrieval
  and policy would be inseparable and future providers would duplicate rules.
- Let an LLM choose the latest or reconcile values: rejected because freshness,
  stage ownership, and conflict decisions must be deterministic and auditable.
- Import execution-foundation runtime/store objects directly: rejected because
  it violates the service boundary and prevents provider replacement.

## Consequences

Phase-I managed evidence behavior remains compatible. Applications can inject a
fake or execution-foundation context provider without changing business rules.
The port is read-only and does not submit tasks or open attempt workspaces.
Design-data and analysis contracts remain future phases.

## Migration implications

Existing `RunEvidenceProvider` remains available for Phase-I retrieval. A
composition root may wire both ports during migration. Future adapters map into
the shared context models rather than adding provider-specific domain types.
