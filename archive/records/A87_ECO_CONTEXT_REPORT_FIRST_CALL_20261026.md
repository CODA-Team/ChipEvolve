# A87：修复 ECO 上下文报告首次时间格式化失败

根基线 `6d12b06`、ECO 基线 `ff8d13c`。**实际故障复现，三处修复及短验证通过。** 模块修复 `de19cc4` 供新会话使用；旧会话、历史结果、专业策略和业务约束保持。

## 业务问题与修改

主循环在初始、迭代及回溯后调用路径邻居、扇出导出；模型也可请求带文件输出的扇出排序。三个报告头仍用 `clock format [clock seconds]`，首次格式化可能报 `invalid command name ":Tcl/Localtime"`，正文缺失。A79修的是过程QoR时间戳，未覆盖这里。

只改模块两个文件：`OpenROAD_utils/eco_procs.tcl` 的三个报告注释头改用epoch秒；`src/test_context_report_timestamp.py` 增加六个回归，覆盖三个导出在缺少格式化能力时仍保留正文、三个真实文件写入失败仍报错。旧Tcl仅三处字符串替换，其余字节完全相同，函数签名、筛选/排序、评分、动作和回溯保持。

数据流保持：EF监督的原生OpenROAD → 专业报告 → 原 `ContextBuilderV5` → 原提示与分析。无新服务、公共API、数据库、跨模块源码访问或模型harness。要改注释查三个Tcl过程；要改理解规则查原ContextBuilder，本轮未改。

## 真实验证

相同A84 Ariane/Nangate45最终ODB/SPEF、6ns SDC、typical库及共同OpenROAD，仅做只读诊断。

| 记录 | EF run | 结果 |
|---|---|---|
| 原实现 | `run-6c7f2547038240a1a2fcf3d76bea2603` | 首rank报:Tcl/Localtime、文件0字节；同进程后续siblings/fanout成功 |
| 修复 | `run-b72f8a12873f464eab4ceab70bd80d06` | 三导出全部成功，原成功的两份报告除注释外正文逐行相同 |

不能说“三次原生调用都失败”：本次只有首次失败，之后可格式化，存在调用顺序依赖；三项受限时钟回归分别覆盖同类风险。原EF外层succeeded表示诊断脚本完成，内部失败事实保持。任务各1CPU/4GiB，原预算180秒，修复按实测给360秒；CPU130.39/134.33秒、峰值约2.04GB，无搜索或修改设计。

原ContextBuilder在ECO自有环境实际消费 **91个路径邻居实例、13个高扇出驱动、目标5个负载**。原两份成功报告正文同值，新rank完整；不以路径子集slack代替设计汇总。报告前后共四次原生时序精确相同：setup WS **+0.2884936815540547ns**、setup TNS **0**、hold WS **+0.047782001929789715ns**、hold TNS **0**。全部输入、10份捕获输出和日志注册SHA核验通过。没有新优化网表、最终PPA、模型调用或采用。

## code-check 与发布

旧实现新回归3失败/3通过，修复后 **6通过**；ECO **56通过/2子项通过**，根业务接点 **57通过**。新测试及两份私有脚本lint/格式/Pyright通过；测试使用含pytest的测试解释器，驱动使用客户端解释器，不往运行环境安装测试包。初次测试错误要求单空格，而原报告列间为双空格，已改成核列值且继续要求正文逐行同值；原失败日志保持，没有改产品格式迁就测试。

公共根Python未改，复用A82同源 **754项根回归**，非本轮重跑。差异/边界/消费者实测通过；26用户保护文件、generic_agent.py及DF/DI WIP保持。模块发布至ChipEvolve的 `modules/timing-eco-agent`，不推第三方origin，保留来源署名。根只更新gitlink、manifest的ECO commit/tree、本报告、STATUS、A54和TASKS。

证据：`var/business/a87-eco-context-report-timestamps-20261026/`，含原生记录/报告、旧失败与最终回归日志、消费者结果、`native-evidence-verification.json`、`source-boundary-review.json`、`code-check.json`、`continuation.json`。工程检查通过，老板业务验收独立。

本次关闭ECO上下文首次导出阻断。Ariane剩余电气/时序、GCD/Nangate45完整协作、八组两次合格优化仍未完成。下一项先只读定位生产DF实际解析/索引写入成本与用户WIP边界，不重复盲调已有cache或跑大EDA实验。
