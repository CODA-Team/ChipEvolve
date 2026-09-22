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
| `DesignObjectRef` / `DesignInstance` / `DesignNet` / `DesignPin` | Stable typed design identities |
| `DesignConnection` / `DesignLocation` / `DesignRegion` | Read-only relationships and physical scope |
| `AnalysisScope` / `AnalysisProvenance` | Explicit scope and origin for analysis results |
| `TimingMetricObservation` / `TimingPathObservation` | Bounded timing-analysis evidence |
| `DiagnosisScope` / `DiagnosisProvenance` | Scope and origin of one finding |
| `DiagnosisFinding` / `DiagnosisSupport` | Diagnostic claim and its citable support |

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

Phase III-A design objects are intentionally narrower than a physical-design
database. `DesignDataProvider` exposes typed lookup and relationship operations
for instances, nets, pins, locations, fanout, connections, and regions. The
provider owns translation from its external representation; application code
never receives a mutable provider dictionary or executes a parser.

## Phase I capabilities

Available when a provider advertises them:

- `DOMAIN_KNOWLEDGE`
- `ARTIFACT_DISCOVERY`
- `TEXT_SEARCH`
- `EXPLICIT_METRIC`

Defined as explicit capability boundaries (the default null adapters do not
advertise them):

- `DESIGN_OBJECT_QUERY`
- `DESIGN_RELATION_QUERY`
- `SPECIALIZED_ANALYSIS`

Phase III-B adds a fixture-backed `AnalysisProvider` for
`SPECIALIZED_ANALYSIS`. It exposes only scalar WNS/TNS and bounded timing
paths. Incomplete results are retained as partial evidence and cannot satisfy
the current-analysis requirement; no timing graph, parser, tool launch, or
diagnosis is included.

Phase IV adds a fixture-backed `DiagnosisProvider`. A `DiagnosisFinding` must
contain at least one typed support item, explicit design/run/stage scope, and
provenance. The application does not treat a claim as answerable when the
finding is incomplete or absent; it also does not add a numeric confidence
score or infer a cause from experience.

## Binary and large-file contract

`ArtifactMetadata` may describe GDS, ODB, or other binary files. Binary files
cannot be returned through `read_excerpt`. Text search and excerpt reads are
bounded by a configured byte limit; callers receive a truncation marker rather
than an unbounded report.
