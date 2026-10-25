# A78：查清 Goal 原生功耗策略适用条件与阶段功耗缓存

基线根 `039ecad`、Goal `33661a5`。本轮完成源码审计及三次有界 EF 原生诊断，未修改产品源码、专业算法、评分或公共接口；没有 Teacher/Student 搜索和模型调用，没有新增采用。工程检查通过，老板业务验收独立。

## 业务结论

Goal 原专业能力在共同工具版本下能真实执行，但策略须与 PDK、当前设计状态匹配。`mid_area_reclaim` 仅产生纯 VT 交换，Nangate45 为单 VT，因此本次 0 候选是策略不适用，并非平台丢任务。`early_forced_reclaim` 实际接受 271 次缩尺寸、29 次去缓冲，减少面积，但默认允许的时序债务使闭合设计重新违反 setup，并增加 slew/cap，不能采用。

另查明 A77 **私有诊断脚本**遗漏了原 Goal 已有的功耗缓存刷新。A77 的阶段功耗差值撤回，不作为优化收益；时序、电气及面积的拒绝结论保持。A74 独立新进程的最终测量未受该遗漏影响。原 Goal 的正式 evaluator 已有刷新，此轮无需给 Goal 再造一套机制。

## 源码核查

- 原 `RepairPowerPolicy.cc::generateMidAreaCandidates` 只构造纯 VT 候选；`early_forced_reclaim` 可构造缩尺寸、去缓冲及 VT 动作。
- 原 `Resizer.cc::replacementPreservesMaxCap` 检查前级负载增加，不能解读成所有输出电容、slew 和 hold 都有保护。
- 原 early 默认最大 WNS 损失为 0.5ns，允许 TNS 扩大；源 TNS 为 0 时仍有绝对预算底值。因此“原策略通过内部规则”不等于“最终业务约束通过”。原生已有 `-max_wns_drop` 可供后续按状态显式选择，不改算法或放宽验收。
- 原 `goalevolve/evaluation/contest2026.py::_POWER_CACHE_REFRESH_TCL` 使用全局活动 set/unset 刷新缓存；本轮诊断在每次报告前复用相同命令。

## 两项原生策略短验证

相同 A74 来源、Nangate45 库、6ns 时钟和 A72 已核对的 Goal 二进制，SHA `275790d63baa00404494f8fd7b707e19d463d6ac7ae65edeef863aec1d0e3da6`。300 moves 为本次诊断上界，未修改正式专业搜索配置。每次均保存动作后、后续重建 GRT 前的中间状态。

| 节点 | power mW | cell µm² | setup WS ps / TNS ns | hold WS ps / TNS ns | slew / cap |
|---|---:|---:|---|---|---|
| 两次相同输入，完整 SPEF | 159.392521 | 739267.193 | +261.794 / 0 | +42.930 / 0 | 0 / 64 |
| mid 原策略后，原 SPEF，无改动 | 159.392521 | 739267.193 | +261.794 / 0 | +42.930 / 0 | 0 / 64 |
| mid 无动作控制，重建 GRT | 160.227120 | 739267.193 | +283.277 / 0 | +18.288 / 0 | 0 / 16 |
| early 原策略后，混合寄生 | 159.317121 | 738828.589 | −110.256 / −5.530243 | +42.930 / 0 | 75 / 166 |
| early 后重建 GRT | 160.154119 | 738828.589 | −87.186 / −3.845758 | +18.288 / 0 | 74 / 119 |

mid 的输入/动作后网表 SHA 完全相同，原生 committed/trials/rejected 均 0；其重建 GRT 的差异是寄生初始化变化，不是优化收益。early committed=300、trials=314、rejected=14；相同初始化 GRT 控制与 early 后继有小幅功耗、面积差异，但后继不满足 setup 和电气条件，未做最终 DRT/RCX/采用，不计算最终 PPA 改善。

原生 EF 分别为 `run-816ad8baae2a4f36bd307def8071d07c` 和 `run-d20b00bf74aa4299a5513585848ccc9a`，各 7 份输出按公开 EF bundle/manifest 校验；源结果、ODB/SPEF/SDC、库、二进制和 160 份构建源码身份核对。

## 功耗缓存的独立复现与更正

EF `run-a082aae1552f4eb88e7018cd8eb946ae`，同一保存 ODB、同一进程、不修改设计：

| 读数时点 | power mW | setup WS ps | hold WS ps |
|---|---:|---:|---:|
| placement RC 首次报告 | 157.849103 | +479.782 | −16.771 |
| 改用 GRT，未刷新缓存 | 157.849103 | +372.243 | −33.774 |
| GRT，原 Goal 缓存刷新后 | 160.476595 | +372.243 | −33.774 |

缓存刷新前后 GRT 的四个 setup/hold WS/TNS 精确相同，power 改变 2.627492mW，确证原生 `estimate_parasitics` 后报告可能读取旧功耗。此新数值来自恢复保存 GRT 的测量，不声称与 A77 活动路由逐网完全同值；撤回 A77 未刷新功耗的收益含义，保留原始记录，未覆盖旧快照。

## 数据交付与 code-check

无动作控制与缓存新测量通过既有 ORFS metadata adapter → EF → DF → DI → 独立安装 Query 发布；两快照数值、Query 的 hold TNS/power 及证据原件完整字节/SHA 核对通过：

- `a78-run-816ad8baae2a4f36bd307def8071d07c-mid-VT-no-op`
- `a78-run-a082aae1552f4eb88e7018cd8eb946ae-fresh-power-cache`

后者标明受影响的 A77 快照及 stale-power 限制。early 诊断的完整阶段、原生遥测和 7 份 EF 原件保存在私有证据中，未伪装成最终结果。

四份私有驱动 Ruff/format/Pyright 全通过。26 份用户文件与根产品源码 SHA 保持，复用相同根源码的 740 项回归；产品未变，不重复跑全场。证据目录 `var/business/a78-goal-mid-power-audit-20261026/`，含 `Goal-stage-analysis.json`、`early-stage-analysis.json`、`power-cache-analysis.json`、`fact-verification.json`、`code-check.json` 及 `continuation.json`。

下一项针对 ECO 持久进程 `dump_iter_qor` 的实际调用链核查同类缓存风险，先用实际 helper 复现再修；不盲重跑上述负策略。Ariane 最终电气/功耗资格、ASAP7 闭合、Ibex/Nangate45 证明、500ps 协作、八组双次及大设计 DF 交付耗时仍未完成，总目标继续。
