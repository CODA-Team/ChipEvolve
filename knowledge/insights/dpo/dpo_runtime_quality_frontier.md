# DPO Runtime-Quality Frontier

## Evidence Type

- `measured_observation`: formal three-case DPO/improve-placement runs on
  medium dense, dense image-style, and large row-rich placement cases.
- `reference_donor`: source-root patches under `patches/evolved_dpo/`.
- `policy`: future Agents should use stable patch names and mechanism ids, not
  private workbench commit hashes.

## Stable Donor Names

Use these names when assigning work:

- `neg014_hybrid_quality`: quality-ceiling donor.
- `neg015_staged_runtime`: staged fallback runtime donor.
- `neg017b_algo1_src_cache_runtime`: current balanced first-try donor.

Do not ask an Agent to check out local workbench commit hashes.  The durable
artifacts are the patch files and their documented apply bases.

## What Worked

`neg017b_algo1_src_cache_runtime` is the current practical donor when both
quality and runtime matter.

Mechanism:

- Preserve Algorithm-1 region-kick search, Algorithm-2 local DP repair, and
  Algorithm-3 transaction accept/rollback.
- Keep dry-run candidate scoring parallel and exact `trySwap` / journal /
  commit serial.
- Use `partial_sort` top-K reduction before exact candidate evaluation.
- Cache source-cell incident-edge current HPWL and source outside extrema per
  source batch.
- Score destination-only edges on the fly with thread-local scratch instead of
  pre-expanding all candidate edge references.

Observed formal result versus `neg015_staged_runtime` / `neg016`:

| archetype | final HPWL | runtime signal |
|---|---|---|
| medium dense | unchanged | modestly faster |
| dense image-style | unchanged | modestly faster |
| large row-rich | unchanged | modestly faster |

This is a runtime-quality donor, not a new final-HPWL breakthrough.

## What Did Not Work

Avoid blindly precomputing full per-candidate edge-reference lists.  The first
cache prototype improved some large-case dry-run costs but made the medium
dense case slower because it shifted too much work into serial candidate setup.

Avoid expanding Algorithm-2 DP parallelism as the next default action.  Logs
showed DP parallel sections were not the main runtime bottleneck.  DP can still
be useful for correctness and local repair, but the next high-ROI work is not
more DP threading by itself.

## Remaining Quality Gap

`neg014_hybrid_quality` remains the quality-ceiling donor on some dense and
large cases because it pays for stronger fallback descent.  `neg017b` keeps the
staged fallback policy, so it is faster but can give back final HPWL versus
the quality donor.

The next high-value direction is selective fallback restoration:

- Start from `neg017b_algo1_src_cache_runtime`.
- Detect high-ROI transactions where cheap `gs/vs` fallback leaves large
  recoverable HPWL.
- Pay for stronger forward or reverse reorder fallback only on those
  transactions.
- Keep aggregate logs for fallback calls, fallback gain, fallback runtime,
  Algorithm-1 dry-run runtime, and exact final HPWL.

Do not restore the full quality fallback globally unless the active case has a
large enough runtime budget and the strict metrics justify it.

## Patch Selection Rule

- Use `neg017b_algo1_src_cache_runtime` as the default first patch when final
  HPWL and runtime both matter.
- Use `neg014_hybrid_quality` when finding the quality ceiling matters more
  than runtime.
- Use `neg015_staged_runtime` mainly as a review base or when a Student wants
  to inspect the staged fallback mechanism separately.

Always rerun the active case and report canonical stage-wise HPWL, runtime,
avg/max displacement, legality, and DPL kernel logs before promoting a donor.
