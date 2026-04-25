# AGENTS.md

This file is for Codex/agent execution. For human setup and quick start, use
`README.md`.

This repo is the standalone control plane for `dpl_evolve`. It is not an ORFS
submodule and should not be treated as one.

## Runtime Roots

Every script resolves runtime through these roots:

- `DPL_EVOLVE_AGENT_ROOT`: this repo.
- `ORFS_ROOT`: the external OpenROAD-flow-scripts workspace.
- `DPL_EVOLVE_STATE_ROOT`: mutable runtime state, builds, checkpoints, packets,
  operations, and variant binaries.

Machine-local values belong in untracked `env.sh`, using `env.sh.example` as
the template. Do not hardcode local paths in tracked scripts or docs.

Optional convenience only:

- `$DPL_EVOLVE_AGENT_ROOT/.mounted_orfs`

Do not introduce another runtime model.

Important boundary:

- ORFS is the interaction workspace. Agents may read it and may write runtime
  artifacts under `DPL_EVOLVE_STATE_ROOT`, which defaults to
  `$DPL_EVOLVE_AGENT_ROOT/.dpl_evolve_state`.
- Agents must not edit tracked ORFS flow files, design configs, Makefiles,
  evaluator wrappers, or the `tools/OpenROAD` submodule as source-of-truth
  changes while designing a family.
- Family source experiments should be materialized as private variant source
  trees under `DPL_EVOLVE_STATE_ROOT`. If an experiment works, encode the
  durable recipe back in this control repo as a generator, family patch,
  algorithm card, router rule, or robustness note.

## Loop-Driven Patch Contract

When an outer Python loop invokes Codex, the loop already owns:

- prepare and patch application
- flow variant discovery
- snapshot validation
- checkpoint restore
- build
- evaluator execution
- scoring and accept/reject

Codex owns only one thing:

- make one bounded source patch, then stop

## Minimal Read Set

For a bounded patch turn, read only:

- `$DPL_EVOLVE_PACKET_DIR/current_run_packet.md`
- `$DPL_EVOLVE_AGENT_ROOT/skills/patch_rules.md`
- the active `problem.yaml`
- the one target source file named by the packet

The packet is authoritative for the selected family, source symbol, allowed
line window, recent failures to avoid, and whether the target is a materialized
family variant. Follow that route instead of choosing a different target after
local exploration.

Patch after those focused reads. Do not start with a repo survey.
Do not use `README.md` as bounded-patch context.

## Do Not Read During A Bounded Patch

- `tasks/archive/*`
- `knowledge/stage_context/*`
- `knowledge/delta_ledger/*`
- `knowledge/design_profiles/*`
- `flow/Makefile`
- `flow/scripts/*`
- `flow/designs/*/config.mk`
- git history
- broad repo status

Those paths are for flow debugging or project maintenance, not for normal
code-evolve turns.

## Patch Surface

Preferred target files:

- `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizer.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizerPass.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/NegotiationLegalizer.h`
- `tools/OpenROAD/src/dpl_evolve/src/Opendp.cpp`
- `tools/OpenROAD/src/dpl_evolve/src/Opendp.tcl`

Do not edit classic `tools/OpenROAD/src/dpl/` for this project.

Family-specific implementations, such as LEGALM, must live in materialized
variant source trees. Do not reintroduce them into the clean main
`dpl_evolve` base.

## Algorithmic Evolve Standard

Bounded does not mean timid. The goal is real algorithm-level evolution of
`dpl_evolve`, not parameter twiddling.

Good patches change one clear mechanism, such as:

- candidate generation or candidate ordering
- legality recovery and stuck-cell escape
- negotiation ordering and active-set growth
- objective/proxy-cost structure
- HPWL/runtime/displacement/timing tradeoff logic
- guarded local refinement with legality preservation
- telemetry that exposes why a legalizer succeeds or fails

Weak patches only change a constant or widen/narrow one existing loop without a
mechanistic hypothesis. They are acceptable as calibration probes, but they
should not be treated as the main evolve result.

For every algorithmic patch, the final response or manifest must say:

- mechanism changed
- source symbol touched
- expected effect on HPWL, timing, runtime, and legality
- expected failure mode
- rollback condition

Prefer bold but bounded changes over tiny safe edits. The evaluator, preflight,
checkpoint, and rollback system exist so agents can try meaningful algorithmic
ideas without corrupting ORFS or the final scoring protocol.

## Current Base-Family Tuning Phase

The current phase is not an idea-bank expansion phase. Do not use broad
algobank composites, self-evolving prompt variants, or many small constant
changes as base-family work. Those records are evidence for what to avoid or
what mechanism might be worth isolating; they are not robust base
implementations.

