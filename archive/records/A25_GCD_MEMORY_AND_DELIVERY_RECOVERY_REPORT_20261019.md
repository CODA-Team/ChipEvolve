# A25：GCD 原生完成、内存准入与事实交付恢复

## 本轮实际收口与当前运行状态（2026-10-19）

GCD 原完整 2×50 正常完成；99 布线成功、1 失败，99 个候选已全部交付。公开 EF/DF/SDK 与注册原始输入胶囊独立核查通过：198 快照、1683 数值事实、297 个单 attempt 的共同测量/导出任务。**最终可行 0/99，未采用任何结果**；面积超限 90、功耗超限 36、setup TNS 超限 21、core/die 各超限 20（可重叠）。48 个分支只剩单元面积超限，说明后续应考虑有面积调整能力的专业；不能默认交给不改变单元面积的 DPL，或放宽原约束。前三个面积/余量取舍及当前 SDK 已核对，尚未新增优化或宣称修复收益。

独立审计第一次暴露旧共同测量缺少 `analysis_of_run_id`。旧任务已有父 run、注册命令及完整捕获输入；新的独立审计只对逐项冻结的原 99 个任务开放历史核查，逐一验证 EF 注册请求、ODB/SPEF/SDC/Tcl 与结果胶囊哈希，不覆盖旧失败或补写旧标签。此核查不授权新正式任务缺失标签。前瞻修复 a7c3b31 只加 7 行：新测量声明原生分析对象，旧任务保持原字段；3 新场景/491 隔离根回归与静态通过。一份新 GCD 真实测量及三类事实导出共 4 个任务通过，所有 PPA 原值相同，标签/SDK 正确，旧结果未改。

来源、阶段资源、DPL 线程预约、辅助观察故障及 Toolkit 内存准入的合格候选已安全启用。Flow=7b1003b、DPL=8940667、Toolkit=224a7ad，两个实际运行环境的 wheel SHA 均为 e427367e…04ef7。激活根 dae995b 后 **516 根回归、95 Flow、43 DPL** 通过。环境没有内置 pip 曾使安装脚本停止；旧失败保留，改用既有安装器的 `--python` 指定目标环境完成，未重建环境或更改依赖。DF/DI 与 26 项用户工作保持。

唯一主管现在是 `var/business/a25-serial-recovery-20261019/after-wheel-bootstrap-r3/receipt.json`（PID 3824294），已实际进入 JPEG 原 94 分支共同测量/事实续交；原原生超时和部分完成性质保持。此前停止的主管及错误审计/安装日志均保留，不能重复启动。后续仍是双构建资源资格→五组统一布线控制→Goal03/ECO 共 PDK 与修正 Goal 新完整轮次→健康完整 JPEG2×50，再补实际接力/证明/重放/成本并冻结 A25。

实际交付中六分钟公开观察 343/343 成功、55 个执行中周期，最长读取 0.175 秒；原时序报告精度保留，不据此保证消除所有 I/O 长尾。成本新 r32 去重纳入 965 个新任务：GCD 本 campaign958（917 成功/41 失败）及 4 个新标签资格任务、3 个隔离内存资格任务；新增采样 CPU14733.37 秒，原 22 模型调用/640347token 独立列示，缓存是输入子集。主 Codex/服务/安装等费用仍未知，不报完整总成本或正式效率比。

新增证据：`lineage-audit-r3/independent-audit/acceptance.json`、`new-analysis-qualification-r1/acceptance.json`、`flow-parent-tradeoffs-r1/analysis.json`（前三者位于本轮 GCD 恢复目录）；`preparation-costs-r32.json` 与 `final-cost-ledger-r32/acceptance.json`；实时来源以 CURRENT.json 及新主管回执为准。**A25 未冻结，A26–A28 未执行，正式实验尚未就绪。**

## 早先恢复检查点记录（以下保留当时状态）

本轮继续老板已授权 A23–A28。GCD 原完整参数域搜索已完成 2×50、原生 exit 0；仍在补交共同测量与事实，尚无本轮最终可行率/团队收益结论。A25 未冻结，A26–A28 未执行。

## 已解决与真实边界

