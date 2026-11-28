# A25：恢复入口的目标继承与结果身份

真实原生Codex平台恢复验证确认：观察驱动被SIGTERM终止后，原EF run/attempt继续并成功，重连没有重复完整ORFS；但暴露两个业务错误。针对修复、工程门禁及新r2真实复验均已通过独立核查；原生直接侧也完成同任务身份的恢复资格。这里验证的是确定性EDA观察/交付恢复，完整专业搜索的中途恢复和正式效率不是本片结论。

## 已验证的错误与最小修复

1. 显式请求规范目标`bb3bdcf5…`，ORFS恢复却未向原baseline函数转交objective，生成了`2af83424…`的新目标。本例数值条件相同，但目标身份已经不同；自定义严格约束不能在恢复时丢失。`delivery.recover`现在转交原请求目标，`cli`在保存新请求前将该目标路径归一为绝对路径。
2. 成功后再次resume重新发布结果，三个exports的execution.wait_seconds改变，使result.json哈希从`d59ae62f…`变成`004efcf1…`。这会使已经绑定哈希的交接和验证引用失效。已成功且有结果的恢复现在返回原结果；已有checkpoint的输入哈希检查仍执行，设计或显式请求目标不符会拒绝，不改写旧结果。

修改文件只有`chip_evolve/cli.py`、`chip_evolve/delivery.py`及两个对应测试文件`admin/test_local_workflow.py`、`admin/test_orfs_objective_handoff.py`。公共签名、专业算法、PPA约束、服务和活动JPEG副本不变。待交付和失败任务仍沿原恢复路径，不以缓存替代尚未完成的计算/交付。

## 工程检查与原失败

新增检查修复前9失败/10通过，修复后19项针对检查通过；全部451项根回归、Ruff、格式、Pyright及差异检查通过。覆盖显式/默认目标、不同当前目录、五个专业入口和Flow集合结果的哈希/mtime稳定，以及原checkpoint输入变化拒绝恢复。26份用户文件哈希保持。

原平台案例`native-platform-recovery-r1`完整保留：物理run `run-6266f57790a44a41b0a12782b572f357`在中断前后均运行，随后成功。原生CLI最后返回0，但有TLS重连事件，usage_complete为false，成本只能保留已知下界。题意还曾让模型误以为三种视图都应返回最终PPA；正确验收是三种快照身份一致、ORFS指标视图提供七PPA。OpenDB/OpenSTA不重复保存这些指标不能据此判为DF故障，不修改底座去迎合该误读。

失败证据在`var/business/a25-formal-preparation-20261017/recovery-r1-defect-evidence/`，保存原目标/结果差异及修复前源码；原native事件、SDK响应、重复前后结果和成本在`native-platform-recovery-r1/`。门禁在`recovery-fix-gates/`。原实验不回写或改成成功，新案例将使用独立key及修复后的源码身份。原生直接侧恢复案例的原始产物/进程身份独立核查已通过，详见下文。

A25未冻结，JPEG完整专业轮次/接力、生产Gateway实际更新及A26–A28仍待完成。没有新的PPA收益或正式效率对照结论，老板业务验收独立。


## 修复后的真实复验

平台r2：原生Codex终止自有前端929219时，EF `run-cd5fe7c0ffe14aca98e50c6bd02e4231`正在运行；恢复后仍是同一run/attempt，完整ORFS只执行一次。共同测量及三种事实发布共5个任务均成功且只有一次attempt。结果继续绑定原`bb3bdcf5…`目标；成功后再次resume的结果SHA256和mtime_ns完全不变，运行目录也没有重新交付产生的内容变化。三快照身份及ORFS七PPA经现有公开SDK再核实，全部与规范控制同值。61份冻结输入、26份用户文件及171份证据文件哈希通过独立检查。

原生直接r1：实际OpenROAD正在运行时只终止observer 858704，工具858709的PID与进程start ticks在重连前后相同，实际完整ORFS只有一次调用；原生退出0、所有阶段记录完整。共同测量模板、库顺序和显式ps SDC保持，七PPA与规范控制相同。129份产物/证据哈希、28份输入及用户文件检查通过。核查脚本最初把等价的相对include写法误作错误，原误判日志保留；按实际固定--pwd解析为同一原SIF配置后通过，没有重调模型/EDA。

两侧仍为共享主机的功能资格，不能直接作成本比。平台r2原生输入1,456,270、输出10,809、缓存输入1,379,200、墙钟230.521秒；直接r1输入582,852、输出7,378、缓存输入538,112、墙钟191.288秒。全部原失败和重试进入`preparation-costs-r7.json`，平台r1的TLS事件使其成本仅为已知下界。直接侧持久worker已脱离CLI后代树，其实际RUSAGE单列，不能把记录器CPU当整场完整CPU或盲目相加。

正式任务应以同一业务结果为要求，独立oracle另取内部任务/进程证据；不能把全量底层审计输出强塞进Agent对话后当作普通用户工作量。A25冻结前仍需实际专业动作与交接的匹配资格，以及JPEG完整优化/健康Code轮次和预算校准；不把本片确定性恢复扩称任意未结束的Teacher/Student搜索恢复。

独立验收：`native-platform-recovery-r2-independent-acceptance.json`、`native-direct-recovery-r1-independent-acceptance.json`；原始案例和全部工作目录均在同一`var/business/a25-formal-preparation-20261017/`下。本片源码提交为`4c3a2b7`，之后仅补报告和协议。
