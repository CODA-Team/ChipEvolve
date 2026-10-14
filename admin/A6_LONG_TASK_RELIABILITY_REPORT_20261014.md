# A6：长任务可靠性修复与真实验证

状态：执行底座修复及工程回归通过，真实长构建/物理与数据验证进行中；原 DPL 完整轮次尚待验收。老板已授权 A6/A7，业务验收独立。

## 已证实的问题和修复

四个可控跨租约延迟分别放在输入准备、资源采样、日志观察和证据收尾。修改前四项全部以 `lease_expired` 回收健康 attempt；修改后全部正常成功。旧续租由 guardian 的取消轮询触发，慢回调和执行前后阶段都能阻断续期。

另一个并发测试证实：heartbeat 在获得连接锁之前取当前时间，锁等待超过一个租约后，会写入已过期的期限。时间采样移入原锁内后，等待结束才起算续租。

两者是已证明的机制缺口。历史三次失联没有完整心跳耗时记录，不能唯一断言每次具体阻塞在哪一环节，也不能将它们改写为 C++ 编译失败。

修复使用一个 attempt 级续租对象，覆盖输入、执行、证据/产物处理，在退出时停止。原 guardian 的取消、硬超时和资源限额仍有效；续租受现有 task/manifest 预算加一个租约周期约束，不让无法结束的回调无限续期。真正杀死 worker 的实测单元场景停止续租、回收 adapter，旧 attempt 无法写成功。未增加专业算法、后台服务、数据库字段或公共 API。

## 文件与承重墙影响

| 文件 | 职责 / 影响 |
|---|---|
| EF `core/runtime/src/openroad_platform_runtime/lease.py` | 唯一内部续租实现；独立于慢回调，按 attempt 收尾 |
| EF `core/runtime/src/openroad_platform_runtime/runtime.py` | 挂接完整生命周期，移除旧轮询续租；影响所有专业/测量/导出任务 |
| EF `core/runtime/src/openroad_platform_runtime/store.py` | 同一连接锁内计算 heartbeat 时间，无数据库/公共签名变化 |
| EF `tests/core/test_runtime.py`、`test_store.py` | 四种延迟、真 worker 死亡、续租预算/线程退出、锁等待回归 |
| EF 三份 `approvals/` 记录 | 内核实际9019行，上限精确增长36行；runtime 文件上限降到1054行 |
| 根 `admin/verify_long_task_reliability.py`、`test_long_task_reliability.py` | 独立安装、空闲专属服务更新、保存源码重放与物理/数据验证；公共SDK/HTTP边界 |
| 根 `SOURCE_MANIFEST.json`、`TASKS.md` 和计划/报告 | 固定模块检查点及真实未完成状态 |

EF 修改只在 core 层；guardian、worker、gateway、contracts 未改。模块检查点 `078795d` 已推送 `modules/execution-foundation`。新 runtime wheel SHA256 `40c78e932f820634f795acba0a14e3ecafca51038c5bbd02f1d0ced574488ee0`。真实运行之前只更新本轮已空闲专属 EF 服务的安装环境，保留其运行记录及 DF 服务；其他历史/生产服务没有切换。

## 工程门禁

- EF：mypy 无错误；涉及文件 Ruff F、唯一新源码格式、差异空白检查及架构门禁通过。既有文件遵循原项目格式，没有为格式化重写无关段。
- EF 全套：377项通过，1项宿主条件跳过。包含七项本片新增验证；完整日志 `var/business/a6-reliability-20261014/ef-gates-final.log`。
- 根：相关边界测试、原业务回归、Ruff/格式/类型与文件差异审查见本片最终回执；最初选择不含SDK的测试环境造成的收集错误保留，改用已安装公共依赖的 qualified Query 环境。
- 原26份用户修改核对一致；不打包 Data Foundation / Data Interface 的本机未提交修改。

## 真实验证和恢复记录

所有新实验在 `var/business/a6-reliability-20261014/runtime/experiments/gcd/`，原实验/失败不覆盖。

| 验证 | 真实范围 | 当前状态 |
|---|---|---|
| `dpl-saved-source-replay` | 旧失败轮次保留的Student源码复制、原helper构建、原三基线/候选评价、CTS/route接续、共同测量与DF入库 | 长构建进行中 |
| `goal-lost-source-relink-r2` | 原失联Goal源码701项hash逐项相同；私有source/build副本挂载到原CMake路径，执行原完整LTO链接 | 长构建进行中 |
| Goal新binary真实GCD物理与查询 | 原专业Tcl只改输出目录；随后完整DRT/RCX、共同测量、EF产物→DF/SDK | 待构建通过 |
| DPL一轮完整原生搜索 | Teacher/三Student/review正常收尾，原评分/晋升保持 | 待固定源码验证通过 |

DPL保留源码是旧轮次最终保存版本，和历史失联时的未提交中间源码存在差异，不能称旧失联源码逐字复建；新实验按自己的固定source/binary身份验收。Goal与原失联记录的专业源码逐项一致。

恢复驱动有两条工程失败证据：服务启动第一次探测未捕获客户端的 `KernelUnavailable`，服务本身随后正常启动，已核实实际PID和安装来源，没有二次重启；首次Goal重放误假定输出为`src/openroad`，查原`link.txt`发现是`bin/openroad`，主动取消并保留回执后以真实路径启动r2。两项不伪装成专业算法失败或原租约故障。

当前最好合法Goal单项指针已复制到新业务状态，指向原不可变结果；本片不自动用环境验证结果替换它。长构建采用64GiB/2048进程/8核基线；实际资源/队列/终态通过EF公开回执记录。

## 可复查入口

- 部署：`var/business/a6-reliability-20261014/runtime/local.json`；安装及服务：`before-upgrade.json`、`upgrade.json`。
- 复现：`reproduction-before.log`、`reproduction-after.log`、`lock-reproduction-before.log`。
- 原失联回执继续在 `var/business/a4-a5-20261014/lease-failures.json`；新主动取消在 `goal-replay-driver-cancellation.json`。
- Git/用户文件基线及保留incumbent：`var/business/a6-reliability-20261014/baseline.json`。

真实验收结束前，不把A6记作全部通过，也不把旧DPL三小时截止改写为正常轮次。
