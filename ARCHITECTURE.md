# 架构与源码边界

本页整理现有实现和已确认职责，不以预设架构强迫专业项目重构。源码证据、历史审计和接点依据见 [admin/INTEGRATION_MAP.md](admin/INTEGRATION_MAP.md)。更新：2026-10-13；本机目标关系与分阶段验收见 admin/LOCAL_EXECUTION_PLAN_20261011.md；共同工具链审计与迁移路线见 admin/COMMON_TOOLCHAIN_AUDIT_20261012.md 和 admin/COMMON_TOOLCHAIN_PLAN_20261012.md。

## 模块清单

U3 的 DPLEvolve 共同工具链及确定性 EF 入口工程验收通过，业务确认待老板。真实基线、源码演化及固定来源独立编译重放通过，专业决策/原生筛选与指标含义保留。数据接入仍按 L5/L6 验收；接口与证据见 `admin/U3_DPLEVOLVE_COMMON_TOOLCHAIN_PLAN_20261013.md` / `admin/U3_DPLEVOLVE_COMMON_TOOLCHAIN_REPORT_20261013.md`。

U4 GoalEvolve 本轮已暂停，完整验收待补齐：原生 Teacher、四 Student、AST、EPD 与筛选保持，由原集中 runner 将构建、OpenROAD、parser/checker 和版本查询交给 EF。共同专业源码完整构建、新 AST、实际 AES 基线已通过；两轮四 Student 真实编辑与构建已运行，第二轮 Student 4 新源码完成合法物理实测但未达原目标；Student 4 空目录独立重放已通过；原生最新轮次已按原截止时间停止，正常收尾及最终验收仍待完成。两个 Code 的 DF/DI/Query 数据入口不在本轮接入范围。实际签名、数据流和证据见 `admin/U4_GOALEVOLVE_COMMON_TOOLCHAIN_REPORT_20261013.md`。

仓库层面由 ChipEvolve 根仓库以 Git 子模块固定八个独立项目；六个自有模块与两个 Code 的平台适配分支保存在同一远程的 `modules/<目录名>`，DPLEvolve / GoalEvolve 官方上游来源在 manifest 保留。模块源码、环境和 wheel/HTTP 边界保持独立。`discarded/` 为旧仓库原始 tree 的历史归档，不参与当前模块依赖。源码来源见 `SOURCE_MANIFEST.json`，原始发布记录见 admin/REPOSITORY_PUBLICATION_20261012.md。

