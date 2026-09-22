# ADR-001: Use Ports and Adapters

## Context

The data foundation, knowledge corpus, filesystem and execution foundation are
owned by different systems and will evolve independently.

## Decision

Keep domain/application code dependent on provider-neutral ports. Put concrete
filesystem, knowledge, design-data, LLM and future execution integrations in
adapters.

## Consequences

Providers can be replaced and contract-tested independently. The project has a
small amount of explicit wiring, but no source-specific logic leaks into the
Query Agent core.
