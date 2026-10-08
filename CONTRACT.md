# Data Interface contract 0.2

Breaking changes from 0.1: all Data Foundation SDK methods return the service envelope, including list_designs and get_instance. get_instance returns data.entities/data.target rather than a client-built flattened instance. get_net_context defaults to exact name; use by="object_id" for an ID. list_runs no longer accepts stage: execution status belongs to Execution Foundation, stage snapshots to Data Foundation. No client-side grouping, name matching, metric ownership lookup or per-run stage requests.

New tools: resolve_scope and get_object_context (15 published tools total). resolve_scope accepts snapshot/design/revision/run/stage and origin=flow|query|all. Zero matches is not_found; multiple matches is partial with candidates and missing=[unique_snapshot]. Selection is never implicit latest. Exact object resolution is at /snapshots/{id}/resolve-object. Metrics at /snapshots/{id}/metrics enforce the owning run in one request.

Data Foundation responds with contract_version=0.2, tool, scope, status, missing, data, evidence, limitations. Missing/ambiguous targets are not substituted. HTTP errors raise EdaAiError with status; business partial/not_found with HTTP 200 pass through unchanged. Consumers must inspect status before using data. SDK requires the 0.2 Data Foundation; services need not import the SDK.

Execution methods list_runs/list_artifacts retain their execution catalog shape; raw artifacts are bytes. HTTP encoding and these documented transport projections belong here. Execution and data are distinct catalogs: a queued execution may have no imported snapshot.

The detailed fact vocabulary below remains applicable; the 0.2 changes above supersede old client-specific projections.

# EDA-AI Data Interface — CONTRACT v0.2

状态：**0.2 独立项目契约** · 更新日期 2026-10-08。历史 EDA 事实词汇保留，当前服务行为以下述边界为准。
本文件是外部调用方唯一需要读的接口规范。它规定"模型看到什么"，不规定我们内部怎么实现。

> 变更规则：新增字段/新增 tool 属于向后兼容，允许；改变已有字段含义、删除字段、改变状态枚举属于破坏性变更，必须提升 `contract_version`。

---

## 0. 服务边界

Data Foundation 只回答 **结构化 EDA 事实**。它不诊断、不建议、不解释"为什么"。
所有数据来自原始 artifact。**每一类记录与 evidence 的关系必须按实情读，不能一概而论**：

| 记录类型 | 带 evidence？ | 说明 |
|---|---|---|
| `timing_paths` / `timing_points` | ✅ | 指回**它自己来自的那份** OpenSTA 报告（文件内 path 序号 + point 序号）；point 另有一条指向 `dbnetwork_map.json`（它的 `pin_id`/`net_id` 来自那里） |
| `physical_context`（markers） | ✅ | 指回 `inputs/design.odb` |
| `observations` / canonical metrics | ✅ | 指回 `inputs/stage.json` 或 ORFS 报告 |
| `stages` | ✅ | 指回该 stage 的来源文件 |
| **`entities` / `relations`** | ✅ | **紧凑引用**：记录只带 `source_ref` + `locator`，快照级的 `source_catalog.json` 持有 artifact 描述；入库时展开成完整 evidence（见 §3.1），**不逐行复制元数据** |

**§3.1 紧凑来源引用（entities / relations 用的就是这个）**

一条记录只需说"我从哪来"，不需要把 artifact 的五个字段抄一遍（百万行会重复百万次）。所以：

```json
{"object_id": "inst:1", "kind": "instance", "name": "_479_",
 "source_ref": "opendb:route", "locator": {"native_id": "1"}}
```

```json
// query-data/source_catalog.json —— 每个快照一份
{"schema_version": 1,
 "refs": {"opendb:route": {"artifact_kind": "raw_design_database",
                           "logical_path": "inputs/design.odb",
                           "source_type": "opendb",
                           "detail": {"tool": "opendb", "stage": "route"}}}}
```

