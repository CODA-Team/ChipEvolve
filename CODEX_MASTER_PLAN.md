# Query Agent construction plan

This document is the stable plan for evolving the evidence-first Query Agent.
The application reasons over typed contracts; concrete execution, design-data,
analysis, and language-model implementations remain replaceable adapters.

## Capability ladder

1. Phase I — bounded evidence and deterministic answerability (complete).
2. Phase II — experiment context reasoning (current construction target).
3. Phase III — design-object and analysis understanding.
4. Phase IV — evidence-grounded diagnosis.
5. Phase V — explicit, reversible action and optimization loops.

Phase II establishes run, stage, artifact, metric, provenance, freshness,
comparability, and conflict semantics. It does not parse EDA databases, launch
tools, mutate designs, or add an agent framework.

## Boundary rules

- `domain` contains the shared vocabulary and no infrastructure knowledge.
- `ports` describe capabilities needed by the application.
- `application` coordinates policies and providers through dependency injection.
- `adapters` translate external APIs into domain contracts.
- `interfaces` assemble concrete providers and expose the use case.
- missing or contradictory evidence is a typed business outcome, never a
  plausible fallback answer.

## Vertical slices

- 2.0: baseline and architecture records.
- 2.1: typed experiment run/stage/context contracts and provider port.
- 2.2: execution-foundation adapter plus deterministic run/stage selection.
- 2.3: provenance, metric ownership, freshness, and conflict policies.
- 2.4: comparable-run selection and QueryService/trace integration.
- 2.5: externally meaningful Phase-II benchmark and completion verification.

Each slice must retain the Phase-I tests and pass the complete quality gate.
