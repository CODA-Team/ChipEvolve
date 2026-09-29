# EDA-AI Data Interface — CONTRACT v0.1

状态：**冻结（阶段 A）** · 冻结日期 2026-09-30 · 适用实现 commit：`ba8dd61`+
本文件是外部调用方唯一需要读的接口规范。它规定"模型看到什么"，不规定我们内部怎么实现。

> 变更规则：新增字段/新增 tool 属于向后兼容，允许；改变已有字段含义、删除字段、改变状态枚举属于破坏性变更，必须提升 `contract_version`。

---

## 0. 服务边界

Data Foundation 只回答 **结构化 EDA 事实**。它不诊断、不建议、不解释"为什么"。
所有数据来自原始 artifact；任何返回都能通过 `evidence` 指回原始文件与哈希。

调用方式（同一套语义，三种壳）：HTTP JSON（当前可用）、Python client（阶段 C）、JSON tool schema（阶段 C，供 function calling）。

- 当前地址：`http://127.0.0.1:8860`
- `contract_version`: `"0.1"`
- 所有响应 `Content-Type: application/json`，UTF-8。
- **永远不返回宿主路径。** 文件只以 artifact identity + logical path 出现。

---

## 1. 通用响应信封

除 `/health` 外，每个 tool 返回：

```json
{
  "contract_version": "0.1",
  "tool": "get_timing_path",
  "scope": {
    "design_id": "gcd",
    "revision_id": "native-reproduction-20260929",
    "run_id": "run-aebb41c…",
    "snapshot_id": "gcd-nangate45-native-route-20260929",
    "stage": "route"
  },
  "target": {"type": "timing_path", "id": "path:0"},
  "status": "available",
  "missing": [],
  "data": { },
  "evidence": [ ],
  "limitations": [ ]
}
```

| 字段 | 语义 |
|---|---|
| `scope` | 该回答覆盖的事实边界。缺字段表示"该维度未声明"，不是通配。 |
| `target` | 这次查询指向的对象；`id` 一律是服务返回过的 ID，不接受文件名或路径。 |
| `status` | 见 §2。**必填。** |
| `missing` | `status != available` 时给出缺失字段名列表；`available` 时必须为空数组。 |
| `data` | tool 专属结构，见 §4。 |
| `evidence` | evidence 引用数组，见 §3。无来源时必须是显式的 unavailable 条目，不能省略。 |
| `limitations` | 影响可解释性的已知边界（例如"该快照无 corner"，"geometry coverage = partial"）。 |

**禁止行为**：用 `0`、`null`、空字符串或省略字段来代表"数据不存在"。数据不存在必须走 `status` + `missing` + `reason`。

---

## 2. 状态枚举（封闭集合）

| status | 含义 | 调用方应如何理解 |
|---|---|---|
| `available` | 请求的事实完整存在且已解析 | 可当事实使用 |
| `partial` | 部分存在；`missing` 列出缺的维度 | 只能用存在的部分；缺的部分不得推断 |
| `unavailable` | 该事实不存在于当前快照 | **必须拒绝作答**，不得用相邻数据代替 |
| `truncated` | 结果被分页截断 | 用 `next_offset` 继续；不得当成"这是全部" |
| `not_found` | 请求的 target ID 不在该快照 | 与 `unavailable` 区分：这是"问错了对象" |
| `incomparable` | 两个 scope 不能按同一口径比较 | 不得输出差值 |

每个"非 available"必须携带 `reason`（简短、机器可读的英文短语）与 `required_for`（缺少它会挡住哪个能力）。示例：

```json
{"status": "unavailable", "reason": "analysis corner is missing",
 "required_for": "cross_stage_timing_comparison", "missing": ["corner"]}
```

---

## 3. Evidence 表示（每条事实的来源引用）

```json
{
  "record": {"record_type": "timing_points", "record_id": "path:0:point:1"},
  "artifact_id": "art-d3c57c1f3e5f4a40b01c3e12a55499bd",
  "run_id": "run-aebb41cc1ca4424bb08e6a80c5a7b4e9",
  "attempt_id": "attempt-0df80694cb95472fbe3a8b5d4dca902e",
  "sha256": "51400c0548106c97605d8ea8c182c89e36af4f5652833dcf35d1ffd81d737e4b",
  "logical_path": "query-data/timing_report.json",
  "source_type": "json",
  "locator": {"kind": "json_pointer", "value": "/checks/0/points/1"},
  "parser": {"id": "opensta-json", "version": "0.1.0"},
  "resolved": true
}
```

