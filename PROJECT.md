# Agentic EDA 产品目标

本项目是 Codex 消费的 OpenROAD 垂直能力层。用户在 Codex 中提出设计目标，Codex 调用专业能力完成实验、取得事实与归因证据，并判断结果和下一步。产品目标来自老板已确认的 P0 规划、2026-10-10 补充协议及 2026-10-11 本机施工要求。

2026-10-15 A8：正式入口增加已完成专业的交付恢复、Goal原生续作、统一比较与验证；GCD真实中断恢复、18输出证明、独立布线七项PPA同值及验证重入不新增任务通过。A9接续用AES验证迁移，完整专业搜索尚未验收。详见admin/A8_LOCAL_WORKFLOW_REPORT_20261015.md；下文旧A4/A5状态保留历史含义。

最新 A4 单机交付：Codex 可通过根 `chip-evolve.py` 指定设计、能力、目标、预算和源结果，平台自动准备原专业输入、统一 EF 执行、共同复测、事实入库和 Query 诊断交付。GCD 四专业调用和 AES 的 ORFS→Goal 原生基线/数据链路已实测；当前诊断进入实际专业提示。工程通过、老板业务验收待确认，范围和跨设计限制见 [A4 报告](admin/LOCAL_BUSINESS_ENTRY_REPORT_20261014.md)。A5 的单项与组合实际收益独立验收，不能把接口可运行当作联合优化成功。下文 A1/A2/A3/N/O/U 状态保留历史含义。

A5本机对照收尾：GCD/AES的Goal原方法经专业EF桥接或直接EF执行，各7项最终PPA逐值相同；完整Flow→DPL原框架→Goal新源码→ECO已正常运行、共同复测并入库，时序未达，不采用。当前保留Goal新源码单项，满足本轮物理约束并通过网表逻辑等价，相对ORFS功耗约−36.9%、单元面积约−23.2%，不是联合收益。DPL修复后三个新Student取得真实布局评价，补充轮次三小时超时、未正常收尾，不记完整原生成功。实际指标、原评分与最终验收落差及成本见 [A5报告](admin/LOCAL_PROFESSIONAL_COMPARISON_REPORT_20261014.md)。老板业务验收独立；本轮不推进公开benchmark和token节约第五项。

A6/A7最终工程交付：长任务续租与共享文件托管锁问题经复现修复，真实构建/大输入/默认lease/完整DPL轮次通过；Goal原Teacher/四Student正常收尾，无新源码晋升。已有组合父源码使用原生时序恢复后，在共同FF/310ps下闭合时序，功耗1.1775332mW、单元面积40.27µm²，较旧合法单项分别降低14.5755%/7.2220%；18个功能输出等价、空目录七项PPA同值、DF/SDK与真实Query反馈通过，已采用。相对ORFS功耗−46.1086%/单元面积−28.7041%，core/die不增；这是GCD实际分支收益，公平总预算团队优势未验证。历史失败与旧结果保留，老板业务验收独立。报告见admin/A6_LONG_TASK_RELIABILITY_REPORT_20261014.md和admin/A7_COLLABORATION_QUALITY_REPORT_20261014.md。

## 最终用户能做什么

1. 提出时序、功耗、面积约束，让 Codex 查询当前设计及问题证据。
2. 调用专业 Flow Agent 自动优化参数，保留原项目的优化算法和阶段继承。
3. 通过统一执行与数据管理，查到每次实验的输入、结果、产物和来源。
4. 实验中断后继续同一实验，复用已完成的计算和模型决策。
5. 调用 DPLEvolve、GoalEvolve 做源码优化，调用 TimingECOAgent 做时序 ECO，并复用平台记录和查询能力。

这些是目标能力，当前交付范围见 [TASKS.md](TASKS.md)，不能全部视作已实现。

## 工程贡献与业务规则