规则：
1. `source_ref` **只在同一快照内唯一**（目录就在快照里），所以引用可以很短；
2. `locator` **只在能精确定位时出现**（如 ODB 的 `native_id`、pin 的 `pin_id`），**不猜**；
3. **入库时**由快照目录展开成完整 evidence（`artifact_id`/`sha256`/`run_id`/解析方式一并给出），
   所以调用方看到的仍是一致的 evidence 形状；`source_ref` 本身保留在记录上，便于看出"同一来源"；
4. 已经有完整 evidence 的记录（如 `markers.jsonl`）不会被覆盖。

**两个已声明的取回限制**（不是"能取回"的反例，而是**取回通道**的限制）：

1. **超过 4 MiB 的 artifact 无法通过 API 下载**：Execution Foundation 的下载接口上限为 4 MiB，
   ibex 的 `inputs/design.odb`（26.8 MB）等超过上限 → 下载返回 HTTP 413。原始字节仍在 run 工作区里，
   但**不能通过这个 API 取回**；相应地，那些 evidence 指针**在 API 层面无法兑现**。
2. **模型/调用方不应把"指针存在"当成"事实已验证"**：验证要真的按指针取字节、核对 sha256、再找事实
   （本仓库的 `evidence/B/check_evidence_recoverable.py` 就是这么做的，且**无法验证时返回"无法验证"而不是通过**）。

调用方式（同一套语义，三种壳）：HTTP JSON（当前可用）、Python client（阶段 C）、JSON tool schema（阶段 C，供 function calling）。

- 当前地址：`http://127.0.0.1:8860`
- `contract_version`: `"0.2"`
- 所有响应 `Content-Type: application/json`，UTF-8。
- **永远不返回宿主路径。** 文件只以 artifact identity + logical path 出现。

---

## 1. 通用响应信封

除 `/health` 外，每个 tool 返回：

```json
{
  "contract_version": "0.2",
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
  "artifact_kind": "raw_flow_metadata",
  "category": "raw_flow_metadata",
  "detail": {"field": "metrics.finish__timing__setup__ws"},
  "resolution": "exact_path",
  "stage": "finish",
  "size_bytes": 3133
}
```

**字段名以本块为准**（服务实际发出的就是这些）：`resolution` 表示引用绑定情况
（`exact_path` 等），`detail` 是来源内的定位信息，`category`/`source_type` 说明来源类型。
`parser`（解析器 id/版本）目前**不在** evidence ref 里——M7/Q7 需要它，已记为 Phase 1 缺口。

规则：

1. **`resolution: "unavailable"` 是合法且有意义的返回值。** 当来源无法绑定到已登记的 artifact 时：
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

## 4. Tools（0.2 共 15 个）

`scope`/`status`/`missing`/`evidence` 字段全部适用，下表只列各自特有的入参与 `data`。

### 4.1 `list_designs()`

`data.designs[]`: `{design_id, revisions[], run_count, latest_run_at, snapshot_count}`

### 4.2 `list_runs(design_id?, status?, limit, offset)`

返回 Execution Foundation 的 run 数组：生命周期、设计、插件及时间。SDK 单次 HTTP 请求传递过滤与分页；没有 snapshot_ids 合并，也没有 stage 过滤。数据阶段通过 Data Foundation 的 run summary 查询。

### 4.3 `get_run_summary(run_id)`

`data`: `{run_id, snapshots[]}`；每个元素是 `{snapshot, coverage, record_counts, run_summary}`——
`snapshot` 是快照元数据（含 `snapshot_id`/`design_id`/`stage`/`created_at`），
`record_counts` 是各类记录数（`entities`/`relations`/`timing_paths`/`timing_points`/`physical_context`/`observations`），
`coverage` 是每类解析状态，`run_summary` 是该快照所属 run 的摘要。（字段名是 `record_counts`，不是 `counts`；
run 级的 `design_id`/`status` 目前只在 `snapshot`/`run_summary` 里，见 NEXT 的 M1 条目。）

### 4.4 `get_stage_summary(snapshot_id)`

`data`: `{snapshot, coverage, record_counts, run_summary}`——`snapshot` 内含
`snapshot_id`/`design_id`/`revision_id`/`run_id`/`stage`/`created_at`，`record_counts` 见 §4.3，
`run_summary` 是该快照所属 run 的摘要。
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

