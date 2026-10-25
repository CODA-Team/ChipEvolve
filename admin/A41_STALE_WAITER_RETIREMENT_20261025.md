# A41：清理失效长实验等待器，保留当前空队列

基线 `13d564e`。A38–A40 收尾检查发现同账号 PID207350 仍执行旧 `repeat_feasible_nangate_strategies.py`，等待并不存在的 `local-ariane-nangate45-goal-bound-r1.json`；其余三设计原 status 已成功。该等待器将来可能因补上同名配置而重新触发旧重复实验，与当前长搜索暂停不一致。

先通过公开 EF 接口核对 queued/preparing/running/retry_wait 均为空；再核对该进程完整命令、UID、start ticks、无子进程，仅向这个失效前端发 SIGTERM。进程已退出，EF 队列仍为空，没有取消、重跑或删除任何实验，没有停止/重启 EF/DF 服务，没有改容量、数据库或历史 status。

第一次尝试使用 pidfd，当前生产 Python 没有 `os.pidfd_open`，在发送任何信号前退出；随后在发送 SIGTERM 前重新核对同一进程身份。原记录保留，不新增进程管理框架或补丁。

运行证据：`var/business/a41-stale-waiter-retirement-20261025/before.json`、`retirement.json`、`final-integrity.json`。50 个旧/新配置、八组历史结果和用户保护文件哈希均保持；EF/DF 原 PID 继续运行。此项没有产品源码变化，复用 A40 根 670 回归；短验收是具体进程消失、公开空队列及原件/服务身份核验，不为运行收尾再跑 EDA。

当前已收口 Goal 崩溃、专业源码/构建 donor 绑定、续作工艺目录和旧自动触发器四项具体问题。全目标继续按逐功能清单推进；长实验未放行，八组双次 PPA 和完整设计证明等业务验证仍未完成。
