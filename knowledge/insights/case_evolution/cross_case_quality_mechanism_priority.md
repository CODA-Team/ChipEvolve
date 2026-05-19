# Cross-Case Quality Mechanism Priority

Evidence type: fixed-source replay of per-design evolved programs across
multiple technology, utilization, and design-scale settings.  This card records
feature-level lessons only.  It intentionally avoids benchmark-name routing,
local paths, raw result rows, and historical program aliases.

Use this card when Teacher wants to turn prior evolved programs into current
case search guidance.  It should be read together with
`runtime_light_final_hpwl_mechanism_priority.md`: this card says which quality
mechanisms transferred; the runtime-aware card says which ones should be tried
first under a practical runtime budget.

## Replay Calibration

Fixed-source transfer shows three distinct mechanism classes.

- `Broad exact-consumer quality donors`: these often produce the strongest
  average final-HPWL reduction when they run on a compatible placement basin.
  They usually spend substantially more runtime.  Use them when stage metrics
  show a large recoverable DPO basin, then rewrite with affected-net caches,
  top-K candidate caps, or narrower frontier windows.
- `Balanced producer-consumer donors`: these combine legalizer-output shaping,
  compact frontier or source-edge signals, and exact DPO transactions.  They
  are the best default inspiration when Teacher needs both quality and
  controllable runtime.
- `Runtime-light local closure donors`: these can be excellent on placements
  whose remaining HPWL is row-local or edge-local.  They are not universal
  donors.  Transfer them by matching design features, not by copying the whole
  historical source state.

The key evidence is final detailed-placement-flow HPWL, not stage-local HPWL.
A legalizer may slightly worsen `HPWLlg` while preserving a basin that a later
exact DPO consumer can repair strongly.  Conversely, a legalizer-stage win is
weak evidence if after-improve or final HPWL does not improve.

## Quality Mechanism Families To Prefer

### Producer-Guided Exact DPO Consumer

Best feature match:

- legalization produces a compact frontier, residual-net set, dirty row set, or
  source-edge set;
- after-improve HPWL still has a visible recovery opportunity;
- DPO accepts exact local moves when candidates are ranked by that frontier.

Implementation shape:

- keep producer state in native in-process structures tied to cells, nets, rows,
  or regions;
- rank only a bounded candidate set by frontier/residual evidence;
- exact-score top candidates with affected-net or journal HPWL;
- commit through local legality and rollback guards;
- log producer count, consumer probes, exact accepts, accepted gain, and runtime.

Promotion rule:

Promote only if final HPWL improves.  If producer counters are nonzero but exact
accepts are zero, mark the result as passive handoff or consumer failure.

### Recoverability-Shaped Legalizer Plus DPO Closure

Best feature match:

- legalization disturbs the global-placement basin too early;
- DPO has enough local structure to recover if the legalizer preserves better
  relative ordering or residual neighborhoods;
- stage metrics show a large gap between `HPWLlg` and `HPWLimprove`.

Implementation shape:

- modify row assignment, conflict repair, target release, or local closure so
  legalized states stay recoverable rather than merely legal;
- expose only accepted or high-confidence frontier records to DPO;
- let DPO choose exact moves instead of forcing producer targets blindly.

Promotion rule:

Treat this as a co-optimization mechanism.  Legalizer HPWL can be worse than
global or worse than a stage-only donor if the full flow is better and logs show
that DPO consumed the recoverable basin.

### Source-Edge And Selected-Segment Exact Reorder

Best feature match:

- residual HPWL concentrates near edge-critical cells, shifted cells, selected
  row segments, or boundary-active nets;
- a small number of exact reorders can be tested cheaply;
- broad replay would be too expensive or too noisy.

Implementation shape:

- select source-edge/frontier cells from accepted producer or DPO evidence;
- build small row/segment windows;
- exact-score reorder, pair, or endpoint polish candidates;
- stop by accepted-gain rate instead of fixed long tails.

Promotion rule:

This is a good runtime-controlled quality donor when exact accepts and accepted
gain are nonzero.  Do not credit ranking-only telemetry.

### Runtime-Light Local Closure

Best feature match:

- the default legalizer is close to a good final solution;
- row-local conflicts dominate;
- global or differential guidance creates more disruption than recoverability.

Implementation shape:

- keep Diamond or negotiation closure as the primary legalizer;
- add bounded exact same-row or adjacent-row repair around dirty rows,
  high-residual nets, or displacement outliers;
- rely on exact affected-net scoring and fast rollback.

Promotion rule:

Use as a guard or first local route, but do not let all Students chase the same
small local closure once gains flatten.

## Heavy Mechanisms That Need Runtime Discipline

These mechanisms can be valid quality donors, but Teacher should assign them
with a runtime-rewrite plan.

- broad exact DPO basin search;
- endpoint-level full-tail branch scoring;
- residual diversity replay with mirror-aware replay;
- scoped LSMC-style escape after deterministic descent is already live;
- large selected-window or multi-row exact enumeration.

Required discipline:

- cap windows, endpoints, candidates, and restart count;
- use affected-net or journal deltas instead of full HPWL rescans when possible;
- parallelize independent scoring only when acceptance remains deterministic;
- stop by accepted-gain rate, not by a fixed heavy tail;
- report whether extra runtime bought final HPWL rather than only more probes.

## Low-ROI Patterns To Downweight

Downweight these unless Teacher has a specific repair hypothesis:

- legalize-only wins whose final HPWL does not improve;
- mirror-only priority changes without accepted exact moves to preserve;
- guidance producers with zero downstream consumer accepts;
- critical-window or multi-row assignment previews that never commit exact
  improvements;
- passive metadata handoff that is not consumed by DPO;
- threshold or constant edits without a changed candidate generator, scoring
  function, transaction, producer, or consumer;
- broad random tails or repeated endpoint passes without accepted-gain evidence.

## Teacher Use

Before assigning routes, Teacher should classify the current case by evidence:

- if `HPWLlg` worsens but `HPWLimprove` can recover strongly, try
  recoverability-shaped legalizer plus exact DPO consumer;
- if final residue is localized, try source-edge or selected-segment exact
  reorder before broad replay;
- if all routes are small and runtime-light, allocate one Student to a heavier
  quality donor with caps and one Student to a runtime rewrite of the best
  quality donor;
- if a mechanism is live but weak after one real repair, switch mechanism
  family instead of stacking more threshold variants.

Student reports should state whether the implemented change is a producer,
consumer, handoff, transaction, endpoint-selection, or runtime-rewrite
mechanism, and should include enough counters for Teacher to decide whether the
next round should deepen, repair, or abandon that family.