`data` 另有 `canonical_names`（封闭集合本身）与 `canonical_names_available`（**本次响应 scope 内**声明为
`available` 的名字；带 `stage`/`snapshot_id`/`name` 过滤时随之收窄——不要再把它读成"整个 run 的可用名"）、
`units_declared`、`filters`。

规则：

1. **每个 canonical metric 必须声明 `authoritative_source`。** 同名数值来自不同来源时，非权威来源只作为普通 observation 列出，不得覆盖权威值。
2. 其他 ORFS/report 字段**不进入 canonical 集合**，只在 `data.raw_metrics[]` 里以**原始 key** 出现，并带 `"canonical": false`。它们不参与 `get_metrics(name=...)` 的按名查询。
3. `unit` 缺失 → `status: unavailable`（不得隐含单位）。`corner` 未由来源声明时**不得静默省略**：保留数值，但该行必须带 `corner_status`——来源声明了就是 `"declared"` 并给出 `corner`，没声明就是 `"not_declared"` 且 `corner` 为 `null`（同时 `reason` 说明）。理由：ORFS 的 run 级报告本就不声明 corner，若按 `unavailable` 处理会让**整个 canonical 指标面不可用**，那是拿诚实换可用性；显式声明可以让两者同时成立。
4. `AREA` 单位为 `um^2`，`POWER_TOTAL` 为 `uW`，`RUNTIME` 为 `s`（以 ORFS 原始 JSON 为准；不一致时以原始为准并在 `limitations` 记录）。

### 4.7 `get_timing_paths(snapshot_id, check?, sort?, order?, limit, offset)`

`data.timing_paths[]`（摘要，不含 points）：`{path_id, startpoint, endpoint, slack, required_time, margin, unit, analysis, check, corner, group, point_count, path_identity:{basis, native_path_id?}}`

- **没有 `delay` 字段**：OpenSTA 的 `report_checks -format json` 在 check 级**不声明** delay（只有 `data_arrival_time`/`required_time`/`slack`/`margin`），
  所以早期文档里的 `delay` 是**幽灵字段**，实现只能填 `null`——这违反"不得用 null 冒充缺失"，已从契约移除。
  路径级的 `data_arrival_time` 目前**没有**被索引（见 NEXT），时间事实在 point 级完整可查（`arrival`/`required`/`slew`/`load`）。

### 4.8 `get_timing_path(snapshot_id, path_id, include?: "summary"|"points"|"context")`

`data`: `{timing_path, timing_points[], analysis_context, availability}`

- `timing_points[]` 顺序即 `ordinal`；每点：`{point_id, ordinal, pin_name, instance_name, net_name, cell_name, arrival, required, slew, load, capacitance, clock, pin_id, instance_id, net_id, mapping_status, mapping_basis, evidence[]}`
- `mapping_status` ∈ `mapped | unmapped`。`unmapped` 表示 STA→OpenDB 原生桥没有给出对应对象，**不得用名字猜**。
- `analysis_context`: `{design, revision, run, snapshot, stage, analysis, check, corner, unit, status, missing[]}`，缺任一关键字段则 `status: unavailable`。
- `include=context` 时额外附 `objects[]`（沿 ID 展开的实体）与 `physical_context[]`。
- `detail`（`summary` 默认 / `full`）：summary 只保留**目标对象**的 geometry/routing 与 pack 级 evidence，
  邻居保留身份、计数与 bbox；`timing_context.points[*].evidence` 在 summary 下省略（pack 级 evidence 与
  `/timing-paths/{path}/points` 仍完整）。full 返回未投影的完整 pack。
- `relation_limit`（默认 200，`0` = 不限）：context pack 合并的关系上限，**两种 detail 下都生效**。
  触顶时返回 `relations_truncated: true`、`relations_total`，并往 `limitations[]` 追加一条 truncated 记录 ——
  一条 12 点的 ibex 路径上下文会合并 401 条关系，调用方必须能设上限、也必须被告知被截断。

### 4.9 `get_instance(snapshot_id, name)`

