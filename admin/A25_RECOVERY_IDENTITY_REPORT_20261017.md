# A25：恢复入口的目标继承与结果身份

真实原生Codex平台恢复验证确认：观察驱动被SIGTERM终止后，原EF run/attempt继续并成功，重连没有重复完整ORFS；但暴露两个业务错误。本片完成针对修复和工程门禁，新的真实复验尚待完成，不能先记恢复整项通过。

## 已验证的错误与最小修复

1. 显式请求规范目标`bb3bdcf5…`，ORFS恢复却未向原baseline函数转交objective，生成了`2af83424…`的新目标。本例数值条件相同，但目标身份已经不同；自定义严格约束不能在恢复时丢失。`delivery.recover`现在转交原请求目标，`cli`在保存新请求前将该目标路径归一为绝对路径。
2. 成功后再次resume重新发布结果，三个exports的execution.wait_seconds改变，使result.json哈希从`d59ae62f…`变成`004efcf1…`。这会使已经绑定哈希的交接和验证引用失效。已成功且有结果的恢复现在返回原结果；已有checkpoint的输入哈希检查仍执行，设计或显式请求目标不符会拒绝，不改写旧结果。

修改文件只有`chip_evolve/cli.py`、`chip_evolve/delivery.py`及两个对应测试文件`admin/test_local_workflow.py`、`admin/test_orfs_objective_handoff.py`。公共签名、专业算法、PPA约束、服务和活动JPEG副本不变。待交付和失败任务仍沿原恢复路径，不以缓存替代尚未完成的计算/交付。

## 工程检查与原失败

新增检查修复前9失败/10通过，修复后19项针对检查通过；全部451项根回归、Ruff、格式、Pyright及差异检查通过。覆盖显式/默认目标、不同当前目录、五个专业入口和Flow集合结果的哈希/mtime稳定，以及原checkpoint输入变化拒绝恢复。26份用户文件哈希保持。

原平台案例`native-platform-recovery-r1`完整保留：物理run `run-6266f57790a44a41b0a12782b572f357`在中断前后均运行，随后成功。原生CLI最后返回0，但有TLS重连事件，usage_complete为false，成本只能保留已知下界。题意还曾让模型误以为三种视图都应返回最终PPA；正确验收是三种快照身份一致、ORFS指标视图提供七PPA。OpenDB/OpenSTA不重复保存这些指标不能据此判为DF故障，不修改底座去迎合该误读。

失败证据在`var/business/a25-formal-preparation-20261017/recovery-r1-defect-evidence/`，保存原目标/结果差异及修复前源码；原native事件、SDK响应、重复前后结果和成本在`native-platform-recovery-r1/`。门禁在`recovery-fix-gates/`。原实验不回写或改成成功，新案例将使用独立key及修复后的源码身份。原生直接侧恢复案例已经收尾，但尚待原始产物/进程身份独立核查。

A25未冻结，JPEG完整专业轮次/接力、生产Gateway实际更新及A26–A28仍待完成。没有新的PPA收益或正式效率对照结论，老板业务验收独立。
