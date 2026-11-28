# A59：Ariane/Nangate45 剩余电气违反已在 GRT 阶段清零

基线根 `29917a7`，接续 A48 原 14 动作及完整 GRT 修复。此次按具体诊断、原生定点动作、短验证、code-check 推进；没有新模型搜索、产品代码、服务、公共接口或数据库修改。**本轮解决 GRT 电气阻断，不代表最终 DRT/RCX PPA、完整功能证明或采用通过。**

## 问题在哪里

A48 原末尾留下 4 项 slew、8 项 cap 违反，涉及 11 个不同引脚。通过 EF 在该次登记的精确 ODB 上只读检查，11 个实例/网络均无 do-not-touch 限制；其中三个 slew 驱动传播为常量，分别是：

| 驱动 | 原单元 | 常量 | 本轮显式动作 |
|---|---|---:|---|
| `issue_stage_i.i_scoreboard/_45684_/ZN` | NAND2_X1 | 1 | NAND2_X4 |
| `issue_stage_i.i_scoreboard/_45040_/ZN` | OAI22_X1 | 0 | OAI22_X4 |
| `issue_stage_i.i_scoreboard/_45903_/ZN` | NAND2_X1 | 1 | NAND2_X4 |

现有 `RepairDesign::repairDriver` 的通用修复条件排除 `sta::isConstant` 驱动；仅重复默认 `repair_design` 不能据此期待这些对象被处理。三个对象也不在 A48 的原 14 个显式选择中。本轮保留算法，依据实际对象选择已有单元替换动作；不是在平台代码中加入 Ariane 特判，也不把它说成新一轮 Teacher/Student 或 ECO 模型会话。

只读任务 `run-392d7dc4a571425ea16619d9b1327495` 成功，查询输出与原件均由 EF 登记。原源 result、ODB、SDC、SPEF、脚本及两个 Liberty 身份保持。

## 两步定点修复与实际时序

第一步复用 A48 ODB，处理上述三个常量驱动，并显式选择原生 `repair_design -slew_margin 10 -cap_margin 10`、原 Diamond 合法化和增量 GRT 收尾。没有修改修复器或原专业评分。原生另实际 resize 2 个实例、插入 611 个 buffer；不能把这些动作省略成“只改三个单元”。

这一步初始化时重新建立了 GRT，因而得到自身的 **5 slew / 51 cap** 起点，与 A48 末尾 **4 / 8** 不是同一次路由状态。下表使用本轮自己的前后记录；不改写 A48，也不混入旧提取 SPEF 指标。

| 当前实际节点（均为 GRT 估算） | setup WS (ps) | setup TNS (ns) | hold WS (ps) | hold TNS (ns) | slew | cap |
|---|---:|---:|---:|---:|---:|---:|
| A59 本轮起点 | +269.753116 | 0 | +19.383717 | 0 | 5 | 51 |
| 三驱动替换 + 原生 margin10 修复 | +284.388965 | 0 | +19.383717 | 0 | 0 | 1 |
| 从保存 ODB 恢复 GRT，最后一动作前 | +284.388965 | 0 | +19.383717 | 0 | 0 | 1 |
| 最后一缓冲器定点增大后 | +284.388965 | 0 | +19.383717 | 0 | 0 | 0 |

WS 是可为正的最差裕量，不能把正 WS 写成负裕量指标的改善百分比；这里 setup/hold WNS 与 TNS 均为零。最初 setup 裕量增加约 14.636 ps，最后一步保持，而电气违反清零。没有测量新功耗或面积收益。

第二步定位唯一剩余的 `i_cache_subsystem.i_nbdcache/wire32058/Z`：BUF_X4 驱动电容约 0.26 pF，限制约 0.24 pF。新版 GRT 能从 ODB 中的 guides 恢复路由，故不再运行整段新的 `global_route`；先恢复寄生估算并核对保存的 setup/hold WS 与 TNS，再将该 BUF_X4 替换为 BUF_X8，完成原合法化/增量更新。

