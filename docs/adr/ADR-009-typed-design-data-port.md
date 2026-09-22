# ADR-009: Typed read-only design-data port

## Context

The next capability after experiment context is answering what objects exist,
where they are, and how they connect. The application must remain independent
of OpenDB, DEF/LEF/SPEF parsers, and any future data foundation.

## Decision

Define `DesignDataProvider` operations for typed instance, net, pin, connection,
fanout, location, and region queries. Use immutable domain models with stable
object references and bounded provenance locators. Translate those models to
the existing `Evidence` contract in one application collector. The fixture
adapter is the deterministic test implementation; external database adapters
remain plugins behind the same port.

## Alternatives considered

- Expose a generic `query(str) -> dict`: rejected because it is stringly typed,
  hides operation semantics, and makes provenance and validation inconsistent.
- Parse DEF/ODB directly in the application: rejected because it couples the
  use case to one implementation and violates the adapter boundary.
- Give the language model raw database APIs: rejected because invalid calls and
  untraceable observations would become part of the architecture.

## Consequences

Design-object retrieval is replaceable and testable with a fake provider. The
current fixture supports research benchmarks without claiming external EDA
performance. Future providers must preserve object identity, scope, and
read-only semantics; richer timing/analysis concepts belong to later ports.

## Migration implications

`UnavailableDesignDataProvider` remains the truthful default and implements the
typed operations with empty results. Existing Phase-I callers that probe its
null behavior continue to receive no fabricated evidence. New application
questions use `DesignQuestionParser` and typed operations only.
