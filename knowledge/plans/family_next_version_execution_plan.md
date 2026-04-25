# Next Family Execution Plan

This plan defines how the next `dpl_evolve` family generation should be
implemented and validated.  It is intentionally more operational than a
research note: a future agent should be able to use it to decide what to edit,
what to build, what to measure, and when to reject a candidate.

## Operating Model

All family work keeps the same command entrypoint: run detailed placement
evolve, then run the strict evaluator.  Different families are different
algorithmic forms behind the same evolve command, not different flow scripts.

The stable model is:

1. Prepare an external ORFS workspace in place.
2. Keep classic OpenROAD `dpl` unchanged.
3. Materialize or generate only private `dpl_evolve` source variants.
4. Reuse the common OpenROAD core build.
5. Recompile the variant `dpl_evolve` objects.
6. Relink a private `openroad` binary for each variant.
7. Evaluate with an explicit binary path.
8. Store runtime state under `DPL_EVOLVE_STATE_ROOT`, not in ORFS source.

Do not treat branch names as the source of truth.  Anchors and source records
decide what a variant was built from.

## Flow-OK Definition

A family candidate is flow-ok only if all of the following are true:

- The source-of-truth shape is declared: generator variant, clean-base patch,
  overlay chain, materialized sidecar, repair candidate, or polish-only.
- The variant can materialize into a private `dpl_evolve` source tree.
- The lightweight relink path produces a private `openroad` binary.
- The evaluator is invoked through the common detailed-placement evolve
  command and that explicit private binary.
- The run confirms the intended engine path and does not silently fall back.
- Metrics and evaluator JSON are produced or a structured failure signature is
  recorded.
- Legal placement is a hard gate for promotion.
- Large-case performance is not treated as optional.  Small-case wins cannot
  promote a family that is slow, unstable, or fallback-dependent on large
  designs.

## Gate Ladder

Use the same ladder for every candidate unless a family-specific note below
says otherwise.

1. Build gate: materialize or generate the source, relink the binary, and
   record the binary path.
2. AES smoke: fast legality and engine-path check.
3. JPEG quality guard: check HPWL, displacement tail, and runtime on a
   medium-size case.
4. Ariane strict gate: check the large-case path under the strict evaluator.
5. BP_QUAD split gate: run legalizer-only first, then run full metrics with a
   longer timeout.  Do not classify full-metrics timeout as legalizer failure
   without evidence.
6. Cross-case decision: promote only when failures are explained and the
   family does not rely on fallback or small-case-only behavior.

Parallel sweeps can run up to eight variants at once if the machine is idle,
with about ten build threads per variant.  For full metrics on large cases,
lower concurrency if report generation becomes the bottleneck.

The shared harness entrypoint is:

```bash
./scripts/run_family_base_gate.py \
  --family <family> \
  --cases aes_nangate45 jpeg_nangate45 ariane133_nangate45 bp_quad_nangate45 \
  --legalizer-only-first \
  --eval-timeout-sec 900 \
  --force
```

The first registered R6/netaware14/priority/localized ids are
`bringup_alias_not_algorithm_promotion` aliases.  They are useful for checking
materialize/build/eval plumbing, but they must be replaced by real mutation
bodies before their results can be cited as algorithm evidence.

## Required Attempt Record

Every experiment should leave enough evidence to rebuild the judgment:

- family id and parent source record;
- source kind and materialization command;
- touched files and touched symbols;
- private variant root and private OpenROAD binary;
- compile/relink logs;
- evaluator command and run tag;
- metrics JSON and evaluator JSON;
- engine-path confirmation;
- family-specific telemetry;
- short decision: promote, repair, donor-only, polish-only, or reject.

## Family Plans

### Negotiation R6: Two-Pass Frontier and Row Index

Target id:

```text
negotiation_row_bucket_quality_frontier_r6_twopass_rowindex
```

Source model:

- Current parent is the generated r5 matrix variant.
- Implement R6 in the matrix generator, not as a partial patch over a local
  materialized tree.

Main algorithmic change:

- Replace the online frontier with a true two-pass top-K frontier.  First
  enumerate bounded legal candidates and keep the top cheap candidates.  Then
  score only that bounded set with net-anchor, local HPWL, and displacement
  tail terms.
- Replace per-iteration full row-bucket rebuilds with a persistent or
  incremental row index where practical.
- Add row-edge or free-segment probes as bounded candidate sources, not as a
  fallback that hides failure.

Required telemetry:

- candidates seen and valid;
- candidate cap hits;
- no-valid and returned-current counts;
- top-K frontier collected and scored;
- dirty scan added cells;
- row-index rebuild or update time;
- legalizer-only runtime.

Promotion gates:

