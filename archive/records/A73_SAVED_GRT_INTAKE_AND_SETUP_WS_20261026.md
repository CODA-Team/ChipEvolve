# A73：保存 GRT 的公共交接核查与 setup WS 查询修复

基线根 `85ffd44`、Query `5291730`、Goal `33661a5`。按具体诊断、定点修复、短验证与 code-check 推进，工程验证通过，老板业务验收独立。正式长搜索保持暂停。

## 老板能看到的效果

Ariane/Nangate45 已修复的全局布线检查点，经现有公共 `resume` 入口恢复后，设计规模、布线引导、层范围和 setup/hold 时序值均保持。重复恢复复用同一 EF run/attempt，不重复计算。本轮没有复现这个入口丢失已有收益的问题，因此没有给交接代码增加补丁。

实际发现并修复的阻断是 Query 不识别 `setup WS?`：底层已有该指标，但意图解析只认识 WNS/TNS 和 hold WS。现在 Codex 可通过原查询入口读取正的 setup 最差余量，并比较两个运行的 WS，无需改问 WNS 或自己绕过 Query 读文件。

## 实际短验证及边界

父项为 A59 的 `run-e4d53b33ca2146af8b0acc656a22fe12`，使用其 EF 登记的 `post_repair.odb`、原 Nangate45 typical 库、6ns 双时钟及原目标。源 ODB/result/SDC/库/历史输入哈希核对，DF/DI 阶段来源核对通过。

隔离诊断调用真实公共恢复入口，只在 `Jobs.command` 的 qualification 提交接点捕获正常生成的路由脚本前缀，另用一个明确的预检任务运行，**在 detailed_route 前停止**。正常 qualification 任务没有提交，未写 result 或采用回执；诊断 hook 不进入产品。这个验证证明公共入口选择和加载的正确性，不等于整条最终资格已通过。

EF 实测 `run-f03854658ce2464b9544c408b7a356be` 成功，CPU55.93秒，峰值2847965184字节。加载与正式 DRT 前的准入状态同值：176184实例、189839网络、1667022条 guides、0条信号 detailed wires；信号层2–10，时钟层4–10。

| 同一 GRT 估算状态 | A59 保存值 | A73 公共入口恢复值 |
|---|---:|---:|
| setup WS (ps) | +284.388965 | +284.388965 |
| setup TNS (ns) | 0 | 0 |
| hold WS (ps) | +19.383717 | +19.383717 |
| hold TNS (ns) | 0 | 0 |
| slew / cap / fanout 违反 | 0 / 0 / 0 | 0 / 0 / 0 |

原生浮点值逐值相等，表内仅显示舍入值；两个时钟原生秒值均在6ns的数值精度内。WS可为正，不能以WNS代替正余量。这里没有新增功耗/面积测量，也没有完成详细布线、RCX、完整证明或最终采用。

独立恢复核对同一 run/attempt、成功执行回执与冻结文件哈希，确认没有新 EDA run，没有普通 qualification job。最初误用完整创建驱动再次运行，被已有实验目录检查拒绝；随后改用现有实验的公共 resume 验证。不把正确的创建保护当作产品缺陷，不新增 fallback。缓存恢复不是第二次独立优化。

## 修复文件、数据流与 code-check

- `query-agent/src/query_agent/application/planning.py`：意图分类复用已有指标名解析，加入独立 token 的 setup WS 识别；现有 CLI、SDK、数据结构与 provider 不变。
- `query-agent/tests/integration/test_hold_metric_queries.py`：使用正 setup WS、负 WNS 和独立 hold WS，新增4种问法、1项跨运行比较和4种误匹配反例。原有 hold、缺失数据和 TNS 用例保持。
- 本报告、A54、STATUS、TASKS：记录实际结论、未通过的资格及下一恢复点；manifest/gitlink只更新本次Query提交。

数据仍走保存 ODB → 公共 resume → EF 只读准入预检 → 现有 ORFS adapter → DF → 已安装 DI/Query → Codex。阶段 metadata 明确标记 intake preflight，没有最终 PPA。一个阶段快照的4次setup/hold WS/TNS查询通过；每次返回原值和ns单位，并沿引用取回完整 metadata 字节/SHA，5份EF捕获文件核对通过。

Query全228项回归通过，其中本次新增9项；最终针对集24项、根项目Query接点9项通过。根业务Python哈希与733项既有验证同源，其余未变功能复用既有结果，不将其写成本轮重新跑733项。Ruff、format、严格Pyright和3条import-linter约束通过；私有4脚本静态检查通过。代码检查期间曾报告测试列表元素未知类型、私有AST列表不变性，均只补实际类型标注后通过，没有关闭检查。

独立wheel内97份Python源码与工作树、安装目录逐字节一致；相对旧wheel只有`application/planning.py`变化，依赖检查通过。没有热替换旧Query环境、重启服务或改变容量。八份未来绑定保留A72的全部专业源码、PDK、目标、500ps政策及资源，只更换Query解释器和私有state路径；`long_search_ready=false`。

26份用户在途文件和根业务源码保持。未增加服务、公共API、数据库、跨源码导入或通用harness；专业算法没有修改。Git差异逐文件核对，业务数据留在var，不纳入源码提交。

## 恢复资料与下一项

证据目录 `var/business/a73-nangate45-grt-handoff-20261026/`：`input-admission.json`、`actual-preflight-execution.json`、`public-intake-verification.json`、`reentry-verification.json`、`fact-verification.json`、`prepared-bindings.json`、`code-check.json`和原始日志/安装包。恢复入口为该目录`runtime/experiments/ariane/a73-saved-GRT-intake-r1`，不存在最终result。

下一项针对这个已确认可加载的6ns分支，先核查已有资格配置、资源和输出约束，再决定有限的最终DRT/RCX验证；不先重跑专业搜索。Ariane/ASAP7 setup闭合、Ibex/Nangate45完整证明、GCD/Nangate45的500ps协作及八组两次合格优化仍未完成。没有证据证明Control优于固定调度，不增加该论文主张。
