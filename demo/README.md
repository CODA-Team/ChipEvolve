# Phase I five-minute demo

From the repository root:

```bash
./demo/demo_phase1.sh
```

The script is read-only with respect to the repository. It runs the deterministic
benchmark and a local evidence-insufficiency example. To show managed-run
metrics and status, set `QUERY_AGENT_KERNEL_URL` to an execution-foundation
public read API URL. To show the real knowledge provider, set
`EDA_CORPUS_ROOT` to a checked-out EDA-Corpus directory.

The three stories are:

1. Experiment metric query: a run/stage-scoped metric with an execution
   citation (when the public API URL is configured).
2. Evidence insufficiency: a root-cause question returns `NEEDS_MORE_DATA`
   because design relations are unavailable.
3. Knowledge query: a real EDA-Corpus QA or prompt-script row is returned with
   its dataset path, row number, and source hash.
