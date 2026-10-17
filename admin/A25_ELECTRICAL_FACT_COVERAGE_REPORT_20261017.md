# A25：共同测量补齐扇出事实

源码与原始报告核查发现：原 ORFS 已输出 `finish__timing__drv__max_fanout`，共同复测却只记录 slew/capacitance 违例数。因此，原十项冻结目标的判断不能被扩写为已经检查全部 SDC 电气条件。本片补齐这一事实，原 PPA、目标 ID、专业算法和评分保持。

## 实现与兼容边界

- `chip_evolve/physical.py`：共同测量先调用原生 `report_check_types -max_fanout -violators`，再记录原生扇出违例计数。固定 OpenSTA 源的计数函数依赖 CheckFanouts 初始化，标准 report 完成初始化；不修改工具或专业算法。
- 同文件保留已派发测量的原 Tcl。恢复旧任务时，旧结果缺少的新字段保持未知，不写成零，也不改写旧脚本来冒充新检查。
- `admin/test_final_fanout_facts.py`：覆盖初始化顺序、实际零/非零计数，以及旧任务恢复的脚本字节与未知值。没有新公共函数签名、API 路径、业务阈值或数据库结构。

新增指标沿原生 JSON → 原 ORFS adapter → DF → 公开 SDK 回流；Codex 根据事实判断，不新增评测服务。正式最终候选必须有对应 SDC 条件的实际证据，不能从 slew/cap 为零推断 fanout 为零。当前十项已冻结业务目标没有增删；JPEG 明确声明 max fanout 10，受检 GCD/AES 的冻结 SDC 没有这一显式声明，不给它们虚构统一阈值。

## 实际检查

先通过公开 EF 对三份既有结果做独立只读检查，分别增加同一原 Run 的 DF 补充视图；再通过修改后的正式 `measure`/`publish` 路径运行三设计。每份正式结果的七项 PPA 与原值逐值一致，扇出违例均为零，八项事实和身份均从 SDK 查回。按原 Run、finish 阶段查询仍能同时获得原七 PPA 和新增扇出事实，补充视图没有遮住原指标。三次重入复用同一测量 run，没有重复 EDA，原脚本 SHA 保持。

另用 GCD 做私有计数反例：在读取原事实后，仅在该分析进程内施加 0.5 的 fanout 限制，检测到 **408** 个违例。反例没有发布到业务 DF，没有修改原 SDC 或目标，不是优化结果。它说明计数不是无条件返回零。

独立核验重新读原生 JSON/功耗日志、原输入与镜像哈希、公开 EF 终态/attempt 和 SDK：13 项托管任务均成功且各一次 attempt，已知托管 CPU 87.08 秒，无缺失 attempt CPU；117 份证据文件哈希、26 份用户文件通过。主 Codex、前端和独立服务成本不在该 CPU 范围内。没有新优化、源码构建、全布线、功能证明、采用或正式对照结论。

针对测试修复前 2 失败/1 通过，最终 3 项通过；467 项根回归及 Ruff/格式/Pyright/差异和模块边界检查通过。测试中一次补丁定位错误被立即拦下并修正，没有 EDA 执行错误测量版本。原失败日志、源前状态与实际证据保留在 `var/business/a25-formal-preparation-20261017/electrical-coverage-r1/`，主要回执为 `independent-acceptance.json`、`product-requalification.json`、`negative-control.json`、`independent-managed-runs.json`。

## 活动工作与切换

原 JPEG 前端 379322/控制器 380965 保持运行，它们已加载旧测量实现，本轮产物不回写成新格式。旧候选的缺失事实需引用实际原生最终检查或另作补核，不能用本片三份结果代替所有候选。

仅将尚未派发任何任务的等待队列 r1 置换为 r2，保留旧 spec/receipt/log 和 superseded 说明。新队列 PID 717623、句柄 83362，目录 `serial-calibration-continuation-r2-fanout/`；46 份文件指纹通过，五条命令、原专业算法/模型/参数域、顺序和预算完全一致。一次 `ps` 无子进程返回 1 的检查误判发生在发信号前，已按实际退出语义修正并保留说明。没有取消任何 EDA、重启服务或改动活动 JPEG 副本。

队列仍等待原完整 JPEG：空闲后更新 Gateway 并核验实际接单，随后两个 JPEG Code 健康轮次，再做恢复原范围的 GCD 完整搜索。首轮 50 项布线全部到终态后另核对实际 CTS→route 输入；原完整搜索继续第二轮。A25 尚未冻结，A26–A28 未开始。