- AES smoke must pass.
- JPEG must not trade HPWL for a displacement-tail spike.
- Ariane must run under strict evaluation.
- BP_QUAD must pass legalizer-only before full metrics is attempted.

### Netaware14: Row-Edge Shortlist HPWL

Target id:

```text
netaware14_rowedge_shortlist_hpwl
```

Source model:

- Current netaware12 is an overlay over an earlier netaware parent.
- Before promotion, collapse the chain into a standalone generator path or a
  clean materializable patch.

Main algorithmic change:

- Keep network-aware scoring, but make it a bounded ranking signal, not a full
  traversal cost on every candidate.
- Build a cheap frontier from current-blend, row-edge, history-runtime-trim,
  and anchor probes.
- Apply cached local HPWL only to the shortlist.
- Use per-cell net proxy caches, high-fanout skip, and per-candidate net eval
  caps.

Required telemetry:

- eligible cells;
- shortlist size;
- local HPWL candidate count;
- net eval count;
- high-fanout skipped nets;
- cache hit or miss count;
- displacement guard rejects;
- runtime overhead relative to the same-run parent.

Promotion gates:

- AES, JPEG, and Ariane must pass strict same-run comparisons.
- Runtime overhead should be below roughly 10 to 12 percent before BP_QUAD is
  used as a full gate.
- JPEG max displacement must not grow materially.

### LEGALM R6: Row-Segment Batch Assignment

Target id:

```text
legalm_r6_row_segment_batch_assignment
```

Source model:

- Start from the committed LEGALM materialized sidecar.
- Keep the R4 stale-overflow counter fix.
- Do not promote the R5 scalar Stage1 quality guard as the base algorithm.

Main algorithmic change:

- Replace greedy Stage1 nearest-window placement with row-segment batch
  assignment.
- Build free intervals from rows, fixed blockages, and fences.
- Bucket cells by region, component, height, row band, and coarse anchor.
- Order scarce or high-risk cells first.
- Reserve row intervals during assignment.
- Let Stage2 and Stage3 repair unresolved overflow or high-cost outliers,
  rather than rescue a globally poor Stage1 order.

Required telemetry:

- Stage1 assigned ratio;
- unassigned cells;
- bucket count and max bucket size;
- candidate cap hits;
- assignment conflict repairs;
- Stage2 hotset size;
- Stage3 moved cells;
- displacement p95, p99, and max.

Promotion gates:

- AES must pass with the same evolve entrypoint and no fallback.
- JPEG must show controlled displacement tail.
- BP_QUAD starts with legalizer-only, then full metrics.

### Priority Escape: Telemetry-First Repair

Target id:

```text
priority_escape_telemetry_first
```

Source model:

- This is a repair operator, not a base parent.
- It should layer on top of a runtime-safe negotiation parent.

Main algorithmic change:

- Add structured `findBestLocation` results and per-cell stuck/no-valid state
  before enabling escape.
- Normal cases should not trigger escape.
- Escape candidates are bounded row-edge, nearest free interval, dirty-frontier,
  and guarded anchor probes.
- Every escape move must be rollback-safe.

Required telemetry:

- stuck cells;
- no-valid cells;
- returned-current streaks;
- escape attempted, accepted, rejected by guard, and rolled back;
- stuck count before and after escape;
- normal-case zero-trigger proof.

Promotion gates:

- AES and JPEG should show zero or near-zero escape triggers.
- A real or synthetic stuck/no-valid gate must show attempted and accepted
  escape moves that reduce stuck count.
- Large cases are run only after the parent family is runtime-safe.

### Localized Swap: Transactional Polish

Target id:

```text
localized_swap_transactional_polish
```

Source model:

- This is polish-only.  It is never the standalone legalizer base.
- Run only after a legal parent exists.

Main algorithmic change:

- Select a bounded hotset by local HPWL potential, displacement outliers, or
  timing proxy.
- Generate same-height, nearby-row, nearby-net-cluster pairs with hard caps.
- Tentatively apply a swap, check local legality and score delta, then commit
  or rollback.
- Skip polish when parent runtime or displacement is already outside guard.

Required telemetry:

- parent legal status;
- skip reason;
- pairs evaluated;
- accepted swaps;
- rollback count;
- post-polish HPWL and displacement delta;
- wall-time budget used.

Promotion gates:

- AES, JPEG, and one larger legal-parent case must pass.
- BP_QUAD only runs after the parent legalizer is already proven runtime-safe.

## Knowledge Update Rule

After each gate, update the family knowledge in three layers:

1. Raw run record: exact commands, binary, logs, metrics, and artifacts.
2. Observation: what changed, what improved, what regressed, and what failed.
3. Family card: scope, confidence, blockers, and next action.

Do not put raw logs into the agent prompt.  Convert them into compact,
evidence-backed cards and keep the raw artifacts in runtime state.