恢复前后的指标字典完全一致；定点动作后 slew/cap 为零，setup/hold TNS 仍为零。合法化仅移动一个单元约 0.4 µm。两份网表的字节差异只有该实例的 BUF_X4→BUF_X8，连接和其余内容相同；这项差异核对不代替完整功能证明。

## 执行与数据回流

| 任务 | EF run | 实际范围 |
|---|---|---|
| 原生 margin10 修复 | `run-c95296994a15465cbc02d5fea6ccfc9b` | 约148.59秒墙钟，CPU247.34秒，峰值约3.09GiB；单次明确配方 |
| 保存 GRT 恢复 + 最后一 buffer | `run-e4d53b33ca2146af8b0acc656a22fe12` | 约54.43秒墙钟，CPU82.39秒，峰值约2.80GiB；一次定点动作 |
| 第一修复阶段事实导出 | `run-e0a998517cbe4d7d9b6a0306e163f70e` | 既有 ORFS 元数据适配器，无 EDA 重算 |
| 最后修复阶段事实导出 | `run-75a8fc1032194a879db83010d1bfc866` | 同上；原生 producer/scope 保留 |

最终快照 `a59-run-e4d53b33ca2146af8b0acc656a22fe12-grt-repair`。两节点的七项原始指标及时间单位通过 EF→DF→DI 逐值核对，安装包 Query 按精确 run/snapshot/revision 回答 TNS=0 ns。实际沿 Query 引用取回原始 metadata 字节，SHA 与本次输入一致。

这些快照提供阶段指标及原件，不冒充新完整对象索引或最终 PPA。后续需要当前全量对象时，应从最终选中的新 ODB 正常导出，不能拿 A48 或旧最终对象快照代替。本轮没有全量重复导入 Ariane 对象库。

## 短验证和 code-check

- 三个原生 EF 任务及两次事实导出成功；13 份原生捕获文件/日志经公共产物核 SHA，保存的源 ODB 与原历史输入不变。
- 最后一步的 saved-GRT 复现、单一网表差异、两个 SDK 快照、Query 精确范围及来源字节核验通过。
- 五份私有驱动/核查脚本执行 Ruff、格式、Pyright；最终日志单独保留并逐项检查。一次类型检查选了不含已安装 DI SDK 的工具解释器，已改为指定实际 client 环境；Zip 流哈希的类型不匹配改成逐块读取，不加 ignore/cast。没有靠修改产品或安装依赖消除这些私有检查问题。
- 产品源码与 A57 检查点相同，复用其根712项、ECO37项/2子测试及静态回归；本轮验证以真实原生短执行与公共数据读取为主，不重跑未变产品的全场测试。
- 26 个用户保护文件保持，DF/DI WIP 不动，EF 五类活动状态均零。没有重启服务、修改容量、sudo 操作或长优化任务。

证据与实际配方位于 `var/business/a59-ariane-residual-electrical-20261025/`，关键记录为 `residual-driver-identities.json`、两份修复 preflight、两次原生 execution、两份阶段 facts receipt、`last-cap-netlist.diff`、`final-functional-verification.json` 及门禁日志。

提交只含本报告、A54/TASKS/STATUS 状态索引及 ARCHITECTURE 接续边界记录；运行配方、ODB、网表、日志留在 var。后续调整本次行为，应修改对应私有配方/动作选择；无需修改 EF/DF/DI 或原专业算法。

## 仍需完成

Ariane/Nangate45 现在有电气闭合、setup/hold TNS=0 的真实 GRT 后继，可以用于后续最终物理资格；**尚未做 DRT/RCX、完整功耗/面积测量、功能证明及采用**。不能直接计入八组正式优化结果或双次均值。

其他阻断继续保留：Ariane/ASAP7 的真实 setup/slew 债及 SRAM GDS、Ibex/Nangate45 完整证明、500ps 协作和八组双次。新长实验仍暂停，总目标未完成。下一步核查缺失 SRAM 物理资料的真实来源及交付边界。
