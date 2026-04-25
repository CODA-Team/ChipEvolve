# CPU LEGALM Reference Data Model

This is a proposed minimum data model for an external high-performance CPU
LEGALM-style implementation. It is deliberately framework-neutral: no OpenROAD
classes, no database objects, no evaluator hooks.

The implementation may define these as C++ structs/classes rather than exactly
copying this syntax.  What matters is that the algorithm can be driven from
these facts and can return a complete placement plus diagnostics.

## Coordinate System

- Use integer DBU coordinates.
- Cell coordinates are lower-left.
- Row/segment `x1` is exclusive.
- Rectangles use `[x0, x1) x [y0, y1)`.
- `site_width` and `row_height` are DBU.
- Legal output cell locations must be site-aligned and row-aligned. Relaxed or
  near-legal outputs should say clearly which constraints remain unresolved.

## Core Objects

```cpp
struct Rect {
  int64_t x0;
  int64_t y0;
  int64_t x1;
  int64_t y1;
};

struct Row {
  int id;
  int region_id;          // -1 means default region.
  int64_t x0;
  int64_t x1;             // exclusive.
  int64_t y;
  int64_t site_width;
  int64_t row_height;
};

struct Segment {
  int id;
  int row_id;
  int region_id;
  int64_t x0;
  int64_t x1;             // exclusive.
};

struct Cell {
  int id;
  int region_id;          // -1 means default region.
  int64_t width;
  int64_t height;
  int64_t init_x;
  int64_t init_y;
  int64_t current_x;
  int64_t current_y;
  bool fixed;
  bool movable;
  bool multi_row;
  bool timing_critical;
};
```

`Segment` may already exclude fixed blockages and obvious row/fence
violations. The algorithm should still be able to validate against fixed
rectangles for safety, especially for multi-row cells.

## Net Model

```cpp
struct Pin {
  int cell_id;             // -1 for fixed-point pins.
  int64_t offset_x;        // relative to cell lower-left if cell_id >= 0.
  int64_t offset_y;
  int64_t fixed_x;         // absolute if cell_id == -1.
  int64_t fixed_y;
};

struct Net {
  int id;
  double weight;
  std::vector<int> pin_indices;
};
```

High-fanout nets should be skipped, approximated, or cached. The algorithm
should report how many nets/pins were skipped or approximated.

## Problem Input

```cpp
struct LegalizationProblem {
  int64_t dbu_per_micron;
  Rect core;
  std::vector<Row> rows;
  std::vector<Segment> free_segments;
  std::vector<Rect> fixed_rects;
  std::vector<Cell> cells;
  std::vector<Pin> pins;
  std::vector<Net> nets;
};
```

Working assumptions:

- `cells` contains both movable and fixed cells if useful, but the output only
  needs locations for movable cells.
- `free_segments` are the preferred capacity representation.
- Fixed rectangles are the safety representation.
- Region/fence constraints are represented by `region_id` on cells, rows, and
  segments.

## Options

```cpp
enum class LegalizationMode {
  RelaxedGuidance,   // overlaps allowed; return good target locations.
  FullLegalize,      // try to return legal placement.
  RepairOnly,        // repair overflow/hotspots from current locations.
  PolishOnly         // legal parent only; bounded local improvement.
};

struct LegalizationOptions {
  LegalizationMode mode = LegalizationMode::FullLegalize;
  int max_threads = 1;
  bool deterministic = true;
  int seed = 0;
  int64_t max_runtime_ms = 0;       // 0 means no explicit wall budget.
  int64_t max_displacement_x = 0;   // 0 means implementation default.
  int64_t max_displacement_y = 0;

  double displacement_weight = 1.0;
  double hpwl_weight = 0.0;
  double overflow_weight = 1.0;
  double max_displacement_weight = 1.0;
  double timing_weight = 0.0;

  int max_outer_iterations = 0;     // 0 means implementation default.
  int max_candidates_per_cell = 64;
  int high_fanout_threshold = 64;
};
```

## Output

```cpp
enum class PlacementKind {
  Unchanged,
  Relaxed,
  NearLegal,
  Legal
};

struct CellPlacement {
  int cell_id;
  int64_t x;
  int64_t y;
  int status;       // 0 unchanged, 1 moved, negative means failed/unplaced.
};

struct LegalizationResult {
  PlacementKind kind;
  std::vector<CellPlacement> placements;
  int unresolved_overlap_count = 0;
  int moved_cell_count = 0;
  double hpwl_proxy_delta = 0.0;
  double avg_displacement_dbu = 0.0;
  double max_displacement_dbu = 0.0;
};
```

The implementation should return one placement record per movable cell. If a
cell cannot be placed, preserve its current location and set negative status.

## Telemetry

```cpp
struct LegalizationTelemetry {
  int stage1_assigned_count = 0;
  int stage1_unassigned_count = 0;
  int stage1_overflow_count = 0;
  int stage2_iteration_count = 0;
  int stage2_final_overflow_count = 0;
  int stage3_moved_count = 0;
  int candidate_cap_hit_count = 0;
  int high_fanout_skipped_count = 0;
  int row_segment_conflict_count = 0;

  double total_runtime_ms = 0.0;
  double stage1_runtime_ms = 0.0;
  double stage2_runtime_ms = 0.0;
  double stage3_runtime_ms = 0.0;

  std::string json_summary;
};
```

Telemetry should explain both success and failure. At minimum, include:

- effective objective weights,
- candidate caps,
- thread count,
- overflow by major stage,
- assignment conflict count,
- high-fanout handling,
- runtime by stage,
- final legality estimate.

## Algorithmic Expectations

A strong implementation should not be only a scalar-weight tweak. The current
working hypothesis is that it needs real scalable structure:

- Stage 1: relaxed/static-constraint projection or differentiable-style target
  guidance.  Movable overlaps may be allowed here.
- Stage 2: capacity-aware row/segment assignment, ALM/BGD-style overflow
  reduction, or another scalable overlap-removal mechanism.
- Stage 3: no-overflow refinement and bounded polish.

Important constraints:

- no full pair enumeration,
- no full-grid scan inside inner loops,
- bounded candidates per cell,
- row/segment data structures suitable for large designs,
- deterministic parallelism when requested,
- JPEG-class cases should be treated as the first real performance gate.

## Quality Targets

The first target is robustness and useful telemetry:

- AES is only smoke.
- JPEG should complete with runtime comparable to OpenROAD diamond order of
  magnitude.
- Displacement tail should not explode.
- HPWL should be competitive enough to justify further porting.
- If legality is partial, the remaining failure mode must be clear enough for a
  downstream repair stage.
