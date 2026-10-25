# A40：Goal 续作交付使用原冻结工艺

基线 `112c3a1`。核查 A39 续作入口时，发现最后的 `delivery.checkpoint` 将 PDK 固定为 `previous/inputs/asap7`：Nangate45 续作即使专业优化已经完成，也会在共同交付阶段选择错误的 RC 目录；ASAP7 的自定义冻结目录同样被忽略。

## 定点修复

`chip_evolve/continuation.py` 只改最终交付的 PDK 选择：优先使用原 profile 明确冻结的 `pdk_root`；没有该字段的旧记录按明确配置的设计平台寻找 `previous/inputs/<platform>`。不改原 benchmark、源码、目标、评分、轮次、物理动作或公共契约，不改变历史实验。

`admin/test_goal_continuation_pdk.py` 从原 parent/checkpoint 经过现有续作配置与交付调用，核查 ASAP7/Nangate45、显式冻结目录/旧布局四种情况；专业推理与最终计算使用单元夹具，没有把这些测试记为真实搜索或 PPA。旧实现真实复现三例错误、一例通过；修复后四例均通过，原目标保持。

## 验证与边界

- 相关 **32 项检查通过**；根业务 **670 项回归通过**；Ruff、格式、实际依赖环境 Pyright、逐文件 diff 检查通过。
- 对 A39 实际 EF 准备产生的 profile 进行选择核查，得到真实 `inputs/nangate45`；其 `setRC.tcl`、`rcx_patterns.rules` 的 SHA 与 A38 真实原生控制 `run-6947cab22c8447c291c25afff6deb55f` 使用的文件逐字节一致。复用已有有效工具验证，没有为了目录选择修复再运行 EDA。
- 26 个用户保护文件 SHA 保持。无新增服务、API、数据库、跨源码依赖或服务部署动作。
- 证据：`var/business/a40-goal-continuation-pdk-20261025/test-before.log`、`targeted-regression.log`、`root-regression.log`、`actual-pdk-selection.json` 和静态检查日志。

数据仍沿原 parent/checkpoint→原 Goal 续作→EF producer→共同物理交付→DF/DI；本次修复保证这条路在交付时继续使用该输入对应的工艺。要改变冻结工艺位置，在下一次明确任务 profile 中配置 `pdk_root`，不用再改业务代码。

这不是一次完整新续作/DRT/RCX/PPA 证明。A38–A40 解决已定位的崩溃、源码/cache 绑定和跨 PDK 交付错误，长搜索仍暂停；GCD/Nangate45 500 ps 基线与协作、Ibex/Nangate45 完整证明、八组双次最终 PPA 等原业务缺口仍在。
