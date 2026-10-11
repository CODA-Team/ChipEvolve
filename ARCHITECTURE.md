# 架构与源码边界

本页整理现有实现和已确认职责，不以预设架构强迫专业项目重构。源码证据、历史审计和接点依据见 [admin/INTEGRATION_MAP.md](admin/INTEGRATION_MAP.md)。更新：2026-10-11；本机目标关系与分阶段验收见 admin/LOCAL_EXECUTION_PLAN_20261011.md。

## 模块清单

| 模块 | 职责与实际边界 |
|---|---|
| Codex | 用户入口、全局目标、决策、判断、工具调用与下一步规划。 |
| Flow Agent | A2 原生候选生成、阶段屏障、DRP 替换/继承、固定 CP0 与功耗约束；平台接入不改优化算法。 |
| Execution Foundation | 幂等任务、资源调度、进程生命周期、日志和注册产物。 |
| Toolkits | 现有 OpenROAD/A2 阶段适配、真实评价和数据导出。 |
| Data Foundation | 统一事实快照、指标/对象/关系、来源与持久导入回执。 |
| Data Interface | 对外工具语义与已安装 SDK；不新增后台服务或数据库。 |
| Query Agent | Codex 的 EDA 垂直形态：统一事实、比较、领域技能、调查状态、证据与补 STA。当前 host 路径复用 Codex 推理；真实 Flow/Code 接收与可靠诊断效果仍待验收。 |
| Code Agent | DPLEvolve 原生复现工程验收通过，真实新源码构建/评价及固定源码重放可运行；统一平台接入尚未交付。GoalEvolve 原生复现为下一切片。 |

## 模块依赖

```mermaid
flowchart TD
    C[Codex] --> Q[Query Agent]
    Q --> DI[Data Interface SDK]
    DI --> DF[Data Foundation]
    C -. 完整业务接收器待实现 .-> F[Flow Agent]
    F --> EF[Execution Foundation 公共 HTTP / wheel]
    EF --> TK[Toolkits]
    TK --> OR[OpenROAD / Yosys]
    DF --> EF
    C -. 后续接入 .-> CODE[DPLEvolve / GoalEvolve]
```

## 核心数据流

```mermaid
flowchart LR
    Goal[用户目标] --> C[Codex 判断与调度]
    C --> Query[Query 查询与证据]
    Query --> Facts[DF 事实 / SDK]
    C -. P4 待完成 .-> Flow[原生 A2 优化]
    Flow --> Task[带候选身份的阶段任务]
    Task --> EF[EF 执行与注册产物]
    EF --> Eval[Toolkits 实际 CP0 测量]
    Eval --> Import[导出 / 指定产物导入]
    Import --> Facts
    Facts --> C
```

数据底座提供事实和来源；Query 提供解释与证据；Codex 负责业务判断。工具测量与开发验收脚本不是独立评测底座。

## 两个关键场景

```mermaid
sequenceDiagram
    participant F as 原生 Flow
    participant E as EF
    participant T as Toolkits/OpenROAD
    participant D as Data Foundation
    F->>E: 保存请求后提交单候选物理阶段
    E->>T: 运行真实阶段 / CP0 评价
    T-->>E: 产物、实际数值及评价条件
    E-->>F: run_id、artifact_id、hash
    F->>E: 引用实际评价 metadata 导出快照
    F->>D: 从指定注册产物导入
    D-->>F: 同一快照与持久回执
    Note over F,D: P3 自动回流与完整恢复工程验收通过；业务确认待老板
```

```mermaid
sequenceDiagram
    participant U as 操作者
    participant F as Flow Controller
    participant J as 本实验状态
    participant E as EF
    U->>F: 原命令加 --resume
    F->>J: 核对源代码 / 工具 / 选项 / 实验身份
    J-->>F: 最后提交阶段、原生小状态、产物引用
    F->>E: 原 run 查询或原幂等键重取
    E-->>F: 原任务与注册产物
    F->>J: 复用已完成模型响应及原调用账本
    F->>F: 继续未提交阶段
    Note over U,E: L1 四个真实中断窗口工程验收通过，业务确认待老板
```

## 对外接口及关键决策

- EF：已发布公共 client/contracts wheel 和 HTTP，提交、状态、取消、产物与上传输入；不访问其私有数据库。
- 本机物理产物交接：HTTP 传任务、状态和产物定位元数据；大文件通过公共 `KernelClient.materialize_artifact` 使用执行底座核准的本机路径复制并校验 hash，不受整包 HTTP 的 4 MiB 响应上限限制。远程才使用该接口已有的分块下载。2026-10-11 实际 17,579,571 字节布局包的本机取回/校验约 0.026 秒（已有文件缓存），证据见 `var/flow-agent/p3-platform-campaign-20261011-retry3/local-transfer-check/receipt.json`；此单次测量不是磁盘稳定吞吐基准。
- DF：`POST /snapshots/from-run` 指定注册产物导入，`GET /imports/{artifact_id}` 回执、快照/指标查询；POST 直接结果和 GET envelope 语义沿用现有契约。
- Data Interface：已发布 SDK 工具和来源读取。Query 通过 SDK 访问 DF；不直接读 sibling 源码。
- Flow：既有 `run.sh` 入口保留；新增 opt-in 平台运行和显式同 campaign 恢复。`-F` 是归档重开，不能冒充恢复。
- Query→Flow 的业务接收器仍未实现，不把 `contract_only` 标记改成完成。
- 运行状态放 `var`，模型 cache 不跨实验复用；保留未知调用成本和失败现场。
- 专业源码项目各自冻结工具链，不强行迁就 Flow 的工具版本。
- L2 的 DPLEvolve 保留原生 Teacher/Student 和 evaluator；确定性接点为官方共享 core configure/build、私有 variant configure/relink、带明确私有 binary 的原生 baseline 评价。当前独立原生执行及结果留证通过，尚未由 EF/DF 接管；统一接入分别在 L4、L6 实现。详细源码与接点证据见 `admin/L2_DPLEVOLVE_REPORT_20261011.md`。

## 已知缺口

P3 完整真实恢复、评价自动回流及四个中断窗口、L2 的 DPLEvolve 原生复现已通过工程验收，业务确认待老板；GoalEvolve 原生复现、两个 Code 项目的统一接入、统一身份与数据入口、三项目协同及本机收益测量未完成。DPLEvolve 本轮新源码候选可运行但未晋升，不能记为已验证优化质量。现有 Query 的查证/比较不能自动被包装为已证明的因果结论。教学、新用户安装和论文交付本轮暂缓。

源码优化交接包含候选源码、构建工具身份与实际评价，最终设计 PPA 通过兼容工具下的实际物理流程确认。两个 Code 项目分别保留原始工具锚点进行复现，组合工具版本由构建/运行兼容性验证决定。
