# Phase IV — Evidence-Grounded Diagnosis

## Scope

This slice answers a narrow root-cause question only when an injected provider
returns a typed finding with citable support. The fixture demonstrates a timing
degradation finding linking a negative-slack path to a design net relationship.

It does not infer causes from logs alone, assign numeric confidence, launch
analysis tools, recommend an ECO, or mutate a design.

## Contract

`DiagnosisFinding` contains:

- a bounded human-readable claim;
- optional affected and cause `DesignObjectRef` values;
- one or more `DiagnosisSupport` items with evidence kind, locator,
  description, and optional source hash;
- explicit design/run/stage scope and provider provenance;
- a completeness marker.

`DiagnosisProvider.get_findings` is the only application boundary for these
claims. Missing, wrong-scope, or incomplete findings become
`NEEDS_MORE_DATA`; no answer is synthesized from provider absence.

## Verification

```bash
PYTHONPATH=src:. python -m query_agent.benchmark benchmarks/phase4
```

The five deterministic cases cover a supported finding, missing provider, wrong
design scope, unsupported symptom, and incomplete-support refusal.
