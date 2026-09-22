# Data contracts

The models in `query_agent.domain` are the shared language between the
application and adapters.

| Contract | Meaning |
| --- | --- |
| `QueryRequest` / `QueryContext` | Question and workspace/design/run/stage scope |
| `QueryIntent` | Question type, independent of answerability |
| `Capability` | Provider ability; Phase I availability is explicit |
| `Evidence` | First-class fact or excerpt with scope, locator and provenance |
| `EvidenceStatus` | `SUFFICIENT`, `PARTIAL`, `INSUFFICIENT`, or `CONFLICTING` |
| `EvidenceRequirement` / `QueryPlan` | What must be collected before answering |
| `QueryResponse` / `QueryStatus` | Answer or a structured missing-evidence result |
| `ExperimentRun` / `ExperimentStage` | Run and stage lifecycle vocabulary |
| `ArtifactRef` / `MetricObservation` | Run/stage ownership and metric lineage |
| `ExperimentContext` / `ContextSelection` | Provider snapshot and deterministic selection |
| `ComparisonSet` / `Conflict` | Aligned comparisons and unresolved disagreement |

`EvidenceProvenance` is intentionally small: provider, optional source SHA-256,
optional source modification time, and retrieval time. `EvidenceLocator` points
to a URI/path and optional line range or section. A response cites locator URIs
and retains the typed evidence items.

No core contract has a fabricated numeric confidence. Evidence quality is a
business state, and missing evidence is a normal result rather than an
exception.

`QueryContext.source` separates `LOCAL_WORKSPACE` from `MANAGED_RUN`. A managed
run has a `run_id` and no attempt workspace; its authoritative evidence must
come from `RunEvidenceProvider`. A local context has an explicit workspace and
is served by `LocalArtifactProvider`.

`EvidenceRequirement` can carry an exact scope, a `fact_key`, and a
`requires_current` flag. Deterministic answerability evaluation rejects wrong
run/stage evidence, retains conflicting values, and treats partial/non-current
evidence as insufficient for current-state questions.

Phase II keeps lifecycle separate from `Evidence`. A metric without a
registered source artifact is retained as a partial observation but cannot
satisfy a strict current-state requirement. Only complete observations take
part in authoritative conflict detection. Comparisons require aligned design,
canonical stage, metric, unit, and corner semantics.

## Phase I capabilities

Available when a provider advertises them:

- `DOMAIN_KNOWLEDGE`
- `ARTIFACT_DISCOVERY`
- `TEXT_SEARCH`
- `EXPLICIT_METRIC`

Defined for future integration but unavailable in the default design-data
adapter:

- `DESIGN_OBJECT_QUERY`
- `DESIGN_RELATION_QUERY`
- `SPECIALIZED_ANALYSIS`

## Binary and large-file contract

`ArtifactMetadata` may describe GDS, ODB, or other binary files. Binary files
cannot be returned through `read_excerpt`. Text search and excerpt reads are
bounded by a configured byte limit; callers receive a truncation marker rather
than an unbounded report.