`data`: `{scope, target, entities[], physical_context[], relations[], ...}`；目标实体在 entities 中由 target.id 指定。SDK 透明返回信封。
- `name` 为索引中的精确名（或 hierarchical name）；命中 0 条 → `not_found`，命中 >1 条 → `partial` 并全部列出（不静默取第一条）。
- 实体的 master/cell_type、属性和物理覆盖依赖来源，字段缺失不代表有完整物理证据。

### 4.10 `get_net_context(snapshot_id, net, by="name"|"object_id")`

`data`: `{target, entities[], relations[], physical_context[], observations, timing_context?}`
（`entities` 是**该 net 及其关系端点**的实体列表，不是单独的 `connected_entities` 字段；`target` 同时镜像在信封层。
 evidence 在信封层，见 §7。）

### 4.11 `get_physical_context(snapshot_id, object_id)`

`data`: `{physical_context: {object_id, snapshot_id, instance_name, x, y, bbox, layer, geometry[], routing[], identity, evidence[]}}`
（记录**嵌在 `physical_context` 下**，不是直接放在 `data` 上——这是服务的实际形状，按真实响应更正。
 注意：**没有** `kind` / `coverage` 字段；`x`/`y` 由 adapter 的 marker 提供，ingest 曾经把它丢掉，
 已修（`ingest.py`），但**已导入的快照要重新导入才会带上**——见 NEXT 的迁移步骤。`bbox` 为 `null`
 表示该对象没有 bbox（例如 pin 只有 master 坐标系的 geometry），不是 0。）
- `geometry[].geometry_type` ∈ `rect | polygon | wire_segment | via`；via 保留 `bottom_layer`/`top_layer`/`cut`，不得退化成矩形。
- `routing[]` 只含该 net 的 segment/via；`coverage` 表明 geometry 是否 `partial`。
- `detail`（`summary` 默认 / `full`）语义同上；`get_instance` 与 `get_net_context` 都接受它。

### 4.12 `get_evidence(snapshot_id, record_type?, record_id?, artifact_id?, limit, offset)`

- `record_type` 用**复数表名**（`entities` / `relations` / `timing_paths` / `timing_points` / `physical_context` / `observations` / `stages`），
  不是单数对象名——Phase 6 的模型实测时要靠猜才发现这一点，所以写进契约。
- **列表在信封层**：`evidence[]` 是信封字段（见 §7），`data` 里是分页计数；这个 tool 的 `count` 按 §5 的唯一例外返回 `null` + `count_status: "unavailable"`。

信封 `evidence[]`（本 tool 的 evidence 引用在信封层，见 §7）: §3 的引用对象；可按 record 或 artifact 过滤。

- **整快照索引也支持 `record_type` 过滤**（只给 `record_type`、不给 `record_id` 时）：响应会带 `filters.record_type`，
  并且**只扫这一类**，不再从头扫整个索引。若给了未知的 `record_type`，返回空页 + `missing: ["record_type"]` +
  `note` 说明，**绝不静默当成"不过滤"**。
  （此前客户端在缺 `record_id` 时会**丢掉** `record_type`，调用方以为过滤了其实没有——已修。）

### 4.13 `read_evidence(snapshot_id, record_type, record_id)`

给一条记录的 evidence，**返回它指的那一小片原始内容**，而不是整份 artifact。

**为什么需要它**：Execution Foundation 的下载接口上限 4 MiB（ibex 的 `dbnetwork_map.json` 10.29 MB、
`design.odb` 25.54 MB 都取不回），而"为了一个 pin 下载 25 MB"本身也不是对的答案。
接口在导入时**保留 bundle 里本来就有**的 JSON 成员（`timing_report.json`、`timing_report_hold.json`、
`dbnetwork_map.json`），于是切片**不需要任何下载**，4 MiB 上限对它不适用。

