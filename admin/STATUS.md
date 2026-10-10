# Agentic EDA 施工状态

更新日期：2026-10-10。用户已确认规划并授权施工。P0 已完成，P1 已启动独立原生实验；P2 的可靠导入修复正在验证，正式阶段接入等待 P1。P3 至 P6 待前置验收。

## 当前工作

已封存本机 A2 上游提交、全部已跟踪修改、未跟踪源码、工具与安装依赖。正式 Flow 基线提交为 `a4f72ce51de6a4565ad85333b2fe6cbe1936aecd`，独立环境检查通过，27 项 Flow 回归通过。

真实两轮三候选实验已启动，命令、进程身份和终态见 [receipt](/home/wjyuan/projects/eda-development/var/flow-agent/p1-native-20261010/receipt.json)，输出见 [campaign.log](/home/wjyuan/projects/eda-development/var/flow-agent/p1-native-20261010/campaign.log)。封存证据见同目录 `baseline/manifest.json`。原目录不作为施工目录。

Data Foundation 已增加指定产物的持久化导入回执、失败记录与重试、批量翻页，并通过 375 项检查，包括真实 HTTP 并发重复导入。证据为运行目录 `data-foundation-check-http.log`。未改动旧数据库或服务。

EF 新状态的默认盘/内存盘配对测量已完成。150 条记录写入分别约 77.53 秒与 0.016 秒；无并发写入时列表查询约 0.5 至 3.6 毫秒。新原生 OpenROAD 取消在两个存储条件下各测三次，进程消失与本地终态均低于五秒；这不是此前失败场景的 HTTP 复测，不据此关闭历史取消问题。列表 SQL 分页改造正在检查，减少无关记录展开和计数查询。

EF 列表改造已通过完整检查：366 passed，1 skipped；提交 `786bab5`。同规模默认盘筛选查询由 153 次 SQL 减到一次，测得约 3.35 毫秒降至 0.154 毫秒。另一次记录写入耗时变化受机器负载影响，不能归因于只读列表改造。

DF 可靠导入提交为 `95affc8`。已有几何查询和 pending STA 投影等用户修改保留，未纳入本次提交；当前检查覆盖包含这些既有修改的工作树，其补丁和安装状态存于运行目录。Flow 开发规则提交为 `20755ce`，本次物理实验仍固定使用 `a4f72ce` 源码副本。

## P1 当前已核实的运行事实

第一轮三候选的布局与 CTS 均成功。已完成真实模型调用，其 CTS 参数实际进入 run 2 与 run 3 的配置；run 2 继承 run 3 的布局检查点，来源记录为 `llm`。布线、第二轮、预测排序和最终正常退出仍待验收。

原生备份只保存 SDC，下一轮会清理上一轮物理产物。独立 `capture_native_iterations.py` 在原生备份边界采集每轮最终 ODB/DEF/V/SPEF/SDC/GDS 到运行根目录 `iteration-results`，逐文件校验 hash；没有修改运行中的算法源码。采集日志为 `capture.log`。

## 恢复入口

读取 [施工目标](PROJECT_CONTRACT.md)、[版本与接入关系](INTEGRATION_MAP.md) 和 [运行手册](RUNBOOK.md)，再查看运行 receipt 与原生 campaign 状态。不得仅凭聊天内容把阶段标记完成。

第一关仍待验收：同一实验的真实模型调用、多轮物理流程与正常结束共同成立后才推进正式接入。
