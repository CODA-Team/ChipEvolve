# A31.2：当前状态不被旧交付恢复记录覆盖

`status`曾在存在`delivery-recovery.json`时把几乎所有非pending状态改为succeeded，包括后来发生的真实失败。

- `chip_evolve/progress.py`：增加只读状态归纳；恢复记录必须指向存在的本实验结果。显式当前状态始终保留，`delivery_recovered`仅说明历史交付已恢复。
- `chip_evolve/cli.py`：既有status命令复用该归纳，字段和参数保持。
- `admin/test_business_status_recovery.py`：实际CLI失败场景、running/pending/succeeded、缺失/不同结果及缺状态的合法交付回归。

静态/格式/Pyright通过，28项相关与635项根回归通过；差异仅状态只读解释，没有更改任务执行、数据库或专业算法。

真实Ibex恢复验证的status输出已经保存到`var/business/a31-result-recovery-20261024/real-business-status.json`，可以同时查看当前validation与EF任务。

原Ariane基准观察器的等待目标已核对：第一遍EF `run-9efb2a4da95144d299b49b1d7d4a9abb`终态failed/orfs_error、第二遍未提交。原JSON/CSV已保存，精确停止PID/start_ticks核对的只读观察器，不取消EDA；汇总保留七组合格参考对，缺失项标注具体阻断，避免持续每分钟写入等待记录。回执为`baseline-observer-close-receipt.json`。