```json
{"status": "available",
 "data": {"snapshot_id": "…", "record_type": "timing_points", "record_id": "path:12:point:1",
          "available": 2, "returned": 2,
          "fragments": [
            {"artifact_id": "art-…", "logical_path": "query-data/timing_report_hold.json",
             "sha256": "…", "detail": {"path_index": 0, "point": 1}, "status": "available",
             "fragment_path": "/checks/0/points/1", "fragment": {…}},
            {"artifact_id": "art-…", "logical_path": "query-data/dbnetwork_map.json",
             "sha256": "…", "detail": {"pin_name": "input155/A"}, "status": "available",
             "fragment_path": "/input155/A", "fragment": {…}}]}}
```

规则：

1. **切片规则按 evidence 自己的定位器**，不按记录类型猜：`detail.path_index`（±`detail.point`）切时序报告；
   `detail.pin_name` 切映射表（该表以 **pin 名**为键）；`locator` 里的 `native_id`/`pin_id` 用于指认对象。
2. **取不到就是取不到**：该 artifact 不是 JSON 片段来源（如二进制 `design.odb`）或切不出来时，
   该条 `status: "unavailable"` 并给出**原因**——**绝不用别的东西顶替**。
3. **自带来源身份**：每条片段都带 `artifact_id` / `logical_path` / `sha256`（以及 `source_sha256`），
   调用方可以自己核对；`fragment_path` 是可读的定位串（JSON 指针风格）。
4. `available`/`returned` 分开报：一条记录可能指向两个来源（时序点就是这样），可能一个可取、一个取不到。

### 4.14 排序与取前 K（`sort` / `order` / `limit`）

**为什么有它**：V2 实验量出来的事实 —— 问"最差 5 条 setup 路径"，**枚举**的模型答对但读了 52.6 MB / 2529 次调用；
被要求"最小上下文"的模型省了 65%，却**答错了那 5 条**，因为**当时接口没有办法排序**。
所以"排名"必须是**接口能力**，而不是对模型的道德要求。

```
GET /snapshots/{id}/timing-paths?check=setup&sort=slack&order=worst&limit=5
GET /snapshots/{id}/timing-points?sort=slew&order=worst&limit=1
```

规则：

1. **`order=worst` 的方向由指标决定，不是固定的**：`slack` 是预算，最差 = **最小（最负）** → 升序；
   `slew` / `load` / `arrival` 是幅值，最差 = **最大** → 降序。（第一版把 worst 一律当升序，
   结果"最差 slew"返回了 slews = 0 的时钟根 —— 这就是为什么方向必须写死并被检查。）
2. **响应必须声明排序**：`sorted_by` / `order` / `ordered`（`ascending|descending`）/ `worst_means`。
   调用方可以**信任前 K**，不必自己再排一遍。
3. **不认识的 `sort` 字段一律拒绝**（`ValueError`），不静默忽略 —— 否则"排序"变成本地假象。
4. 排序键缺失的行**永远排在最后**（两个方向都如此）：没有 slack 的路径不是"最差路径"。
5. 与 §5 一致：`limit` 小于总数时**必须** `truncated: true` 并给出 `next_offset`。

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
5. **例外：`get_evidence` 的整快照索引。** 该索引可能极大（ibex 约 19 万条；一次响应曾达 95 MB / 10.5 s）。
   服务端对它流式扫描并取满一页即停，因此 `count` 为 `null` 且
   `count_status: "unavailable"`、`count_reason` 说明原因，`truncated` 与 `next_offset` 照常给出。
   指定 `record_type` + `record_id` 的定向查询不受影响，仍是完整的。

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
| 通用信封 / 状态枚举 | 冻结 | **已实现**。除 `/health` 外每个路由都返回 `contract_version`/`tool`/`scope`/`status`/`missing`/`data`/`evidence`/`limitations`；状态由 payload 推导（`not_found` 目标不存在、`truncated` 分页或被 `relation_limit` 截断、`partial` payload 自报不可用、`unavailable` 无法作答）。注意两点：`scope`/`target` 对 context pack 是**镜像**（pack 本身仍保留），`evidence`/`limitations` 是**上提**到信封（各 tool 的 `data` 里不再重复；§4.12 的列表即信封的 `evidence`）。 |
| Evidence 表示 | 冻结 | 已实现，但**字段名与 §3 不完全一致**：实际发出 `artifact_id / artifact_kind / attempt_id / category / detail / logical_path / resolution / run_id / sha256 / size_bytes / source_type / stage`；§3 写的 `locator`、`parser`、`resolved` 未发出（对应物分别是 `detail`、`category`/`source_type`、`resolution`）。 |
| 分页信封 | 冻结 | **已实现**：`/timing-paths`、`/metrics`、`/evidence`、`/observations` 均返回 `count/returned/limit/offset/truncated/next_offset`；`count>10000` 拒绝。 |
| 15 个公开工具 | 0.2 | DF 拥有 `/designs`、`/scope`、对象解析和指标业务。`list_runs/list_artifacts` 查询 EF，后者的 kind 过滤也由 EF 执行；SDK 不做分组/匹配/归属判断。 |
| 未知 target 的表示 | 冻结 | **已实现**：目标不存在时返回 HTTP 404 且 body 是信封，`status: "not_found"`（`error_envelope`），不再是把 KeyError 的 repr 塞进 `error` 字段。Q8-02/Q8-05 两道题在考它。 |
| Canonical metrics 封闭集合 | 冻结 | 阶段 B 实现 |
| 对象级查询不做全表扫描 | 冻结 | 阶段 A 实现（SQL 谓词 + 表达式索引） |

