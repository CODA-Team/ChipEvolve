# A91：ECO跨PDK缓冲引脚与指定负载身份修复

根基线 `b771d38`，ECO基线 `de19cc4`，修复提交 `17b0407`。**两个实际动作阻断已复现、修复并通过双PDK短验证。** 没有启动专业长搜索、模型调用或布局布线，没有新增优化PPA或采用结果。老板业务验收独立。

## 业务问题与真实复现

库能加载不等于每个ECO动作都能正确运行。原 `eco_insert_buffer`／`eco_remove_buffer` 把引脚固定为 `A/Y`；Nangate45的 `BUF_X2` 实际是 `A/Z`。更严重的是，旧插入动作找不到Y时，OpenROAD只发警告，过程仍返回成功，指定负载已经移动到新网络，但buffer的Z输出没有连接。

本轮在A84实际最终Ariane检查点上，用60个DF已核实电容驱动寻找真实负载，得到驱动 `max_cap32020/Z`（原master为 `CLKBUF_X1`），负载 `issue_stage_i.i_issue_read_operands/pc_o[2]$_DFF_PN0_/D`，网络 `net32019`。该负载的STA显示名与OpenDB原始名的括号转义不同。

| 同一真实对象上的动作 | 旧代码 | 修复后 |
|---|---|---|
| 按STA显示名指定一个负载插buffer | 报“no sinks to move”，没有实际动作 | 正确选择该负载 |
| 原始名指定负载、使用BUF_X2 | 返回成功，但输出Z未连接，负载在无驱动新网 | A连原网、Z连新网和指定负载 |
| 删除该buffer | 固定Y无法寻址Nangate45输出 | 原负载接回原网、实例/网络数量恢复 |
| ASAP7原BUF的A/Y插入和删除 | 原有能力 | 实际GCD检查点连接正确、删除后拓扑恢复 |

旧代码的静默断连在一次性内存副本内复现，没有写回ODB或产生优化候选。历史结果和已验证产物保持；不能用本轮修复替旧失败补通过，也不能将其作为Ariane电气已经清零的证据。

## 修改及影响面

仅修改模块两个文件：

- `OpenROAD_utils/eco_procs.tcl`：新增私有master引脚解析，排除电源/地后使用唯一信号输入和输出；指定负载通过已有原生实例桥接获得精确OpenDB名称。只更新插入/删除buffer的相应接点，保留动作签名、负载选择、放置和重连流程。
- `src/test_buffer_technology_identity.py`：七项回归，覆盖Nangate插入/删除、显示名负载、ASAP7插入/删除、歧义负载不变更网络、不适用master在修改前拒绝。

引脚不是按PDK字符串猜测，而是从实际已加载master取得；没有新增优化动作、专业算法、公共API或兼容服务。源码逐过程比较确认只有 `eco_insert_buffer`／`eco_remove_buffer` 的现有过程体改变，其余Tcl过程及所有原签名相同；`main_orch.py`、`LLM_call.py`、`context_builder.py`保持，原评分、时序筛选、最佳选择和回溯未变。

## 针对性短验证与code-check

| 证据 | 结果 |
|---|---|
| 先写的五项回归对旧源码 | 3失败／2通过 |
| 修复后七项新回归及ECO全回归 | **63通过／2子项通过** |
| 根ECO/任务边界/论文接力接点 | **48通过** |
| 新测试、三个私有驱动静态检查 | lint／格式／Pyright通过 |
| 两PDK实际插入和删除 | 引脚连接、所选负载、对象数量及删除后原连接核对通过 |
| EF成功原件 | 3个包／6份capture逐SHA通过 |
| DF实际身份 | 原最终scope下驱动/负载、原ODB SHA核对通过；ASAP7源三视图与指标经DI核验 |
| 正式冻结入口 | 新冻结的helper与正式模块同SHA |

实际EF为：旧缺陷复现 `run-fd048e08b031470d8f94c47998d1ac43`，Nangate45修后 `run-a182e5fd999b4057911c1e451336d1ae`，ASAP7兼容 `run-db7ea605e5494351afc858309e8f968a`。均由EF监督原生OpenROAD，2工具线程与2CPU一致；没有宿主EDA或新服务。三次CPU用量约1.10／1.02／3.08秒，峰值内存约812／733／364MB。这是动作验证成本，不是优化实验成本或加速比。

首次私有探针把 `get_name(pin)` 误用作完整引脚名，并错误预期旧断连会报错；失败run `run-b6c498d458804bc1b9ceaf1eb6dd37fc`和脚本保持。r2使用原生 `get_full_name`，直接断言实际Z未连接，才作为正式旧缺陷证据。核查脚本初次对原驱动master的错误猜测也已改为核对原DF清单中的CLKBUF_X1；没有修改原数据来满足断言。

根产品Python与A82同哈希，复用754项根全回归；本轮模块回归与48项根接点确实重跑。26份用户保护文件、generic_agent.py及DF/DI在途工作保持。收尾EF五种活动状态均为空，专业模块工作树干净。模块只推ChipEvolve的 `modules/timing-eco-agent`，第三方origin未写入。

证据目录 `var/business/a91-eco-buffer-technology-identity-20261026/`：原/新helper、旧失败与修后日志、双PDK EF包、`actual-target-DF-identities.json`、`source-boundary-review.json`、`terminal-verification.json`、门禁日志、`code-check.json`、`continuation.json`。

根仓库只更新ECO gitlink、manifest对应commit/tree、本报告、STATUS、A54和TASKS。修改今后的buffer引脚/指定负载寻址查模块helper；修改ECO原评分或时序目标不属于这次修复。Ariane/Nangate45电气资格、Ariane/ASAP7时序、DF大对象写入延迟与八组双次仍未关闭，长搜索继续暂停；下一项先核原动作在实际电气网络上的可用上下文和调用，不重复A85的同清单路由尝试。
