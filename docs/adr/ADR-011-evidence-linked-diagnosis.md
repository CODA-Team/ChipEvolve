# ADR-011: evidence-linked diagnosis provider

## Context

A root-cause answer is materially different from a design lookup or timing
metric. The application must not promote a plausible relationship into a cause
without retaining the facts that support it.

## Decision

Add a read-only `DiagnosisProvider` port returning `DiagnosisFinding` values.
Every finding carries explicit scope and provenance and must contain at least
one `DiagnosisSupport` item. The application converts findings to cited
diagnosis evidence and rejects missing or incomplete findings. The fixture is a
deterministic contract implementation, not an inference engine.

The existing `DESIGN_RELATION_QUERY` capability remains the planning boundary,
so earlier Phase-I benchmark semantics remain unchanged while an authoritative
diagnosis service can replace the fixture.

## Consequences

- root-cause claims remain auditable and source-linked;
- unsupported symptoms and wrong scopes produce structured refusal;
- no numeric confidence, causal fallback, tool execution, or ECO action is
  implied;
- Phase V actions require a separate reversible contract.
