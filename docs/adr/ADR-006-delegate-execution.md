# ADR-006: Execution Is Delegated to execution-foundation

## Context

The sibling execution foundation already owns tasks, workspaces, resources,
processes, lifecycle, artifacts, logs and provenance.

## Decision

Future read-only analyses go through an `AnalysisProvider` adapter and the
foundation's public service API. Query Agent never opens the foundation
database, launches a tool, or reimplements task/workspace management.

## Consequences

There is one execution authority and one provenance chain. Integration waits on
a versioned analysis contract, but the Phase I domain does not need to change
when the data or execution provider is replaced.