Base-family work must first make a small number of serious algorithms hard and
reliable. A candidate is useful only if it has a coherent algorithmic path on
medium and large cases, not just a good `aes` smoke result. Legal-but-worse is
not success: if HPWL, runtime, displacement, or timing proxy is materially
worse than the same-run baseline, the candidate is a repair target or reject,
not a base.

For this phase, prioritize:

- scale-safe negotiation search and active-set control;
- objective/ranking changes that improve HPWL or timing without displacement
  outliers;
- LEGALM only after its own legality failure is instrumented and fixed;
- localized swap only as opt-in polish after a legal runtime-stable parent;
- priority escape only when a real stuck/no-valid-candidate failure is present.

Do not promote:

- fallback-to-diamond or fallback-to-default behavior;
- full-grid scans or full pair enumeration;
- algobank mixture variants whose mechanism cannot be isolated;
- small-case aggressive changes that hurt `jpeg`, `ariane133`, or `bp_quad`;
- build-only or aes-only evidence.

## Family Router Guidance

Choose the starting family from the case shape and first strict-run evidence.
Do not pick a family by browsing the repo or by changing evaluator commands.
All evolve candidates must execute the same `detailed_placement_evolve` strict
entrypoint; family differences live behind that entrypoint in the private
linked `dpl_evolve` implementation.

Use this case router before proposing a patch:

| Case regime | First family to try | Good follow-up | Avoid first |
| --- | --- | --- | --- |
| Small clean cases such as `aes` | `search_narrow_runtime` or light `netaware_objective` | `localized_swap` only after legal HPWL signal remains | Heavy LEGALM or global postopt |
| Small/medium logic such as `ibex` | `netaware_objective` | `priority_escape` if current-location fallback appears | Pure constant tuning |
| Medium/high-net cases such as `jpeg` | `netaware_objective` with fanout caps | `priority_escape` for stuck clusters, then guarded `localized_swap` | Full-group swap enumeration |
| Large timing-stressed cases such as `ariane133` | `priority_escape` or runtime-aware search | Net-aware objective only after runtime is stable | Wide postopt as the first move |
| Very large stress cases such as `bp_quad` | `priority_escape` with telemetry, pruning, and bounded search | Runtime cache/prune, hotset selection, no-valid-candidate recovery | Normal small-case polish families |
| Cross-process follow-up such as ASAP7 | Reuse a family that already worked on matching Nangate45 size/regime | Retune only after the mechanism transfers | Brand-new broad algorithm without a Nangate45 signal |

Use this family meaning table when reading a packet:

| Family | Use when | Patch character |
| --- | --- | --- |
| `search_narrow_runtime` | No strong failure signature yet and runtime must stay bounded | Search-policy or candidate-count control, not just lower weights |
| `netaware_objective` | Legal placement exists but HPWL or timing proxy is poor | New objective information such as local HPWL delta, endpoint guards, or net anchors |
| `priority_escape` | The run shows stuck cells, late convergence, no valid candidates, or repeated fallback | Main-pass recovery, active-set ordering, escape candidates, or rollback-safe multi-cell moves |
| `localized_swap` | The design is already legal and needs local HPWL/displacement polish | Transactional local refinement with hard legality and runtime guards |
| `legalm_engine` | A structurally different materialized source family is worth comparing | Initializer, partitioning, ALM repair, or refinement changes behind the same evolve command |

Do not treat these families as parameter presets. They are algorithmic
directions. A valid family patch should introduce or remove a mechanism,
change a decision policy, change the search space, or change the objective
signal available to the legalizer.

## Scale-First Algorithm Constraint

Base families must be designed for integrated-circuit scale by default.  A
family is not a robust base if it only wins on small cases or if its large-case
story is to route around the evolved algorithm.  `aes` and other small designs
are useful calibration probes, but they must not dominate the family objective.
Use them to catch build, legality, and obvious quality regressions; promote a
base family only when its mechanism is also compatible with medium and
large-stress cases such as `jpeg`, `ariane133`, and `bp_quad`.

Do not use fallback-to-diamond or fallback-to-default as the normal way to pass
large designs.  Fallbacks may exist only as diagnostic safety fuses that produce
evidence when an experiment is otherwise stuck.  They are not evidence that the
family itself scales.  A scalable family must adapt its own algorithmic path:
bounded candidate generation, row or spatial buckets, component-local active
sets, dirty-region rechecks, hotset refinement, capped repair queues,
transactional rollback, and explicit complexity bounds.

