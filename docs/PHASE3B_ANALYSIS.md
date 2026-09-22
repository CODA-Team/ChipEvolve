# Phase III-B — Analysis Understanding

## Scope

This slice answers a deliberately narrow set of timing questions through a
typed, read-only `AnalysisProvider`:

- scalar WNS and TNS timing metrics;
- bounded timing paths, optionally filtered by a slack threshold.

It does not infer root causes, traverse a timing graph, parse SPEF/STA output,
launch a tool, or mutate a design.

## Contract

`TimingMetricObservation` and `TimingPathObservation` are separate from the
Phase III-A structural design objects. Each result carries:

- `AnalysisScope`: design, run, stage, and corner where available;
- `AnalysisProvenance`: provider, locator, observation time, and optional SHA-256;
- a typed value and completeness marker.

`AnalysisProvider` exposes only `get_timing_metrics` and `get_timing_paths`, with
a bounded path limit. `FixtureAnalysisProvider` is used for deterministic tests;
`UnavailableAnalysisProvider` advertises no capability and returns no evidence.

## Query behavior

The parser recognizes timing summaries and path questions as `ANALYSIS_QUERY`.
The collector converts provider results to `SPECIALIZED_ANALYSIS` evidence with
citations. Partial observations are retained for audit but produce
`NEEDS_MORE_DATA` for the current-analysis requirement. Missing providers and
wrong design scopes produce the same structured refusal, never a guessed path
or slack.

## Verification

```bash
PYTHONPATH=src:. python -m query_agent.benchmark benchmarks/phase3b
```

The benchmark has five deterministic cases covering scalar metrics, path
filtering, missing providers, and wrong design scope; all five pass.
