# A61：ECO 模型上下文恢复全设计 TNS，并标明路径子集范围

基线根 `0f5c4ff`、ECO `163120b`。本轮针对 Ariane/ASAP7 时序失败继续查实际输入，发现并修复专业模型上下文的统计范围错误。仅修改 ECO 的 `src/main_orch.py` 和已有 `src/test_native_probe.py`；原路径表、专业动作、评分、最佳选择及回溯规则保持。长模型/优化搜索仍暂停。ECO检查点 `04a17a8` 已发布到 ChipEvolve 的 `modules/timing-eco-agent`，根gitlink/manifest固定同一源码。

## 真实问题与验证数字

原 `context_builder` 将截断 timing report 中路径 slack 之和写成 `tns_ps`，并将所报路径数写成 `num_violating_endpoints`。控制器实际只请求有限路径，模型看到的值因此不能代表全设计。

使用精确原 Ariane ODB、SPEF、SDC、21库，在 EF 内进行只读原生命令核查：

| 同一次原生分析 | 原值 | 模型应该如何理解 |
|---|---:|---|
| 全设计 `report_wns` | −288.838 ps | 当前全设计 WNS |
| 全设计 `report_tns` | −127167.508 ps | 当前全设计 TNS，约−127.168ns |
| 原50条报告的 slack 之和 | −13813.72 ps | 仅报告子集，约−13.814ns |
| 原报告路径数 | 50 | 已报路径数；全设计违反端点数尚未由该报告给出 |

这是同一份设计的统计范围差异，不是物理收益。旧 DF 的 −127.168ns 为原显示精度；本次 −127.167508ns 增加了精度，没有优化设计。

历史八轮末尾同样存在上下文子集与工具总量不同的情况。原生控制器已经有独立 WNS/TNS 文件，问题在交给模型时未使用它。原评分和最终选择使用独立测量，本轮没有把它们改成子集或新增目标。

另核实了 `reg2reg` 警告：当前输入只含 `core_clock`/asynchronous 等组，工具对未知组警告后仍返回实际路径。旧真实报告和本次都得到路径，不能据此声称 ECO 没看到关键路径；本轮不以这个警告为由修改专业路径策略。

## 两个文件做了什么

| 文件 | 职责与影响 |
|---|---|
| `timing-eco-agent/src/main_orch.py` | 模型请求前，在同一个 EF 监管的 OpenROAD 会话刷新全局 WNS/TNS并等待完成；调用模型前更新 JSON/TOON 的设计 TNS，并标注报告子集。 |
| `timing-eco-agent/src/test_native_probe.py` | 验证设计/子集区分、路径不变、重试幂等、缺全局观测时的范围、真实模型调用接点，以及刷新先于模型调用。 |

`tns_ps` 取当前原生全设计值，`tns_scope=design`；原子集另存 `reported_paths_tns_ps`，`num_violating_endpoints_scope=reported_paths`。缺少原生测量时全局值为 unknown/空，子集仍单独保留。其他原字段及完整 TOON 路径表保持。

恢复分支源码还显示，崩溃重启或回溯后汇总文件可能残留旧值。新增的请求前刷新直接读取当前会话，保证这里交给模型的 TNS来自现态；它不改变恢复/晋升策略，也不作为所有恢复分支已完成端到端验收的声明。

没有修改 `context_builder` 或 `LLM_call` 的专业解析、路径选择、提示词策略、Student/Teacher、工具动作或评分；没有新服务、公共协议、数据库、通用 harness、依赖安装或跨项目源码导入。

## 短验证、数据回流与 code-check

- 新增前四项用例在旧源码失败（新接点未实现）；实现后加上新鲜度顺序检查，共9项针对用例通过。ECO完整 **42 passed / 2 subtests passed**，根业务 **712 passed**。
- 两个修改文件 Ruff 通过；main仅对修改区域格式检查，测试文件整文件格式通过；Pyright **0 errors / 0 warnings**。
- AST差异仅 `run_llm` 和 `run_loop` 增加接点，以及两个小内部函数；其他所有原函数/类 AST相同，评分与选择函数相同。
- 原生 EF `run-ab252ad381bb47ce81c4b9402775116a` 成功，约44.73秒墙钟、CPU54.91秒、峰值约2.36GiB。没有动作、布局布线、模型调用或新优化PPA。四份原生捕获原件及源输入 SHA通过。
- 原有 builder 对真实50路径报告构造上下文，再调用修复后的实际函数，设计TNS正确、子集保存，路径JSON和TOON表主体保持。原 `build_prompt` 构造函数实际包含这些新字段，模型调用为零。
- 通过既有 ORFS metadata适配器→EF→DF→DI回流；export `run-5f94585b3b4b4b14b281c408e96b656e`，snapshot `a61-run-ab252ad381bb47ce81c4b9402775116a-native-context`。Query按精确范围回答 TNS **−127167.508ps**，引用原始字节取回并核 SHA；单位保持原 ps。
- 私有发布脚本首次断言错误地要求 Query转换为ns，已按实际合法ps修正；复用已完成 export及原导入收据，未重做原生分析。早期测试/工具路径错误保留为核查过程，最终门禁单独核对真实退出码和日志。
- 26个用户保护文件、原源result/ODB/SDC/SPEF与DF/DI WIP保持，EF活动队列为零。旧专业会话副本不热改，新会话应冻结本次源码。

证据目录 `var/business/a61-ariane-asap7-timing-diagnosis-20261025/`。关键文件为 `actual-context-verification.json`、`source-boundary-review.json`、`isolated-prompt/next-prompt.txt`、`facts-receipt.json`、`final-functional-verification.json`及门禁日志。私有驱动/核查也做lint、格式和类型检查。

## 对业务的作用与剩余工作

ECO模型能同时看到全设计欠账和局部报告范围，原有有限上下文仍然紧凑。这修正决策输入，不证明新ECO轮次有收益，更不把只读重测算作独立优化重复。

当前最差原路径为存储队列寄存器到 AXI 输出。DI 的该路径报告增量是完整的：排除时钟及首个数据点前的时间后，698.4ps中单元增量648.7ps、连线49.7ps。对象关联部分仍为partial，不能把实例/宏聚合数量当完整事实。此证据支持下一步优先检查已有 sizing/VT 时序策略及实际候选；不改变原900ps条件。

本轮尚未修复 Ariane/ASAP7 的物理 setup/slew债，未运行新八轮ECO或完整DRT/RCX/PPA/证明。Ariane/Nangate45最终资格、Ibex/Nangate45完整证明、GCD500ps协作和八组双次仍未完成，总目标保持进行。
