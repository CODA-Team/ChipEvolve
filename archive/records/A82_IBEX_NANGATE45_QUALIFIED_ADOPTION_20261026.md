# A82：Ibex/Nangate45 独立物理验收与采用，修复检查点入口的旧请求误读

基线根 `d34d746`。A81补齐完整功能证明后，本轮继续现有业务验收流程，未重算PDR、未运行新专业优化搜索。**既有Ibex/Nangate45分支已通过独立DRT/RCX、共同测量、DF/SDK/Query核验，并在本轮runtime登记采用。**工程检查通过，老板业务验收独立。

## 具体阻断及两文件修复

第一次接续在任何新EDA提交前失败：旧原生两单元修复的 `request.json` 不含业务CLI的 `capability`，而源结果有合法的 `delivery-checkpoint.json`。`validation.replay` 虽然已有检查点优先规则，但条件顺序先解析请求，抛 `KeyError: capability`。

修复只调整判断顺序：**先确认没有保存检查点，才考虑读取请求并进入ORFS baseline分支**。有检查点的结果按已有SHA核验与物理边界重放，不要求旁边无关请求使用业务CLI格式。没有加入猜测默认值、异常吞掉或新的兼容接口。

| 文件 | 本次职责 |
|---|---|
| `chip_evolve/validation.py` | 将检查点判定移到请求读取之前；现有函数签名、其他验证/重放逻辑保持。 |
| `admin/test_routed_validation_replay.py` | 增加无capability原生请求与无关不可解析请求两类，在双PDK和三种布线边界组合下验证真实重放调用/脚本，不改变历史baseline测试。 |

12项新增场景在旧源码全部失败，修复后通过；53项针对检查、根项目完整 **754 passed**，Ruff/格式/Pyright通过。AST和依赖审查确认仅原 `replay` 判断顺序改变，其他函数/类、公共参数及导入关系保持。失败状态进入现有历史，恢复沿同一验证key继续，没有重复证明或重启优化。

## 真实独立验证

原检查点ODB、目标、SDC、库、RC模型与A81完整证明收据SHA逐项核对。共同工具镜像保持，8CPU与8工具线程一致；4GiB预约高于原同设计约1.43GB峰值，900秒窗口高于原139秒物理执行。

- 独立完整DRT/RCX：EF `run-a677de2c7fa24bb58672f31db35b37e1`，CPU627.66秒、峰值1406697472字节，6份原件按公开bundle/manifest逐一核SHA。
- 独立共同测量：EF `run-8251b2f9a2e1497e952a3e4430e8fdde`，CPU7.75秒、峰值338862080字节，9份原件核验通过。
- 七项核心PPA全部逐值相同；另核原始19个指标/单位/状态字段全部一致，包含setup/hold WS/TNS、电气计数和设计违反。DRC均0。
- 独立重放网表与A81已证明候选网表 **SHA完全相同**，不是只对上几项汇总数值。
- 原106输出/19384分区完整证明直接复用，证明收据SHA不变；本轮新增PDR=0。
- 三类DF scope、全部核心指标与结果匹配；独立安装Query正确回答setup WS=0.0086342ns、hold TNS=0，引用来源的完整字节/SHA核对通过。

私有Query核查第一次误将venv解释器软链接解析为系统Python，调用了旧包CLI；已更正为保留实际venv入口路径，原错误保留，没有修改Query接口、安装包或重跑EDA。此问题未影响前述物理/SDK结果。

## 可采用结果及真实收益

以下改善来自**已有优化分支**，本轮工作完成其证明、独立验收和采用，不把它说成新跑出的收益。

| 同条件指标 | ORFS参考 | 已采用分支 | 独立重放 |
|---|---:|---:|---:|
| power mW | 22.098418 | 21.887543 | 21.887543 |
| cell µm² | 29473.1 | 29465.4 | 29465.4 |
| core / die µm² | 56102.6 / 57254.9 | 同左 | 同左 |
| setup WS ps | −9.95204 | +8.63420 | +8.63420 |
| setup TNS ns | −0.210899 | 0 | 0 |
| hold WS ps | +84.1203 | +85.5288 | +85.5288 |
| hold TNS ns | 0 | 0 | 0 |
| slew / cap / fanout | 0 / 3 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| DRC | 0 | 0 | 0 |

功耗降低 **0.954257%**、cell降低 **0.026126%**，setup由违反变为闭合，余量增加 **18.58624ps**。原参考的时序/电容违反如实保留，未改时钟或约束来通过。

通过现有 `checked_validation` 和 `select` 完成采用；最终两单元修复仍标注为原生物理动作，不改写为新Goal Student或研究C++贡献。采用路径和校验收据位于本轮私有runtime，设计事实仍统一在原DF。

**独立物理重放不算第二次独立优化实验。**本轮关闭该分支的功能证明与最终采用阻断，没有因此宣布八组双次全部完成或Control优于固定调度。

## 文件清单与恢复

产品/测试改动仅上述两个文件；文档改动为本报告、`admin/STATUS.md`、A54总表、`TASKS.md`、`ARCHITECTURE.md`。26份用户文件和DF/DI在途修改保持，没有新服务/API/数据库或系统操作。

证据目录 `var/business/a82-ibex-nangate45-qualification-20261026/`：原失败与修复前测试、`validation-result.json`、`terminal-inspection.json`、`adoption.json`、Query与原件记录、`source-boundary-review.json`、`code-check.json`及`continuation.json`。

验证实验仍为 `var/business/a81-ibex-proof-resume-20261026/runtime/experiments/ibex/a81-ibex-nangate45-completed-proof-validation-r1/`，复用A81完整收据；旧超时与source结果保持。

后续回到Ariane/Nangate45最终cap64/power超限、Ariane/ASAP7闭合、GCD/Nangate45 500ps协作、八组双次，以及实际大库写入/checkpoint成本。先审原策略与诊断事实，再作具体有界动作；长专业搜索继续暂停，总目标保持进行中。
