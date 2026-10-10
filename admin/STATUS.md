# Agentic EDA 施工状态

更新日期：2026-10-10。用户已确认规划并授权连续施工。P0 已完成；P1 首次实验因整批布线时限不足失败，已启动独立完整重试。P2 可靠导入和列表修复已提交，默认盘 HTTP 取消修复已通过复测；正式阶段接入等待 P1。P3 至 P6 待前置验收。

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

## 恢复入口

读取 [施工目标](PROJECT_CONTRACT.md)、[版本与接入关系](INTEGRATION_MAP.md) 和 [运行手册](RUNBOOK.md)，再查看运行 receipt 与原生 campaign 状态。不得仅凭聊天内容把阶段标记完成。

第一关仍待验收：同一实验的真实模型调用、多轮物理流程与正常结束共同成立后才推进正式接入。恢复时先读实时 receipt、原生账本与 capture.log；本页是索引，不能覆盖运行记录的最新状态。