规则：

1. **`resolved: false` 是合法且有意义的返回值。** 当来源无法绑定到已登记的 artifact 时：
   ```json
   {"resolved": false, "status": "unavailable",
    "reason": "source artifact is not registered in this snapshot",
    "artifact_kind": "raw_timing_report", "logical_path": "query-data/timing_report.json"}
   ```
2. **禁止 placeholder 充当 identity。** `"timing-report"`、`"orfs-metadata"` 这类占位字符串不得出现在 `artifact_id`。
3. `locator.kind` ∈ `line` | `json_pointer` | `path_index` | `field` | `none`。
4. 每个含数值的 fact 至少有一条 evidence；没有证据的事实返回 `status: partial` 且 `limitations` 说明。
5. 任何返回都能用 `artifact_id` + `run_id` 去 Execution Foundation 取到原始字节并校验 `sha256`。

---

## 4. Tools（v0 共 12 个）

`scope`/`status`/`missing`/`evidence` 字段全部适用，下表只列各自特有的入参与 `data`。

### 4.1 `list_designs()`

`data.designs[]`: `{design_id, revisions[], run_count, latest_run_at, snapshot_count}`

### 4.2 `list_runs(design_id?, stage?, status?, limit, offset)`

`data.runs[]`: `{run_id, design_id, status, plugin_id, created_at, started_at, ended_at, snapshot_ids[]}`

### 4.3 `get_run_summary(run_id)`

`data`: `{run_id, design_id, status, snapshots[]}`；每个 snapshot 给 `{snapshot_id, stage, created_at, counts:{entities,relations,timing_paths,timing_points,physical_context,observations}, coverage}`

### 4.4 `get_stage_summary(snapshot_id)`

`data`: `{snapshot_id, design_id, revision_id, run_id, stage, created_at, counts, coverage, source_artifacts[]}`
`coverage` 是**每类数据的解析状态**：`parsed | partial | unsupported | absent`，逐类给出（instances/pins/nets/location/geometry/routing/timing/metrics/parasitics/congestion/drc）。

### 4.5 `list_artifacts(run_id, kind?)`

`data.artifacts[]`: `{artifact_id, logical_path, kind, size_bytes, sha256, category, stage}`

### 4.6 `get_metrics(run_id?, snapshot_id?, stage?, name?, limit, offset)`

**Canonical metrics（v0 封闭集合）**：`WNS`、`TNS`、`AREA`、`POWER_TOTAL`、`RUNTIME`、`INSTANCE_COUNT`、`SETUP_VIOLATIONS`。

每条 canonical metric：

```json
{
  "name": "WNS",
  "value": -0.04544,
  "unit": "ns",
  "stage": "finish",
  "analysis": "setup",
  "corner": "default",
  "canonical": true,
  "authoritative_source": "orfs_metadata",
  "raw_key": "finish__timing__setup__ws",
  "artifact_id": "art-…",
  "status": "available"
}
```

规则：

1. **每个 canonical metric 必须声明 `authoritative_source`。** 同名数值来自不同来源时，非权威来源只作为普通 observation 列出，不得覆盖权威值。
2. 其他 ORFS/report 字段**不进入 canonical 集合**，只在 `data.raw_metrics[]` 里以**原始 key** 出现，并带 `"canonical": false`。它们不参与 `get_metrics(name=...)` 的按名查询。
3. `unit` 缺失或 `corner` 缺失时，该 metric 返回 `status: unavailable`（不得默认 `default` corner 或隐含单位）。
4. `AREA` 单位为 `um^2`，`POWER_TOTAL` 为 `uW`，`RUNTIME` 为 `s`（以 ORFS 原始 JSON 为准；不一致时以原始为准并在 `limitations` 记录）。

### 4.7 `get_timing_paths(snapshot_id, check?, limit, offset)`

`data.timing_paths[]`（摘要，不含 points）：`{path_id, startpoint, endpoint, slack, delay, unit, analysis, check, corner, group, point_count, path_identity:{basis, native_path_id?}}`

### 4.8 `get_timing_path(snapshot_id, path_id, include?: "summary"|"points"|"context")`

`data`: `{timing_path, timing_points[], analysis_context, availability}`

