# Agentic EDA 施工状态

更新日期：2026-10-10。用户已确认规划并授权连续施工。P0 已完成；P1 首次实验因整批布线时限不足失败，retry1 两轮完整结束但因参数物理消费缺失未通过验收。接线修复已通过真实 OpenROAD API 验证，retry2 使用独立冻结源码正在执行完整两轮三候选实验。P2 可靠导入和列表修复已提交，默认盘 HTTP 取消修复已通过复测；正式阶段接入等待修复后 P1。P3 至 P6 待前置验收。

## 当前工作

已封存本机 A2 上游提交、全部已跟踪修改、未跟踪源码、工具与安装依赖。正式 Flow 基线提交为 `a4f72ce51de6a4565ad85333b2fe6cbe1936aecd`，独立环境检查通过，27 项 Flow 回归通过。

首次实验的失败回执、原始日志和 [验收记录](/home/wjyuan/projects/eda-development/var/flow-agent/p1-native-20261010/p1-acceptance.json) 均已保留。第一轮基准候选完成全流程，但布线整批 20 分钟用尽，最终有效候选为 1/3，原生关卡要求至少 2；退出码 1，第二轮未运行，源码 hash 未变。原目录不作为施工目录。

完整重试使用同一封存源码、同一算法与模型条件，将每候选线程从 2 调到 8、整批阶段时限从 20 分钟调到 90 分钟；两轮三候选、物理并发一、三小时总预算保持一致。当前命令、进程和终态见 [重试 receipt](/home/wjyuan/projects/eda-development/var/flow-agent/p1-native-20261010-retry1/receipt.json)，输出见同目录 `campaign.log`。封存证据仍引用首次目录 `baseline/manifest.json`。

Data Foundation 已增加指定产物的持久化导入回执、失败记录与重试、批量翻页，并通过 375 项检查，包括真实 HTTP 并发重复导入。证据为运行目录 `data-foundation-check-http.log`。未改动旧数据库或服务。

EF 新状态的默认盘/内存盘配对测量已完成。150 条记录写入分别约 77.53 秒与 0.016 秒；无并发写入时列表查询约 0.5 至 3.6 毫秒。新原生 OpenROAD 取消在两个存储条件下各测三次，进程消失与本地终态均低于五秒；这不是此前失败场景的 HTTP 复测，不据此关闭历史取消问题。

EF 列表改造已通过完整检查：366 passed，1 skipped；提交 `786bab5`。同规模默认盘筛选查询由 153 次 SQL 减到一次，测得约 3.35 毫秒降至 0.154 毫秒。另一次记录写入耗时变化受机器负载影响，不能归因于只读列表改造。

DF 可靠导入提交为 `95affc8`。已有几何查询和 pending STA 投影等用户修改保留，未纳入本次提交；当前检查覆盖包含这些既有修改的工作树，其补丁和安装状态存于运行目录。Flow 开发规则提交为 `20755ce`，本次物理实验仍固定使用 `a4f72ce` 源码副本。

## P1 当前已核实的运行事实

首次失败实验中，第一轮三候选的布局与 CTS 均成功。两次真实模型调用共输入 41,304、输出 244 token，CTS 和布线参数实际进入配置；run 2 继承 run 3 布局，run 3 继承 run 2 CTS。基准最终 CP0=0.792 ns，TNS=-4.36 ns，功耗 0.4 W；其 ODB/DEF/V/SPEF/SDC/GDS 均保留。没有完整第二轮或收益证据，不能用这次部分结果代替重试验收。

原生备份只保存 SDC，下一轮会清理上一轮物理产物。独立 `capture_native_iterations.py --run-root ...` 在原生备份边界采集每轮最终 ODB/DEF/V/SPEF/SDC/GDS 到运行根目录 `iteration-results`，逐文件校验 hash；没有修改运行中的算法源码。重试 supervisor 自动启动采集器并记录其身份与退出码。

默认盘真实 HTTP/worker 路径已复现取消延迟：三次接口终态耗时约 26.93、27.11、14.23 秒，进程消失约 1.77、9.37、6.05 秒。改用 SQLite WAL、保留 FULL 同步强度后，同一脚本三次终态约 2.75、1.49、0.14 秒，原始进程树消失均小于一秒。证据在首次目录 `http-cancel-disk.json`、`http-cancel-wal.json`；独立内存盘对照也保留。完整 EF 检查 368 passed、1 skipped，mypy 41 文件通过，见 `ef-check-wal.log`。这验证了真实 OpenROAD 初始化与子进程取消；P2 仍需真实设计阶段验收，不把等待脚本当作完整物理任务。

EF WAL 修复提交为 `d0302c1`。真实 HTTP 列表验收已提交 150 条任务，以 API-only 模式查询三页各 50 条，无重复或遗漏，第四页和不存在项目均为空，见首次目录 `http-listing.json`。这是分页验收，不是物理设计实验。写入耗时受当时负载影响，不据此归因总体性能收益。

Toolkits 的阶段接口已准备并通过 48 项检查；实际 AES 检查点在原生 Make 上的外层和叶子 dry-run 均只计划 CTS，不重跑上游。证据为重试目录 `toolkits-stage-preparation-check.log` 和 `var/flow-agent/p2-interface-preparation/cts-inputs/dry-run-receipt.json`。没有改动 A2 dispatch，没有执行正式 EF 物理阶段，也没有完成 P2 业务验收。