- 两项基础设施：执行底座解决可复现执行与实验追溯；数据底座解决数据和产物统一管理。
- Query Agent 基于数据底座提供状态理解、有证据的归因及决策上下文，共同解决第三个工程问题：可观测性与归因。
- 数据接口是 SDK 和接口语义，不是第三个后台底座。没有独立“评测底座”。
- 工具负责测量 TNS/WNS/功耗等事实，Codex 判断是否更好、是否达标及下一步；Flow 内部原有候选评分与优化算法保留。
- Codex 是入口与通用 Agent harness。平台不重造通用推理循环、上下文系统或沙箱；专业项目内部可选 API/Codex 模型后端。
- Query-Agent 是 Codex 的 EDA 垂直形态：通过领域 harness、统一数据/工具和专业技能增强同一 Codex 的查询、理解、分析与诊断能力。评价这种增强的实际效果与成本。
- 所有专业项目的实际 EDA/评价统一由执行底座管理；设计事实与诊断上下文使用数据底座、数据接口和 Query 能力。未完成的入口收口按切片接入，不虚报统一完成。
- 固定评价条件下的可行结果才参与改善判断。超出功耗约束的时序改善不计可行收益。
- 失败、回退与未知模型用量保留；一次实验改善不能等同于公平对照收益。
- ReviewDSE 与 DPLEvolve 为同一项目，工程实现为 CODA-Team/DPLEvolve；GoalEvolve 独立。
- 2026-10-14 老板授权接入 ASU-VDA-Lab/TimingECOAgent，替代 ECO 暂缓；保留上游来源和专业算法。本机 GCD 已实测四专业能力调用、统一执行、数据回流和原生轮次。A1 审计发现 DPL 候选被后续流程重跑覆盖，撤回旧“完整专业接力通过”结论，A2已修复布局交接并完成匹配控制实验；A3已把共同目标送进四专业真实模型、执行与最终数据查询。该DPL候选最终PPA退化，不替换已有合法最好结果，完整四专业联合收益仍未达。详见`admin/HANDOFF_OBJECTIVES_REPORT_20261014.md`。Goal 四候选的原生指标恢复后仍因电气违例被原规则拒绝，未晋升源码；旧完整链路未获得满足原时序条件的整体 PPA 改善。O2 的独立 ORFS/ECO/功耗回收/Query 修复分支在共同条件下得到闭合时序、功耗及单元面积略降的新候选，不算四 Agent 联合收益。详见 `admin/COLLABORATION_AUDIT_20261014.md`。论文和 Tutorial 不作为这轮施工范围。
- 新材料中“Reset”的调参职责对应当前 Flow Agent；未经确认不改工程名称。

## 产品形态与交付

当前优先在老板的 Linux 本机跑完整 Flow、分别复现和接入 DPLEvolve/GoalEvolve、统一执行/数据入口，并完成协同 PPA 优化。ORFS PPA 基线和同一 Codex 使用数据能力前后的 token/耗时测量属于本机验收。

新用户安装、公开发布、ASP-DAC Tutorial 和论文交付暂缓，保留公共接口与模块边界供后续扩展。老板于 2026-10-11 明确同意本机施工，路线见 admin/LOCAL_EXECUTION_PLAN_20261011.md；实际完成状态见 TASKS.md。

2026-10-12 老板确认采用本机 10 月 ORFS 镜像作为三专业项目后续共同基础版本。其官方源码为 ORFS `5105b0a77` / OpenROAD `27288f5c90`，通过 SIF 来源、官方构建日志和内容对照核实；固定 digest/commit，不自动跟随移动的 latest。两个 Code 在共同源码上保留定制能力与私有候选构建；历史原生环境留作复现证据，新版本使用新实验及本机基线。截至 2026-10-13，Flow / DPLEvolve 分别在 U2 / U3 完成工程验证，GoalEvolve 的迁移和 GCD 完整接力现已通过工程核查；原 U4 AES 历史轮次不改写，最新状态以夜间报告为准。审计与迁移切片见 admin/COMMON_TOOLCHAIN_AUDIT_20261012.md 和 admin/COMMON_TOOLCHAIN_PLAN_20261012.md。

本轮最终交付与真实效果见 [admin/OVERNIGHT_GCD_REPORT_20261014.md](admin/OVERNIGHT_GCD_REPORT_20261014.md)，架构与实际接口见 [admin/OVERNIGHT_GCD_INTERFACES_20261014.md](admin/OVERNIGHT_GCD_INTERFACES_20261014.md)。所有工程通过状态仍待老板业务验收。
