# A75：独立重放优先消费已登记检查点

工程验证与code-check通过，老板业务验收独立。基线根 `63ab0d6`；本切片只修复独立验证的入口分流，不修改专业算法、公共契约或实际PPA。

## 问题与业务影响

A74详细布线期间检查后续验收路径，发现 `validation.replay` 用 `native_method.kind == native-ORFS-physical-repair` 排除ORFS从头重跑分支。A73/A74实际保存检查点的方法标签为 `native-explicit-GRT-repair`，虽然检查点、原ODB、PDK与GRT边界齐备，仍会被误分流到baseline。

该问题会让独立验证计算另一条从RTL开始的物理路径，而非验证实际接力的保存状态，既浪费计算，也可能导致无意义的PPA差异。A74当前的恢复/详细布线调用不走这个验证分支，因此不受本缺陷及修复影响。

修复依据是既有 `delivery-checkpoint.json` 契约：**已登记检查点决定实际重放边界，描述性方法标签不应覆盖它。** 没有检查点的历史ORFS baseline仍沿原完整流程；原检查点输入哈希核查、源生产者、GRT/已布线标记、PDK模型及独立子目录规则保持。

## 修改、数据流与验证

| 文件 | 本次职责 |
|---|---|
| `chip_evolve/validation.py` | 在ORFS baseline分支增加“没有已登记检查点”的条件，随后复用原checkpoint重放逻辑 |
| `admin/test_native_physical_relay.py` | 补充真实A74采用的方法标签，确认独立验证不重跑baseline或专业修复 |
| `admin/test_routed_validation_replay.py` | 在双PDK、三种路由边界原用例上补ORFS请求，确认已布线/未布线处理保持且禁止重新综合 |
| 本报告、A54、STATUS、TASKS、ARCHITECTURE | 同步当前阻断、已有公共边界与恢复状态 |

数据流仍为保存检查点 → 核对冻结输入 → 独立复制ODB/PDK → 原finish/qualify → EF → 事实发布。源检查点和历史结果不改；没有新服务、API、数据库或专业策略。后续改变独立重放选择应改 `validation.replay`，物理动作仍属于已有 `physical.qualify`。

修复前，针对性14项中7项失败、7项通过，新增失败均为错误进入baseline路径；其中真实方法标签用例由“不得重跑综合”的断言明确复现。修复后52项针对检查通过，包括旧baseline保留、双PDK路由保留、Flow候选重放和已完成证明的恢复。

根项目现有业务全回归 **740项通过**，相对733项新增7项；最终又在路由用例补充显式禁止baseline断言并复验52项，产品代码未再改变。三份修改文件Ruff、format与Pyright通过；产品前后导入集合相同，模块边界未变，逐文件diff检查通过。26份用户在途文件保持；根业务Python只改validation.py，当前运行的physical/delivery/jobs/leaf路径与A74发起时相同。

本轮是用例复现与源码修复，**没有新EDA或模型调用**，也不把回归夹具写成新设计实验。真实最终结果产生后仍需通过它自己的物理、功能与事实验收。

## 当前真实任务与恢复位置

A74同一EF `run-376fac03616245beb2e94e60b82c442e` 仍运行，已完成首轮详细布线并进入下一轮；中间违反计数不是最终DRC。本轮未停止或重启该任务。后续先观察session82815和同一EF run，终态后核对DRT/RCX/PPA与DF/DI，不重复派发。

本切片证据在 `var/business/a75-validation-checkpoint-priority-20261026/`，包含修复前失败、针对回归、740项全回归、静态检查、差异与保护文件核查。实际物理任务恢复点保持 `var/business/a74-ariane-nangate45-final-qualification-20261026/continuation.json`。

Ariane/Nangate45最终资格仍进行中，Ariane/ASAP7时序、Ibex/Nangate45完整证明、500ps协作及八组双次仍未完成；总目标保持进行中。