完整重试第一轮已完成 3/3 最终物理流程；独立采集器保存 18 个最终产物。基准 TNS=-4.36 ns、power=0.4 W，另两个候选均为 TNS=-8.16 ns、power=0.38 W；首轮没有时序改善。第二轮已开始真实布局。跨轮七次模型响应已逐项审阅：模型的 48% 利用率、0.18 密度调整提案通过选池并进入第二个候选；三条 CSV 事件、输入 hash 与生成配置相符。证据为重试目录 `model-decision-review.json` 和 `decision-review-evidence/`。原生交互式 GPR 分支因少于四个历史样本跳过，候选预测在少量样本下平坦；不能宣称该分支实测通过。最终 P1 验收仍等待第二轮及正常结束。

P2 验收入口已补齐真实 AES 布线取消与实体数据导入：阶段链通过后，用原生 CTS 产物启动真实全局布线，在并发列表读取下核对原始进程身份、五秒取消和资源归还；再通过 Toolkit 从该次最终 ODB 导出快照，用新的 DF 状态验证并发重复导入与服务重启后的回执。此入口尚未运行，不将准备工作计作业务能力完成。

## 恢复入口

retry1 于 07:31 UTC 正常结束：退出码 0、source_changed=[]、capture_exit_code=0，两轮各 18 个最终物理产物。17 次真实模型调用，309,360 token。最终基准和可行最优 TNS=-4.36 ns、power=0.4 W；第二轮第三候选 TNS=-3.15 ns 但 power=0.462 W，超功耗，不计改善。`p1-acceptance.json` 仅参数物理消费及其证据门槛不通过，因此没有启动 P2。

真实接口验证证据为 `var/flow-agent/p1-routing-probe-20261010/receipt.json`：加载本次真实 AES ODB，四次 OpenROAD capacity setter 均返回 0，两个阶段分别使用独立提案。新冻结基线为 `var/flow-agent/p1-routing-baseline-20261010`，修复实验为 `var/flow-agent/p1-native-20261010-retry2`；supervisor 使用同一显式 baseline。首个真实 floorplan 日志已出现 `scope=floorplan pin=0.5 above=0.25`，其余阶段与最终完整验收仍待运行。

`capture_native_decisions.py` 正在等待第二轮配置生成边界，保存模型输入批次、三份配置/SDC 与 lifecycle 到新实验 `decision-review-evidence`，供人工核实；不会自动签署模型决策审阅。修复实验结束并采集完后运行 `review_native_consumption.py` 核对两轮实际工具日志与继承配置，再审阅真实模型决策、完成 P1 审计、推进 P2。

接入准备已进一步覆盖真实评价回流：Toolkits 提交 `190f5e7` 在完整 CP0 评价成功后输出 `a2-evaluation.json`，包含实际 signed TNS/WNS、power、单位、固定时钟与库条件、SPEF 模式及源日志 hash；缺功耗等失败不输出成功反馈。48 项 Toolkits 检查通过。P2 入口会通过既有 ORFS metadata adapter 生成可导入快照，使用独立新 DF 状态，并以 Data Interface 自己的已安装 SDK 验证重启前后相同指标和源字节。相关脚本已通过 lint/compile/CLI 检查，尚未作为真实接入验收执行，不据此标记 P2/P3 完成。

Toolkits `83301d2` 与 DF `077b47e` 进一步保存实际 evaluator 的来源和评价条件到指标行，避免 CP0 评价被误标为常规 ORFS 阶段报告。49 项 Toolkits、376 项 DF 检查通过；DF 原有六项用户修改保留，未纳入提交。SDK 验收要求指标条件与实际评价 metadata 完全一致，并且证据解析到注册的原始 metadata artifact 与 hash。首次新增 fixture 检查暴露证据规范化及缺失 stage，已修正 fixture，原失败日志均保留于 `p2-interface-preparation/feedback-context-data-check*.log`；不是放宽业务验收。

最新物理消费审计在重试目录 `parameter-consumption-review.json`：生成的 FLOORPLAN_PIN/ABOVE 与 PIN/ABOVE 参数未被 Nangate45 默认脚本消费，默认实际容量固定为 0.5/0.25；CTS 两项参数确实被消费。正式 Flow 提交 `57be217` 补充独立 floorplan 和 post-CTS routing hook，保持原平台基准容量不变，29 项检查通过。Tcl stub 检查只证明参数接线，真实工具 setter 与修复后的两轮物理实验仍待验证。不得改动当前运行副本或从不同源码实验拼接验收。

修复后的源码基线通过 `admin/freeze_native_revision.py` 冻结原始归档与 Git delta；启动新实验时 `prepare` 和 `supervise` 均显式指定新 `--baseline`。当前实验的续接监督器只有 P1 审计通过才启动 P2，因消费门槛不通过，预期不会启动正式接入。

读取 [施工目标](PROJECT_CONTRACT.md)、[版本与接入关系](INTEGRATION_MAP.md) 和 [运行手册](RUNBOOK.md)，再查看运行 receipt 与原生 campaign 状态。不得仅凭聊天内容把阶段标记完成。

第一关仍待验收：同一实验的真实模型调用、多轮物理流程与正常结束共同成立后才推进正式接入。恢复时先读实时 receipt、原生账本与 capture.log；本页是索引，不能覆盖运行记录的最新状态。
