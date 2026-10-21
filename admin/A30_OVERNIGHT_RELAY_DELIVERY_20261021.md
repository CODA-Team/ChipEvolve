# A30 夜间交付：八组路径与 GCD 机制案例

老板 2026-10-21 最新确认：保留所有设计已有协同路径，交付四设计 × ASAP7/Nangate45 的逐棒指标/路径图；GCD 另给具体动作、诊断依据和生效机制的详细案例。以 10 月 22 日早上可审阅的实测素材为目标，未结束节点明确显示实际状态，不把计划中的接力画成已完成。

## 交付形式

- 八格总览：每组设计/PDK、baseline、实际专业路径、当前结果、验证/采用状态。
- 长表：每个实测节点的父项、Agent/策略、PPA、setup/hold WS/WNS/TNS、布局/电气/布线违反、相对父项变化、测量条件、来源 SHA 与实际产物。
- 八组路径图：保存改善、拒绝、无收益及分叉；Query 提供依据，不虚构其独立 PPA 增益。ORFS baseline 与 Flow Agent 区分。
- GCD 案例：Flow 为什么需要接力；DPL 原生 HPWL 改善为何未直接转化为合法最终 PPA；Goal 如何处理功耗与时序冲突；ECO 的实际改善与未采用原因；Codex 为什么保留 G02 而不是最后一棒。

## 实验工作清单

| 组合 | 已有/在途 | 本夜接续 |
|---|---|---|
| GCD ASAP7 | Flow→Goal、Flow→DPL→Goal 两条合法接力，Goal→ECO 拒绝支路 | 复用全部结果、原始动作/源码/归因/证明，详细讲解；不重跑 |
| JPEG ASAP7 | Goal→ECO 负接力、Goal→原生 VT/size 修复合法结果 | 全部保留与追踪；不重跑采用产物 |
| Ibex ASAP7 | Goal→原生时序/VT/size 修复，完整证明在运行 | 原证明继续；另补布局→Goal 源码复用的真实分支 |
| Ariane ASAP7 | 原 Goal 一轮四 Student 完整结束，三最终结果均拒绝 | Query 后尝试原生 ECO 两轮；完整 SRAM 库加载与导出适配先检查 |
| Nangate45 四组 | GCD/Ibex baseline、Query 和原生 Goal 搜索已运行；JPEG/Ariane baseline 已派发 | 各补 DPL→Query→Goal 的实际专业接力，原生四 Student 搜索为独立分支 |

DPL→Goal 补充路径使用**已验证的专业源码/二进制与原配方复用**，不是新 Student 搜索；每次仍消费目标设计实际检查点，运行原生专业工具和完整物理测量。Goal 源码来自已验证 DG1，701 声明源码已核对，原模式 power_then_timing/legacy_setup 保留。复用路径的源码来源设计与当前目标设计分开标注。现有 Nangate45 四 Student 搜索继续，不热改、不冒充为同一祖先分支。

## 范围和工程纪律

只复用既有 CLI/SDK/EF/DF/Query 与原专业能力，不新增服务/公共 API/评测数据库，不提高系统权限，不改服务容量，不把其他长期问题清零作为前置。ECO 对 SRAM 只补冻结 Liberty 清单贯通加载/回退重载/最佳结果导出；原动作、评分、压缩上下文、最佳状态回退保持。

`admin/paper_relay_paths.py` 只读已有结果导出路径；每条边来自历史已核查父项或实际 input-receipt；跨条件不算父项收益；每次导出保存原结果字节快照。它不做自动推理、采用判断或调用模型。业务采用仍由 Codex 根据实际最终事实和必要功能验证决定。

夜间脚本是本次既定任务清单的 CLI 组合，不重造 Agent harness。实际失败写出原错误并保留证据，不盲目循环新模型/EDA任务；数据导出随真实新结果更新。难设计和失败分支不会阻塞其他组合的材料交付。