Small-case aggressive variants are allowed as exploration tools.  They can
help discover a useful objective term, search move, or refinement mechanism,
but they should remain exploration variants until the same mechanism is made
scale-safe.  If a strategy improves only `aes` while slowing or destabilizing
`jpeg`/`bp_quad`, record it as a small-case tuning idea, not as a base-family
improvement.

## Robust Base Versus Exploration Family

Do not assume every implemented family is safe as an initial parent. The
current robust-base set is deliberately small:

- `search_narrow_runtime`
- `netaware02_history_sqrt_anchor` as the safe light objective/search base
- `netaware03_row_guard_frontier` as a quality-biased secondary candidate
- `negotiation_row_bucket_active_set` as the current scale-safe negotiation
  candidate
- runtime-safe `priority_escape` variants only after their guards are proven
- scale-safe `legalm_engine` variants only after Stage1/Stage2/Stage3
  themselves pass legality and medium/large gates without routing around
  LEGALM

Current compression decisions:

- Current `netaware_objective` variants are objective/search composites, not
  true db-net/fanout/HPWL inspection yet. Use `netaware02` as the safe base.
  `netaware03` has strong HPWL on aes/jpeg but is slower on jpeg and times out
  on bp_quad, so it is quality-biased opt-in. Demote `netaware06` and
  `netaware08` from robust-base consideration because they regress quality.
- Current `priority_escape10` recipes are repair candidates, not default
  bases. Evidence showed one candidate timing out on `jpeg` and another
  producing severe HPWL degradation. A priority-escape base must first remove
  expensive legality checks from sort comparators, cap candidate probes, make
  row-edge/midpoint/cardinal probes fallback-only, and add large-design
  active-set guards.
- `localized_swap` is follow-up polish only. The existing runnable
  `localswap*` recipes enable post-legalization polish or cost/sort composites,
  while the underlying `cellSwap()` still has full same-shape pair enumeration.
  Do not use it as an initial family until hotset/bucket search, transactional
  rollback, candidate caps, and jpeg/bp_quad runtime gates are proven.
- `legalm_engine` is an important base-family direction, but it is not promoted
  until its own Stage1/Stage2/Stage3 algorithms are scale-safe. It must still
  use the same `detailed_placement_evolve` command. Current evidence says
  `legalm01_hpwl_pinwide` passes `aes` but fails `jpeg`; a Stage1 full-window
  search can pass `jpeg` but has a large displacement outlier and is too broad
  to count as a scalable base. The next LEGALM base must use bounded
  candidate-generation and repair, not full-grid scans.
- `bp_quad` is a runtime-stress gate. If the clean negotiation path or a
  family variant times out before producing metrics, treat that as a
  large-design algorithm failure requiring active-set pruning, component-local
  search, dirty-region scans, or runtime-safe candidate caps. A diagnostic
  diamond/default run can finish quickly on the same snapshot, but that only
  proves the snapshot is runnable; it does not validate the evolve family. Do
  not hide the failure by changing evaluator commands or by making fallback the
  base behavior. The current full-metrics stage for `bp_quad` needs about a
  `900s` robustness timeout unless metrics collection is optimized separately.

The default matrix wrapper runs the `robust_base` group. Use full groups such
as `family40`, `localized_swap10`, or `legalm10` only for explicit exploration
or robustness repair work.

For focused validation of the currently usable family set, prefer the
`flow_ready_candidates` group.  It includes the registered
`negotiation_row_bucket_quality_frontier_r5` candidate plus conservative
comparison starts.  Do not add a family to this group unless it can be generated
by the matrix script and uses the common `detailed_placement_evolve
-use_negotiation` entrypoint.

## Context Hygiene

Start from compact cards, not raw artifacts. For family iteration or
maintenance, default to `family_robustness/ROBUST_BASE_DECISION_20260425.md`,
`knowledge/algorithm_cards/base_family_cards.yaml`,
`knowledge/algorithm_cards/`, and `knowledge/family_components/*.yaml`. Use
`family_robustness/CONTEXT_HYGIENE_20260425.md` for the current directory
hygiene map and pollution inventory.

Do not broad-read runtime artifacts, replay logs, archive prompts, or idea
banks before those cards. In particular, `family_robustness/*/eval_smoke_*`,
`knowledge/replay_bank/`, `tasks/archive/`, `variant_ideas/`, and
`family_ideas/` are opt-in evidence or ideation surfaces, not default context
for a new agent.

Small-case smoke is not base-family success. Treat `aes` smoke as build,
legality, and obvious-regression evidence only; a base family needs medium and
large-case support, or an explicit gate/debug note explaining why the missing
large-case result is infrastructure rather than algorithm quality.

