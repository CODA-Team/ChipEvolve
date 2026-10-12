# 施工切片与验收状态

更新：2026-10-12。老板已同意本机施工并调整优先级；P3 / L1 完整真实工程验收已通过，最终业务确认待老板。八个本机切片及验收标准见 admin/LOCAL_EXECUTION_PLAN_20261011.md；共同版本选择已确认，来源审计完成，迁移切片计划见 admin/COMMON_TOOLCHAIN_PLAN_20261012.md。下表保留原 P 编号，尚未交付的能力仍如实标记。

| 切片 | 用户得到的效果 | 业务验收 | 模块 | 前置 | 状态 |
|---|---|---|---|---|---|
| P0 | 源码现状、保留/改造清单与施工依据 | 现有功能、偏离、原生接点及闭环证据有来源 | 六项目 / 文档 | 无 | 已完成 |
| P1 | 专业 Flow 的真实可复建基线 | 同一实验两轮三候选、真实模型、实际参数消费、固定 CP0 与功耗、完整物理产物 | Flow / OpenROAD | P0 | 已通过 |
| P2 | 统一管理物理阶段并保存可查询结果 | place→CTS→route→eval、实际取消、实体/指标导入、重启后来源一致 | EF / Toolkits / DF / SDK | P1 | 已通过 |
| P3 / L1 | 可查询、可继续同一优化实验 | 完整平台两轮实验；四个实际中断窗口；原计算和模型决策不重复；评价自动回流 | Flow / EF / Toolkits / DF / SDK | P2 | 完整真实工程验收通过，业务确认待老板 |
| P4 / L6–L7 | Codex 自主查询、专业交接与协同优化 | 真正 Flow/Code receiver；统一数据入口；预算内完整闭环；归因上下文可核对 | Codex / Query / Flow / Code / 底座 | L1–L5 | 待做，实际契约按源码审计确认 |
| P5 / L2–L4 | 两个源码项目原生复现并接统一执行 | DPLEvolve、GoalEvolve 分别 smoke/最小真实设计/新源码候选评价；实际 EDA 统一管理 | Code 项目 / 底座 | P3；原生复现优先于全面整合 | L2 原生复现工程验收通过，业务确认待老板；L3 环境/AE-1/模拟 smoke/真实 AE-2/p0 基线冻结通过；AE-3 未启动，模型入口待选择、上游九项失败未解决；L4 未开始 |
| U1 | 有固定源码、能构建和运行真实设计的共同基础工具 | 源码/递归依赖/SIF/实际 binary 可核对；GCD RTL→GDS、source-built 设计检查、DF/DI 事实/指标/单位/证据通过 | EF / Toolkits / DF / DI / admin | 共同版本选择与来源审计 | 工程验收通过，业务确认待老板；未开始专业迁移 |
| L5 | 统一设计数据与原因查询 | 设计实验视图、身份映射、事实覆盖、Query 诊断上下文与来源 | EF / DF / DI / Query / Toolkits | L1–L4 | 待做 |
| L8 | 本机量化产品收益 | ORFS PPA 基线、同一 Codex 数据增强前后 token/时间及正确完成情况 | 现有测量与记录 | L7，基线提前冻结 | 待做 |
| P6 公开交付 | 教学与论文产品 | 新用户安装、Tutorial、论文和公开评测材料 | 全平台 / 材料 | 后续显式发起 | 本轮暂缓 |

## 当前证据与限制

- 共同工具链：老板确认采用本机 10 月 SIF `8e6ee7…`，官方构建日志已把 OCI digest 与 ORFS `5105b0a77` / OpenROAD `27288f5c90` 关联；2,407 个镜像保留文件零内容差异、13 个关键源码 blob 核对通过、三个指定历史 ODB 可读。U1 共同源码构建/平台真实设计资格验证工程验收通过，业务确认待老板，U2 Flow、U3 DPLEvolve、U4 GoalEvolve、U5 组合接力均未开始。两个 Code 的定制功能仍须移植，L3 和 L4–L8 的缺口没有因版本选择而解决。来源审计见 `admin/COMMON_TOOLCHAIN_AUDIT_20261012.md`，本轮结果见 `admin/U1_COMMON_TOOLCHAIN_REPORT_20261012.md`。

- L3 / GoalEvolve 原生复现进行中：正式独立上游固定 `1cc20aa6`；AE-1、模拟 smoke、AST 初始化、AES / ASAP7 已发布源码真实重放及本机 p0 基线通过。基线为 |TNS| 12.37 ns、动态功耗 427,394,076,214.0958 pW、漏电功耗 95,383,300.50418 pW。AE-3 尚未启动；项目 API 入口与本机 Codex 登录之间的选择待回复，上游缺历史配置/知识文档的九项失败未解决。L3 未通过全部门禁，报告见 `admin/L3_GOALEVOLVE_REPORT_20261011.md`。

- L2 / DPLEvolve 原生复现工程验收通过：独立工具源码构建、GCD 真实 RTL→布局快照、三条原生合法基线、prompt/workspace smoke、一轮真实 Teacher/Student/review、真正新源码候选及固定源码独立重放均通过；37 项总核查见 `var/code-agent/l2-dplevolve-20261011/l2-acceptance.json`。候选 HPWL 2941.7 µm，比 OpenROAD 默认 2969.1 µm 少 0.92%，仍略差于项目自带框架 2941.1 µm，最大位移增加，原生选择为拒绝晋升。工程复现与优化质量分开，业务确认待老板；统一执行/数据尚未接入。详见 `admin/L2_DPLEVOLVE_REPORT_20261011.md`。

- P1：`var/flow-agent/p1-native-20261010-retry2/p1-acceptance.json`。
- P2：`var/flow-agent/p2-a2-stage-20261010/p2-acceptance.json`。
- P3 工程收尾：`admin/P3_SLICE_REPORT_20261010.md` 及报告所列独立门禁记录。模拟恢复检查不代替真实物理实验。
- P3 / L1 完整真实工程验收：`var/flow-agent/p3-platform-campaign-20261011-retry3/p3-acceptance.json`；两轮六候选、18 项物理任务、四个真实中断、12 个实际评价快照和模型账本核查全部通过。当前汇报见 `admin/P3_SLICE_REPORT_20261011.md`。
- P1 单次实验在固定功耗条件下观察到 |TNS| 改善约 5.73%，不是平台公平收益结论。
- Query 已有查证、比较和引用；完整“为什么”的归因能力仍需后续业务标准及验收。

## 后续协作流程

老板给验收标准 → 工程师列改动文件/数据流/验证/影响面 → 老板确认计划 → 实现和工程检查 → 老板运行验证 → 通过后记录验收及三句话总结。任何工程检查或业务验收未过均不把该切片记作完成。
