# ADR-010: bounded typed analysis provider

## Context

Phase III-A supplies structural design objects, but timing questions require
analysis results with different semantics and provenance. Passing raw reports,
timing graphs, or provider dictionaries into the application would make scope,
freshness, and answerability ambiguous.

## Decision

Add a read-only `AnalysisProvider` port with two bounded operations:

- `get_timing_metrics` for WNS/TNS observations;
- `get_timing_paths` for bounded path observations with an optional slack
  threshold.

Each observation owns an explicit analysis scope and provenance. The application
converts it into generic cited `Evidence`, and incomplete results do not satisfy
the current-analysis requirement. The fixture and unavailable adapters make the
contract testable without claiming an external timing implementation.

## Consequences

- timing evidence remains distinct from design-object structure;
- provider replacement does not change query planning or response models;
- no timing graph traversal, parser, tool execution, diagnosis, or ECO action is
  implied by the port;
- future analysis families require their own typed contract and benchmark.