Never edit tracked ORFS files or the OpenROAD submodule directly while
designing a family. ORFS is allowed as the interaction workspace, and
`DPL_EVOLVE_STATE_ROOT` should normally live under this agent repo. Legacy ORFS
runtime state may be backed up for inspection, but new durable family work
belongs in this control repo as a generator, patch rule, algorithm card, or
robustness note. Tests may generate private variant source trees and private
OpenROAD binaries under the state root; those are artifacts, not source-of-truth
edits.

## First-Run Decision Rule

Run one strict baseline or clean-family probe first, then decide patch depth:

| First-run observation | Treat as | Next move |
| --- | --- | --- |
| Build fails or binary path is wrong | Infrastructure failure | Fix source routing, variant build, or private binary binding before any algorithm work |
| Metrics are missing or malformed | Evaluator/artifact failure | Fix run plumbing; do not infer algorithm quality |
| Placement is illegal | Algorithmic failure | Change candidate generation, legality recovery, rollback, or active-set order |
| Many no-valid-candidate or current-location fallback events | Search failure | Use `priority_escape`; add bounded escape candidates or stuck-cell state |
| Runtime timeout or sharp runtime regression | Search explosion | Add pruning, hotsets, caching, beam caps, or component-local search |
| Legal and runtime-stable, but HPWL/timing is poor | Objective/ranking weakness | Use `netaware_objective`; add topology-aware cost or candidate ranking |
| Legal and HPWL improves, but displacement outliers grow | Refinement needs guards | Add displacement-aware acceptance or guarded `localized_swap` rollback |
| Legal, HPWL is close, and noise is small | Calibration case | One micro-tune is allowed only after identifying the working mechanism |
| Same family repeatedly builds but does not improve | Family mismatch | Record the failure signature and switch family or target symbol |

In short: first use results to identify the failure mode, then choose the
smallest algorithmic mechanism that addresses that failure. Micro-tuning is a
second-order refinement, not the default evolve move.

Micro-tuning is allowed only under all of these conditions:

- A previous algorithmic patch from the same family was legal and improved at
  least one primary metric.
- The planned change is tied to the successful mechanism, such as tightening a
  cap, normalizing a new cost term, or adjusting a guard threshold.
- The change is logged as a follow-up calibration, not as a new algorithmic
  family result.
- Only one or two calibration attempts are made before switching back to a
  mechanism-level change.

If those conditions are not met, make an algorithm-level patch instead of a
constant-only adjustment.

## Binary Rule

Clean runs may use the root OpenROAD binary.

Variant/family runs must use an explicit private binary:

```bash
source "${DPL_EVOLVE_STATE_ROOT}/variants/<agent_id>/variant_env.sh"
python3 "$DPL_EVOLVE_AGENT_ROOT/adapters/science_codeevolve/evaluator.py" \
  --openroad-binary "${OPENROAD_BINARY}" ...
```

Never assume `tools/install/OpenROAD/bin/openroad` is correct inside a variant
loop.

## Build Model

Preferred path:

```bash
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_core.sh"
"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_core.sh" 10
"$DPL_EVOLVE_AGENT_ROOT/scripts/configure_openroad_variant_relink.sh" \
  --variant-root "${DPL_EVOLVE_STATE_ROOT}/variants/<agent_id>" \
  --dpl-src /abs/path/to/variant/dpl_evolve
source "${DPL_EVOLVE_STATE_ROOT}/variants/<agent_id>/variant_env.sh"
"$DPL_EVOLVE_AGENT_ROOT/scripts/build_openroad_variant_relink.sh" --threads 10
```

This rebuilds only variant-owned `dpl_evolve` objects, relinks a private
`openroad`, and symlinks common-core `sta` when available.

For offline evidence sweeps, prefer the matrix runner defaults: 8 parallel
evaluator jobs and 10 OpenROAD threads per job. Do not exceed that by default;
large cases should become timeout evidence rather than blocking the whole queue.

## Evaluation Rule

Use strict legalization-only first. The reusable snapshot must already exist:

```text
flow/results/<platform>/<design>/<FLOW_VARIANT>/3_4_place_resized.odb
```

The baseline wrapper reuses that snapshot. It should not rebuild upstream
Yosys/place during strict evaluator runs.

Primary result:

```text
flow/reports/<platform>/<design>/<FLOW_VARIANT>/dpl_evolve_baseline/<run_tag>/metrics.json
```

Hard failures:

- preflight diff-scope violation
- build failure
- evaluator failure
- legality failure
- missing or malformed `metrics.json`
- uncontrolled displacement/runtime regression

Before evaluator execution, the loop validates the Codex diff against the
packet-selected target file/symbol. Edits to ORFS flow files, evaluator logic,
classic `dpl`, or broad unrelated source paths are rejected before build.