- `timing_points[]` 顺序即 `ordinal`；每点：`{point_id, ordinal, pin_name, instance_name, net_name, cell_name, arrival, required, slew, load, capacitance, clock, pin_id, instance_id, net_id, mapping_status, mapping_basis, evidence[]}`
- `mapping_status` ∈ `mapped | unmapped`。`unmapped` 表示 STA→OpenDB 原生桥没有给出对应对象，**不得用名字猜**。
- `analysis_context`: `{design, revision, run, snapshot, stage, analysis, check, corner, unit, status, missing[]}`，缺任一关键字段则 `status: unavailable`。
- `include=context` 时额外附 `objects[]`（沿 ID 展开的实体）与 `physical_context[]`。

### 4.9 `get_instance(snapshot_id, name)`

`data`: `{instance, physical_context, relations[], evidence[]}`
- `name` 为索引中的精确名（或 hierarchical name）；命中 0 条 → `not_found`，命中 >1 条 → `partial` 并全部列出（不静默取第一条）。
- `instance.attributes`: `{native_id, master, orient, is_macro, kind}`；`is_macro` 未知时返回 `status: partial`。

### 4.10 `get_net_context(snapshot_id, name_or_id)`

`data`: `{net, connected_entities[], relations[], physical_context[], evidence[]}`

### 4.11 `get_physical_context(snapshot_id, object_id)`

`data`: `{object_id, kind, x, y, bbox, geometry[], routing[], coverage}`
- `geometry[].geometry_type` ∈ `rect | polygon | wire_segment | via`；via 保留 `bottom_layer`/`top_layer`/`cut`，不得退化成矩形。
- `routing[]` 只含该 net 的 segment/via；`coverage` 表明 geometry 是否 `partial`。

### 4.12 `get_evidence(snapshot_id, record_type?, record_id?, artifact_id?, limit, offset)`

`data.evidence[]`: §3 的引用对象；可按 record 或 artifact 过滤。

---

## 5. 分页与规模

所有列表类 tool 必须返回：

```json
{"count": 100000, "returned": 100, "limit": 100, "offset": 0,
 "truncated": true, "next_offset": 100}
```

规则：

1. `count` = **匹配总数**（不是本页条数）；`returned` = 本页条数。
2. `truncated: true` ⇔ `offset + returned < count`；此时 `status` 为 `truncated`（若本页确实截断）。
3. 对象级查询（`get_instance` / `get_net_context` / `get_physical_context`）**不接受全表扫描语义**：必须按索引精确命中该对象及其直接关系，与库里总记录数无关。
4. 服务端默认 `limit=100`，上限 `10000`。任何超过上限的请求返回 400，不静默截断。

---

## 6. 身份（identity）

每个对象同时暴露三层：

```json
{
  "object_id": "inst:587",
  "identity": {
    "native_id": "587",
    "canonical": {"design_id":"gcd","revision_id":"…","kind":"instance","hierarchical_name":"clkbuf_0_clk"},
    "canonical_basis": "scoped_name",
    "matching_status": "candidate",
    "structural_fingerprint": null
  }
}
```

- `canonical_basis` ∈ `native_exact` | `structural_verified` | `scoped_name` | `unresolved`。
- `matching_status` ∈ `deterministic` | `candidate` | `ambiguous`。
- **同一快照内**的 `object_id` 是权威；**跨快照**匹配只有在 `canonical_basis != scoped_name` 时才可当作同一对象。`scoped_name` 只能作为候选，必须在响应中保留该词。
- 跨 stage/run 比较在 `analysis/check/corner/unit` 不一致时返回 `incomparable` + `reasons[]`，**不得输出差值**。

---

## 7. 版本与实现状态

| 部分 | 本文件状态 | 当前实现 |
|---|---|---|
| 通用信封 / 状态枚举 | 冻结 | 部分（需补 `contract_version`、`missing`、`limitations`） |
| Evidence 表示 | 冻结 | 已实现（`resolved` 语义已在 semantic-correctness 中） |
| 分页信封 | 冻结 | 需补 `count/returned/truncated/next_offset` |
| Tools 1–12 | 冻结 | 1–5、7–8、10–12 已存在；6 需 canonical 化；9 需精确索引查询 |
| Canonical metrics 封闭集合 | 冻结 | 阶段 B 实现 |
| 对象级查询不做全表扫描 | 冻结 | 阶段 A 实现（SQL 谓词 + 表达式索引） |

**外部调用方可以现在就按本文件写代码**：字段名、状态语义、evidence 结构、分页结构都不会再变；阶段 B/C 只是把这些字段真正填满，并补上 Python client 与 JSON tool schema。
