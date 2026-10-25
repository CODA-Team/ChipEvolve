# A81：补齐 Ibex/Nangate45 完整功能证明，接回既有验收入口

基线根 `4ab1478`。本轮消除 Ibex/Nangate45“只有部分分区通过、缺完整功能证明”的阻断，保留旧超时和失败记录。没有产品源码、专业算法、模型目标、公共接口或生产服务修改；没有新优化搜索或PPA重测。工程检查通过，老板业务验收独立。

## 结果

新 EF `run-9dc85b1c4f964713b55ced8d26ff454b` **成功**。原完整证明的 **19,384 个分区全部 PASS**：

| 证明组成 | 数量 | 如何确认 |
|---|---:|---|
| 原已完成义务 | 5,333 | 原聚合日志中的通过集合与原生strategy PASS逐个匹配；状态复制后SHA相同，未重新求解 |
| 本次补齐义务 | 14,051 | 原样SBY/RTLIL/SV输入，原生PDR实际执行；逐项strategy及SBY状态、PASS日志与输入SHA核验 |
| 完整原生汇总 | 19,384 | 保持原完整Makefile、summary目标及partition.list，原EQY runner/final产生整体PASS；没有手工写PASS |
| 顶层输出覆盖 | 106 bits | 当前原有 `proof_receipt` 对完整列表/每项状态核验通过，与冻结gold模型输出位数一致 |

原 `run-010c1023e6514e99911eb866bdcbe4ae` 仍为 timed_out，原目录/配置/日志哈希保持。A58八项抽查仍按抽查记录保留，没有将它们冒充整体通过。

## 怎样修复这个具体阻断

实际共同镜像中的EQY v0.68有原生继续入口；源码核查表明仍会进入源模型与分区前处理。此次直接复用已冻结的生成结果，调用**安装版EQY原Make runner、状态汇总与final逻辑**，不重做模型归一化、匹配或分区。

新私有工作目录位于本账号可写的临时盘。所有PDR与子进程均在EF监督树内；结束后保留完整所需证明归档与原件，清理的只是本轮临时目录。没有将生产数据库搬到临时盘、修改系统目录或提权。

SBY动作文件、对应`.sv/.il`逐字节复制并校验，保留原 `abc pdr`、xprop、multiclock、clk2fflogic、Liberty、Z3与所有原输出/状态/实际driver-pin切点。显式SBY工具包装只绑定同一已核验Yosys wrapper与ABC，不改命题、策略或假设。

先运行原生续证小样本：EF `run-020a72cd776e46f69e57aca3ab0d2bf7`，8义务中复用1、真实补齐7，整体1.528秒。确认原生Make不重跑已有状态、工具与汇总正确后，完整续证使用12CPU/16GiB/1200秒有界预约。复制66.825秒，复制/求解/状态采集共376.284秒，另计归档及EF收尾；实际CPU3582.03秒、峰值776695808字节、53进程。不是新专业搜索，也不把不同资源与复用条件下的耗时当作公平加速比例。

首次私有样本因容器Python不支持`hashlib.file_digest`而在输入核验处失败，尚未运行PDR。改为兼容该实际版本的标准流式SHA计算，新副本验证通过；失败 EF `run-fb541237b71144e388f9997b36d9489a`与原件保持，未改工具镜像或用户环境。一次范围过大的只读文件搜索已停止，仅停止本轮自己启动的搜索进程。

## 证明已经能被业务层消费

完整证明的6份EF捕获文件、129MiB级证明归档、全部19,384状态、14,051份新SBY日志及对应输入哈希核验通过；原工具源码捕获另6份通过。原完整partition.list SHA一致，不减少端口、义务或未知项。

在新验证实验 `a81-ibex-nangate45-completed-proof-validation-r1/logic/logical-equivalence.json` 写入原有契约的证明收据，绑定：

- 精确的ORFS参考与最终two-cell修复结果；两网表、Liberty、原模型JSON、原proof配置、完整归档与核查原件SHA。
- 成功EF证据生产者、106输出、19,384完整分区、未证明点0；标明复用5,333及新增14,051，而不是把全部说成新计算。
- 原时钟、state/cut匹配政策与原失败父任务。

现有 `validation.completed_proof` 实际消费此收据通过，没有新增入口或证明框架。后续正常 `validate()` 可复用，不再启动PDR。

待验收分支的当前DF三scope/七项核心指标及原约束也已核对：

| 同条件已有指标 | ORFS参考 | 待最终验收分支 |
|---|---:|---:|
| power mW | 22.098418 | 21.887543 |
| cell µm² | 29473.1 | 29465.4 |
| setup WS ps | −9.95204 | +8.63420 |
| setup TNS ns | −0.210899 | 0 |
| hold WS ps / TNS ns | +84.1203 / 0 | +85.5288 / 0 |
| slew / cap / fanout | 0 / 3 / 0 | 0 / 0 / 0 |

power −0.954257%、cell −0.026126%，setup从违反变为闭合；core/die保持。上述是**既有物理结果**，不是本轮新PPA。原参考本身时序/电容不合法，表中明确保留。最终两单元修复属于原生物理动作，不能改写成新Goal Student或研究C++收益。

完整证明已通过不等于最终采用：**独立DRT/RCX同值重放、重放DF核验和采用尚未在本轮执行**。下一项沿已准备的验证key推进这些收尾，不重算证明。

## code-check与接续

五份私有脚本Ruff、格式、Pyright通过；native sample/full公开原件核验通过。根产品源码相对`4ab1478`保持，复用同源742项回归；26份用户文件、DF/DI在途代码及旧实验保持，没有新增服务/API/数据库。业务验证证明收据已通过，老板验收独立。

证据目录 `var/business/a81-ibex-proof-resume-20261026/`：`sample-evidence-verification.json`、`full-evidence-verification.json`、`business-proof-verification.json`、`candidate-current-DF-facts.json`、`code-check.json`和`continuation.json`。Ariane最终电气/功耗、ASAP7闭合、500ps协作、八组双次及大库实际写入成本仍在总目标内。
