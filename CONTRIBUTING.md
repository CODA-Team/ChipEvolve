# Contributing

Keep the dependency direction explicit:

```text
interfaces -> application -> domain
application -> ports
adapters -> ports/domain
```

Domain models do not import application code or adapters. Application services
depend on ports, never on a concrete provider. Filesystem access belongs only
to `LocalArtifactProvider`; LLM SDKs, when eventually added, belong only under
`adapters/llm/`. The execution foundation is accessed through a future
adapter/service boundary, never through its SQLite database or runtime modules.

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
integration test for a real fake workspace. Keep Phase I read-only and avoid
adding a compatibility branch for a removed design.
