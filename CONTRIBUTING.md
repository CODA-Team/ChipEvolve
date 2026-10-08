# Contributing

Keep the dependency direction explicit:

```text
interfaces -> application -> domain
application -> ports
adapters -> ports/domain
```

Domain models do not import application code or adapters. Application services
depend on ports, never on a concrete provider. Local design-file access belongs to `LocalArtifactProvider`. Investigation state,
skill loading, model traces and cost reservations each belong to their concrete
adapters, with an explicit configured root. Model transports belong only under
`adapters/llm/`. Execution and supplementary analysis use public HTTP/client
boundaries, never another project’s SQLite database or runtime modules.

Every provider result must be typed evidence with a locator and provenance.
Evidence insufficiency is a normal `QueryResponse` status. Do not add a
numeric confidence field or infer a root cause when the required capability is
absent.

Before submitting a change, run the complete local checks:

```bash
ruff check .
ruff format --check .
pyright
lint-imports
pytest
```

Add a unit test for domain changes, contract tests for provider ports, and an
integration test for a real fake workspace. Keep the existing simple-query path read-only. The authorized investigation path
may submit bounded analysis through its explicit analysis port after scope/input/
budget checks. Do not add a compatibility branch for a removed design.
JEV probabilities are routing evidence, never a substitute for fact correctness
or execution permission. Missing billing usage retains its reservation.
