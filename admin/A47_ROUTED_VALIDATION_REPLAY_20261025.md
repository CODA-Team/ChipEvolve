# A47：独立重放保留原检查点的布线边界

接续根 `8ce9a06`。继续“具体诊断→定点修复→针对性短验证→code-check”，无专业搜索/模型、服务调整或历史改写。

## 实际阻断

`delivery.finish` 已能对标明 detailed_route 且原生DRC为0的检查点保留布线、重新提取和测量；但 `validation.replay` 复制检查点时只写 independent-routing-replay 类型，丢掉了原 physical_stage、route_drc 及其证据。因而独立重放退回拆线/重新布线，可能改变专业交付结果。

唯一产品修复在 `chip_evolve/validation.py`：复制这三个原有内部字段。独立重放的类型、原结果引用、输入SHA和producer保持，仍由原 finish/qualify 判断保留或补全布线。没有新公共字段/签名/API，也没有替专业算法做选择。DRC非零或未声明详细布线的输入仍走原补全路径。

## 检查结果

- 修复前正确夹具复现4失败/2通过。最初夹具把字符串交给Path函数的6失败另留原日志，不当成产品失败证据。
- 修复后41项相关检查、712项根业务回归通过；两PDK覆盖已布线0DRC、非零DRC和未完成布线。Ruff、格式、Pyright、差异检查通过。
- 代码审查：仅7行局部传递，未改变物理命令、RCX参数、原算法/目标/评分、DF/DI边界或EF资源。26个用户保护文件哈希保持。

## 真实短验证

用A45真实GCD/Nangate45 500ps已布线来源作为正例；该来源的ORFS归档原5_2_route.json明确DRC0，原件哈希与来源身份留存。私有诊断checkpoint明确标为 routed-source-diagnostic，**不伪装一次ECO会话或新的优化结果**。

原 `validation.replay → delivery.finish → physical.qualify → EF → DF/DI` 实际执行：

| 操作 | EF run | 状态 |
|---|---|---|
| 保留布线/检查DRC/RC提取 | `run-ba7b0de339164aef9d1e3d35d90ec2ea` | succeeded |
| 共同测量 | `run-02033b3a459a46a99834a3b5c78ccb9b` | succeeded |
| OpenDB事实 | `run-0a2a45759b0543c8a2ba2c1aa5e4f718` | succeeded/DF |
| 指标事实 | `run-a02f441659c14fbba99d25ca5bd9566a` | succeeded/DF |
| OpenSTA事实 | `run-4e7ba5c9359940af8a32d22ba887adb7` | succeeded/DF |

实际Tcl没有拆线、global_route或detailed_route优化调用。原网表字节、实例/引脚/特殊网段及632条信号网连接保持；原全部指标值相同，包括功耗2.2321124561mW、cell675.64µm²、setupWS+40.0912ps/holdWS+110.517ps、setup/hold TNS0及全部违反0；同condition/objective，SDK事实查询通过。没有新增搜索、模型或功能证明。

最初检查要求DEF字节相同而失败；实际原生DRC/提取后的wire序列编码有变化。保留原DEF diff、失败断言和原件，不重新执行已完成EDA；随后只读核验网表、连接、放置相关段和全指标同值。**不依据DEF文本哈希推断布线几何逐形状相同**，本切片不作这种扩展主张。检查脚本数值差分最初遇到单位字符串，也保留诊断；最终比较全部原值，不把单位字段做减法。

## 文件职责与接续

`validation.py` 修复独立重放物理边界传递；`admin/test_routed_validation_replay.py` 覆盖真实调用链的边界回归；本报告与TASKS/STATUS/ARCHITECTURE记录可续接状态。若要改此处行为，在replay的检查点元数据传递及其既有finish路由判断处调整，不改专业控制器。

证据位于 `var/business/a47-routed-validation-replay-20261025/`：原/新测试、静态日志、preflight、source-route-evidence、actual-replay-check、SDK-facts、DEF diff和final-code-check。原产品运行SHA、输入/目标/RC文件保持。工程检查通过，待老板业务验收；长搜索仍暂停。

## 当前剩余业务缺口

A33–A47已逐项处理Query精确身份、ECO技术输入、DPL任务绑定、Goal寿命/构建donor/跨PDK交付、Flow反馈恢复、共同测量条件和原生变量时钟接入等具体阻断。A45新500ps来源已物理闭合，A46仅完成原生Flow来源准备，不能当作新完整搜索资格。八组双次优化结果仍不完整；Ibex/Nangate45完整证明仍无整体PASS；Ariane原手工GRT只验证两动作，不能当成完整修复或PPA收益。DF/DI用户源码与已安装包身份差异仍分列，未擅自热切。下一步按实际任务核查这些缺口，不增加额外框架或用长搜索调试环境。