消费者应显式依赖 0.2 契约，检查信封状态和具体证据覆盖。后续破坏性变更提升版本；新增能力先通过契约与实际 HTTP 验证。

## 8. 0.2 新增入口与证据身份

`resolve_scope(snapshot_id?, design_id?, revision_id?, run_id?, stage?, origin="flow"|"query"|"all")` 调用 `GET /scope`，唯一命中返回 data.snapshot；零或多命中分别为 not_found/partial，后者返回候选，不隐式取最新。

`get_object_context(snapshot_id, kind, name? , object_id?, detail, relation_limit)` 调用 `GET /snapshots/{id}/resolve-object`。name 与 object_id 必须且只能提供一个；kind 为 instance/net/pin。

已注册源的 artifact_id/run_id/sha256 指向实际文件。resolution=bundle_member 时 sha256 属于容器 ZIP，nested_path 指包内成员；来源声明成员哈希时独立保留 member_sha256。不得把 ZIP 哈希称为报告哈希。已注册的精确报告路径优先匹配；声明与注册哈希冲突时 resolution=hash_mismatch，不绑定权威 artifact。

`get_timing_paths(..., detail="summary"|"full")` 保持 limit/offset；summary 省略行级来源，full 保留每条路径 evidence。需要证据归属的 Agent 应显式请求有界 full，不把 envelope 的去重来源随意分配给每条路径。

### Rich read extensions (SDK 0.2.1, wire contract 0.2)

| SDK method | HTTP route | Contract |
|---|---|---|
| `query_objects` | `GET /snapshots/{id}/objects` | Filtered whole-domain count; offset/limit never redefine scope; explicit region units. |
| `get_relationships` | `GET /snapshots/{id}/objects/{object}/relationships` | Explicit relations and endpoint identities; count/paging and missing endpoints. |
| `get_net_engineering` | `GET /snapshots/{id}/nets/{net}/engineering` | Native load/driver counts with connectivity availability; lists are paged. |
| `get_path_engineering` | `GET /snapshots/{id}/timing-paths/{path}/engineering` | Cell/net path increments, calculation domain and sources. |
| `read_evidence` | `GET /snapshots/{id}/records/{type}/{record}/fragments` | Raw fragments with registered artifact hash and logical locator; missing bytes are explicit. |

Reads do not create EDA tasks. Analysis submission/import uses explicit operations.
The SDK passes status, units, coverage, evidence and pagination unchanged; the service owns all calculation.

`read_query(path, parameters)` supports documented DF read extensions without adding
business logic to the SDK. The path must be local and separate from query parameters.
`read_batch(requests, bindings)` sends the public read-only `POST /query` batch contract.
Analysis submission is a separate operation, never an option that silently executes during a read.
