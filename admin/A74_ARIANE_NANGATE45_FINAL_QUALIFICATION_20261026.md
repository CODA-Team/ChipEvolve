# A74：Ariane/Nangate45 保存 GRT 的最终物理收尾

当前状态：**前置核查通过，真实详细布线进行中；尚无最终 PPA 或合格结论。** 基线根 `c7ab9e1`，本切片没有修改产品代码或专业算法。继续采用具体诊断、实际阻断、有限验证和 code-check 的工作方式。

## 本次业务问题

A59 已在6ns条件下消除 GRT 电气违反，A73 确认公共恢复入口保留同一设计状态与正 setup/hold 余量。仍缺的是最终详细布线、提取寄生及共同测量，不能用 GRT 估算替代最终结果。此次只完成这个已保存检查点的确定性物理收尾，不重做布局、专业调参或模型搜索。

## 执行前已核查

- 公共 `resume` → `delivery.recover/finish` → `physical.qualify(preserve_global_route=True)`，保持现有接口；检查脚本确实消费保存 guides、不重新 global_route、不覆盖原路由层范围。
- 原 A59 ODB、父结果、SDC、Liberty、setRC、RCX规则与目标哈希保持；实际共同镜像完整 SHA 与配置一致。设计为 Ariane/Nangate45 typical，两个6ns时钟，原目标/时序与功耗面积上限不变。
- 工具8线程，EF申请8 CPU/16GiB、单次原预算14400秒、1 attempt。原同规模qualification峰值约9.34GB、等待约1727秒；没有套用小查询限额。
- 实际EF工作队列空闲、当前worker可消费。账号内存组实际用量加16GiB仍低于现有限额，磁盘余量超过30GiB；原件记录了实际字节数，没有提权、服务切换或清理历史资料。
- 根业务Python与A73同字节，A73/既有733项验证复用；本次再跑19项显式物理接力相关回归，通过。两份私有驱动的Ruff、格式与严格Pyright通过。26份用户在途文件保持。

## 已启动的真实任务

公共EF任务 `run-376fac03616245beb2e94e60b82c442e`，attempt `attempt-913d909bbd7b437c8d4d295d28050a29`；2026-10-26 05:31:33北京时间开始。实时公开状态为running，日志已进入DRT pin access，有实际进展；资源由EF统一预约。一次观察超时不构成失败，也不能据此重启任务。

实验目录复用A73已核查的 `var/business/a73-nangate45-grt-handoff-20261026/runtime/experiments/ariane/a73-saved-GRT-intake-r1`。本次配置只选择A73已验证的Query解释器，保持实验位置和其他参数，未修改A73原配置/历史记录。

确定性后续仍由原业务代码完成：DRT → RCX/SPEF → 共同功耗/面积/setup与hold测量 → 现有三事实导出 → DF/DI。Codex读取后根据原目标判断；生产流程成功与业务可行是两回事。最终功能证明和采用必须另有相应证据。

## 恢复与验收

当前驱动终端session `82815`，日志在 `var/business/a74-ariane-nangate45-final-qualification-20261026/resume-driver.log`。先查询这个session及上述EF run；如果运行中，继续观察同一个任务。驱动报错时先读EF状态和原始日志，已有成功的EDA通过公共resume复用，不重新发起专业搜索。

本切片证据目录 `var/business/a74-ariane-nangate45-final-qualification-20261026/`：`baseline.json`、`preflight.json`、`local.json`、`live-qualification.json`、`live-logs.json`、针对性测试及静态检查日志。物理完成后需核对原始输出SHA、DRC、setup/hold WNS/WS/TNS、电气违反、功耗与cell/core/die面积、条件/父子引用及DF/DI/Query事实回流，之后才能给出通过或具体失败原因。

此检查点只表示已消除“尚未启动最终资格”的工作缺口，没有宣称最终合格、新增优化收益或两次重复完成。Ariane/ASAP7 setup闭合、Ibex/Nangate45完整证明、GCD/Nangate45 500ps协作及八组双次仍待继续。