- 旧固定 16 GiB 本机空闲检查使一个已预约 8 GiB 的只读评价在工具启动前失败；EF 正确保留非重试型 configuration_error，公开 retry 正确拒绝。通过公开 submit 使用原 TaskSpec、显式新幂等键重交，原失败、旧收据和 leaf recovery_history 全保留；替代评价成功。原生 --resume 接着原检查点完成，绝对截止 1792418501.064773、两轮各 50、原参数域及专业目标不改。原 22 次模型请求/640347 token 的事件文件逐字节相同，没有重新生成搜索。
- Toolkits 候选 224a7ad 按 EF 声明内存等待，并由 EF 截止/取消控制；非托管调用保留原 16 GiB 规则。75 项模块测试、类型和改动范围静态检查通过。真实原 GCD 输入在隔离公开 EF runtime 中等待后执行，与原指标同值；另一任务在等待中被 EF 正确超时，工具未启动。内存读数为显式注入，不是实际生产低内存性能证明。此刻模块主版本/生产 wheel 尚未启用，后续单一串行队列空闲启用。
- 数据已导入后，physical.publish 最后读取 metrics 的 TimeoutError 原来会直接中断整条交付。d5512a0 候选/主线 6b2df72 将临时传输故障记为现有 WorkPending，携带原 run、snapshot 与 experiment，让同 key 重接；永久 HTTP 4xx、错误设计身份仍为硬失败。不改变 EF/DF/SDK 接口或专业算法。9 项新增针对、488 项隔离根回归、Pyright 0 错误、Ruff F 与格式检查通过；改动仅 physical.py 与新增测试。主线启用前核对 79 项原输入全部同值及 26 项用户工作受保护；启用后 78 项不变、1 项授权交付代码改变，不宣称全部旧哈希不变。

资格脚本 r2 的简化 manifest 漏 raw_flow_metadata，r3 首次读取超出公开 excerpt 的 64 KiB 限制；均为隔离验证器错误，原运行/费用保留。r3 已成功的真实 EDA 仅从公开 runtime 对账，未重跑；接着完成等待超时场景。补充独立记录将约 0.002 秒明确为恢复核验时间，原实际执行约 9.53 秒，两者不得混淆。

## 当前队列与业务价值

`var/business/a25-gcd-memory-pressure-recovery-20261019/delivery-r2/receipt.json` 管理现有 GCD 完整结果交付；`var/business/a25-serial-recovery-20261019/receipt.json` 是唯一后继串行主管。旧 R10 及依赖它的等待程序均已失败退出，不恢复其旧成功条件，不伪造成功回执。

1. 补交 GCD 原结果、独立核查全部候选产物/七 PPA/SDK 与全部硬约束；账本包含 recovery_history 的旧失败，不只记录替代成功。
2. 安全启用已隔离门禁通过的来源绑定、任务状态观察、阶段资源、DPL 线程预约、注册物理来源和 Toolkit wheel；保留旧 wheel 身份与所有用户未提交文件。
3. 恢复 JPEG 原 94 个完成分支的交付；旧超时原生状态继续是未完成的部分搜索。
4. 原两份源码/10 线程/各 16 GiB 真实并发构建与完整业务重放；原布局和三个 DPL 布局的五组一致布线来源控制。
5. Goal Student03 自身 Query 上下文→ECO 原八轮、共同 PDK；修正 Goal 基线模式的新原生一轮四 Student。原功耗目标和专业评分不改。
6. 完整 JPEG 原 2×50 健康搜索，原 20 小时原生截止、同参数域/线程，按阶段申报资源。然后独立核验实际接力、全部证明/重放/费用，才冻结正式协议。

这些操作解决的是“不重复昂贵计算、统一资源准入、按设计交付事实、保真交接”。仍须用一致条件的实际实验区分布线模板和 RC 差异造成的损失与专业算法本身效果；没有证明团队优于最强单项，也不能仅凭队列启动宣布正式实验已准备好。

## 证据与恢复入口

- GCD 原生恢复、旧失败/同 TaskSpec 替代：`var/business/a25-gcd-memory-pressure-recovery-20261019/`。
- Toolkit 门禁：该目录 `toolkit-acceptance.json`、`real-memory-qualification-r3/independent-acceptance-with-cost-scopes.json`；原脚本失败日志保留。
- 新读取修复：同目录 `published-read-regression.xml` 和 `published-read-activation-before.json`。
- 交付/后继：上述两份 receipt；全部操作输入、保护清单、日志及回执在独立阶段目录。正式成本尚包括未知的主 Codex/服务费用，不将短任务采样 CPU=0 当作免费。

恢复时先读 CURRENT.json 与两个主管回执，再查其 PID/启动身份及公开 EF；不得重复启动同 key、重置原生预算或重启旧失败等待者。