| 模块 | 职责与实际边界 |
|---|---|
| Codex | 用户入口、全局目标、决策、判断、工具调用与下一步规划。 |
| Flow Agent | A2 原生候选生成、阶段屏障、DRP 替换/继承、固定 CP0 与功耗约束；平台接入不改优化算法。 |
| Execution Foundation | 幂等任务、资源调度、进程生命周期、日志和注册产物。 |
| Toolkits | 现有 OpenROAD/A2 阶段适配、真实评价和数据导出。 |
| Data Foundation | 统一事实快照、指标/对象/关系、来源与持久导入回执。 |
| Data Interface | 对外工具语义与已安装 SDK；不新增后台服务或数据库。 |
| Query Agent | Codex 的 EDA 垂直形态：统一事实、比较、领域技能、调查状态、证据与补 STA。当前 host 路径复用 Codex 推理；真实 Flow/Code 接收与可靠诊断效果仍待验收。 |
| Code Agent | DPLEvolve 原生复现及 U3 共同环境/统一执行工程验收通过；GoalEvolve U4 已实际完成共同专业构建、新 AST、本机 Codex 和经 EF 的 AES 基线，首轮四候选无效，第二轮已测一个合法新源码候选但目标未达，Student 4 空目录独立重放已通过，原生轮次已按原截止时间停止，正常收尾和最终验收待完成。两个 Code 的统一数据入口待做。 |

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
    C --> DPL[DPLEvolve Teacher与Student]
    DPL --> EF
    C --> CODE[GoalEvolve Teacher与四Student]
    CODE --> EF
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
    C --> DPL[DPLEvolve 原生源码优化]
    DPL --> EF
    EF --> Native[原生指标和来源证据]
    Native --> DPL
    Native --> C
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
- U2 的 opt-in A2 profile 增加 `runtime`（固定本机 Apptainer/SIF）和 `toolchain`（SIF/OCI/source/binary 身份）；实际 A2 Makefile/scripts 与 PDK/设计仍分别冻结。EF 的 A2 adapter 在镜像内执行原生阶段，冻结 source 只读、独立 workspace 可写、磁盘 scratch 绑定 `/tmp`；controller 留在原生 Python 环境调用 Codex。宿主身份入口只能查工具身份，不能发动 EDA。`platform.json.resources` 把单任务内存/进程额度显式传到原 TaskSpec，原公共 HTTP/schema 不变；恢复核对实际镜像/工具身份与配置。AES 完整两轮、四类恢复及 12 个 SDK 评价快照工程验收通过，业务确认待老板；具体契约与结果见 `admin/U2_FLOW_COMMON_TOOLCHAIN_PLAN_20261012.md` / `admin/U2_FLOW_COMMON_TOOLCHAIN_REPORT_20261012.md`。
- Query→Flow 的业务接收器仍未实现，不把 `contract_only` 标记改成完成。
- 运行状态放 `var`，模型 cache 不跨实验复用；保留未知调用成本和失败现场。
- 老板已确认三专业项目后续使用共同基础工具链：本机 SIF `8e6ee7…`、ORFS `5105b0a77`、OpenROAD `27288f5c90`，不使用移动 latest 作为身份。各项目原生旧工具链保留为历史复现证据；Flow 的共同模式完整工程验收已通过，两个 Code 尚未切换。
- Code 项目在共同基础源码上保留专业 overlay 与私有候选编译，分别记录源码/依赖/编译配置及实际 binary hash。原厂镜像没有 DPLEvolve evolve/GoalEvolve repair_power，不能只替换工具路径。专业组合补丁及跨阶段读写需真实验证，不强迫使用同一个未修改的原厂 binary。
- DPLEvolve 保留原生 Teacher/Student 与 evaluator；`DPL_EVOLVE_PLATFORM_PROFILE` 经薄桥接 `maybe_delegate(operation: str, argv: list[str]) -> int | None` 将共享构建、私有 relink、明确私有 binary 的完整原生评价提交 EF。无 profile 为原生复现，平台模式失败不退回独立执行。构建/评价仍在固定共同镜像内；输入/source/binary/指标绑定，三条基线显式保留 Diamond/negotiation/framework 含义。私有 relink 重新编译使用候选对象布局的 OpenRoad.cc。U3 工程通过，DF/DI/Query 数据入口仍待 L6；构建证据包只留证，不当作设计事实快照。L2 历史证据见 `admin/L2_DPLEVOLVE_REPORT_20261011.md`，本轮见 U3 报告。

## 已知缺口

P3 / U2 的 Flow 完整恢复、评价回流与共同环境，以及 L2 / U3 的 DPLEvolve 原生复现、共同环境与统一执行通过工程验收，业务确认待老板。U3 新候选由原生 helper 保留且独立重放通过，测得 HPWL 减少 3.53%，位移尾部增加、前段零收益均保留；这不是完整 PPA 或公平平台收益。GoalEvolve 新 AE-3、模型入口、共同迁移、统一执行与全部门禁尚未完成。两个 Code 统一数据入口、三项目协同及本机收益测量未完成。现有 Query 的查证/比较不能自动包装为已证明的因果结论。教学、新用户安装和论文交付暂缓。

源码优化交接包含候选源码、构建工具身份与实际评价，最终设计 PPA 通过兼容工具下的实际物理流程确认。共同基础版本已确认，专业改动的具体迁移与组合由源码差异、构建及真实运行决定。三个指定历史 ODB 在共同镜像下读取通过，只证明单向样本可读，不等于完整接力；同设计/PDK/约束/评价条件的兼容性属于 U5/L7 验收。
