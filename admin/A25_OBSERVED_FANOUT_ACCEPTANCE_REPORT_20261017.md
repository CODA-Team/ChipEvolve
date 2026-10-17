# A25：实际扇出违例与采用检查修正

JPEG 原完整搜索的首批 43 份成功布线中，候选 20、34、45 的原生最终报告各有 4 项最大扇出违例。三者 slew/cap 均为零，不能据此推断全部电气约束通过。候选 20 的原产物经公开 EF 物化、原库/原 SDC 共同测量及 DF/SDK 查询，均确认 4 项违例：`clkbuf_2_{0,1,2,3}_clk/Y` 各实际扇出 16，原限制为 10。没有修改候选或放宽约束。

原检查只判断十项业务目标，未把已知 fanout 违例列入失败。该真实候选同时存在 setup 违例，且本次单独测量不提供 DRC 验收，没有被采用；不能据此宣称历史曾误采用这份候选。修复前新增回归用其他条件均满足、功耗更低的候选隔离该缺陷，实际得到错误采用，测试结果 1 失败/2 通过。

## 改动、数据流与影响面

- `chip_evolve/selection.py`：现有 `violations` 对原生已观测的非零 fanout 计数返回 `max_fanout_violations`。比较、候选事实和采用共用此检查，不再把这类候选视为合格。函数签名、API、数据库及原十项目标/ID 保持；不虚构各设计统一的 fanout 数值限制。
- `admin/test_fanout_adoption.py`：验证降低功耗也不能以 fanout 违例覆盖合法保留分支；结果、目标和 incumbent 不被改写。零计数和旧结果缺失字段保持原事实。
- `TASKS.md` 与正式实验协议：登记实际发现、当前边界及新的等待队列；本报告保存可复核结论。

数据流仍为原专业产物 → EF 只读测量 → DF → SDK → Codex。修复复用现有事实和约束检查，没有新增评测服务或通用 harness。要改变已知违例的采用行为，检查 `selection.violations`；要改变测量内容，检查 `physical.measure`，不能仅改报告或目标 ID。

旧结果缺失 fanout 仍为未知。原十项检查通过仍不能被扩写为全部 SDC 条件通过；正式最终候选须绑定其实际物理产物、库/SDC 和完整电气证据。活跃 JPEG 前端加载的旧代码保持，后续旧格式候选需补核，不回写历史。

## 验证和成本

修复后 12 项针对检查、470 项根回归及 Ruff、格式、Pyright 通过。逐文件差异审查确认生产修改仅在现有约束函数增加五行；无跨模块私有数据访问或执行旁路。26 份用户文件哈希不变。

独立核验重新查原生报告哈希、原 ODB/SPEF、原目标/SDC、原生四行违例、公开 EF 和当前 SDK。三项托管任务均成功且各一次 attempt，八项事实逐值一致，原十项目标/ID 保持；已知托管 CPU 52.67 秒，测量和交付墙钟 60.48 秒。没有新原生 Codex 试次、优化搜索、源码构建、全布线、证明或采用；主 Codex/前端和独立服务成本不在托管 CPU 内，不能记零或作正式效率比。

主要证据在 `var/business/a25-formal-preparation-20261017/actual-jpeg-fanout-r1/`：`receipt.json` 保留修复前检查，`independent-acceptance.json` 核验修复后事实及失败原因，`root-regression.txt` 保存回归。首批 43 份原生报告与三份异常产物身份在 `var/business/a24-jpeg-pilot-20261016/flow-r4-observations/native-finish-electrical-evidence/`。这些是阶段采样，不能外推为完整 2×50 已验收。

## 连续工作状态

尚未派发任务的 r2 等待进程 717623 正常以 143 退出，原 spec/receipt/log 及 superseded 说明保留，没有取消 EDA。新 r3 队列 PID 1413959、工具句柄 79202，目录 `serial-calibration-continuation-r3-fanout-acceptance/`；47 份指纹与 dry-run 通过，五条命令、原专业算法/模型/参数域、顺序和预算一致。

队列仍等待完整 JPEG 收尾，然后安全启用 Gateway 更新并核验实际接单，再运行两个 JPEG Code 健康轮次和恢复完整参数域的 GCD 搜索。JPEG 原进程 379322/380965 持续运行，本次观察由首轮 42 份推进到 45 份布线完成；50 份到终态后再核对全部 CTS→route 实际消费。A24 未完整结束，A25 未冻结，A26–A28 未启动，团队公平优势和端到端效率收益尚未证明。
