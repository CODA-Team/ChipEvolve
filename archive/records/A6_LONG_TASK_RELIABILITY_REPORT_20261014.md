# A6：长任务可靠性修复与真实验证

状态：工程验收通过。执行底座修复、两项真实长构建/物理与数据验证、新DPL Teacher/三Student/review完整轮次及后续CTS/DRT/RCX/DF/SDK均已完成；本片42次公开运行全部终态、无新增租约失联。老板业务验收独立，历史失败不改写。

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
| `dpl-saved-source-replay` | 旧失败轮次保留的Student源码复制、原helper构建、原三基线/候选评价、CTS/route接续、共同测量与DF入库 | 通过；构建1198.7秒，峰值RSS37,096,685,568 bytes；setup TNS=0 |
| `goal-lost-source-relink-r2` | 原失联Goal源码701项hash逐项相同；私有source/build副本挂载到原CMake路径，执行原完整LTO链接 | 通过；链接1180.8秒，峰值RSS37,122,605,056 bytes |
| `goal-rebuilt-native-physical` | 原专业Tcl只改输出目录；随后完整DRT/RCX、共同测量、EF产物→DF/SDK | 运行/数据通过；该非晋升Student的最终时序不合法，不采用 |
| `dpl-complete-campaign` | Teacher/三Student/review正常收尾，原评分/晋升保持 | 通过；00:34:34–03:26:01正常收尾，没有新源码晋升 |

DPL保留源码是旧轮次最终保存版本，和历史失联时的未提交中间源码存在差异，不能称旧失联源码逐字复建；新实验按自己的固定source/binary身份验收。Goal与原失联记录的专业源码逐项一致。

恢复驱动有两条工程失败证据：服务启动第一次探测未捕获客户端的 `KernelUnavailable`，服务本身随后正常启动，已核实实际PID和安装来源，没有二次重启；首次Goal重放误假定输出为`src/openroad`，查原`link.txt`发现是`bin/openroad`，主动取消并保留回执后以真实路径启动r2。两项不伪装成专业算法失败或原租约故障。

当前最好合法Goal单项指针已复制到新业务状态，指向原不可变结果；本片不自动用环境验证结果替换它。长构建采用64GiB/2048进程/8核基线；实际资源/队列/终态通过EF公开回执记录。

## 可复查入口

- 部署：`var/business/a6-reliability-20261014/runtime/local.json`；安装及服务：`before-upgrade.json`、`upgrade.json`。
- 复现：`reproduction-before.log`、`reproduction-after.log`、`lock-reproduction-before.log`。
- 原失联回执继续在 `var/business/a4-a5-20261014/lease-failures.json`；新主动取消在 `goal-replay-driver-cancellation.json`。
- Git/用户文件基线及保留incumbent：`var/business/a6-reliability-20261014/baseline.json`。

本片实际验收通过；旧DPL三小时截止仍是历史失败，不因新成功改写。

两项新物理结果的OpenDB/指标/OpenSTA三个scope均经公开SDK确认设计/run归属，设计摘要和指标可查询，回执见各实验`sdk-query.json`和本片`qualification.json`。根业务及既有回归167项通过，Ruff/新文件格式/pyright通过；运行可靠性前置通过与完整DPL轮次收尾分别记录。


## 完整原生轮次及业务结果

`dpl-complete-campaign`于2026-10-15 00:34:34启动、03:26:01完成Teacher/三Student/review；不是预算截止。三个新候选原生最终HPWL586.7/592.9/611.2µm、均合法且正常结束。Teacher确认第一候选虽然线长最好，但MoveCellAction回滚没有完整恢复方向/引脚状态，晚期接受机制不可靠；其余候选没有充分收益，因此原规则拒绝三份源码，平台没有强行晋升。

随后使用原生已有默认方法接续CTS、完整DRT/RCX、共同测量及DF导入，最终run-ca33897503094510aae669c6f6c78c45，setup/hold TNS均0，setup WS+0.0231264ns，电气/布局/DRC通过，功耗0.0020305505022W、单元面积53.3336µm²、core/die58.7866/78.4819不变。功耗相对同条件ORFS−7.0691%，但比已有合法Goal单项差，不采用；不是新Student源码或联合优化收益。

OpenDB/ORFS/OpenSTA三个scope及summary/metrics经公开SDK确认，见实验sdk-query.json。Teacher拒绝原因及原selection通过既有analysis_of_run_id登记到最终scope，analysis run-3929c0eec11d49a29a7b6927057b9293，公开ZIP成员0/codex_last_message.txt与原review hash一致；不是私有数据库查询。

最终回执：var/business/a6-reliability-20261014/acceptance.json、a6-closeout.json、qualification.json及两份dpl-round-vs-*.json。A6相关42次公开运行全终态，无新增lease_expired，26份用户文件hash一致。增补证据驱动第一次用了相对experiment路径而被公共契约以400拒绝；改用绝对路径的新r2登记，拒绝的本机请求文件保留，没有修改平台校验。首次ZIP成员核验误加query-data前缀，核对真实包根后验证0/...成员；未改变声明的工作区query-data/...路径。


42次终态细分为40次成功、2次真实失败：一项原DPL增量构建超过请求资源，随后专业原生以96GiB完整构建恢复；另一项extractor_error保留。公开失败attempt均检查无lease_expired，真实失败不删、不当成租约故障，也不把42次全部写成成功。


## A7收尾暴露的A6补充接点（2026-10-15）

A6首批42次运行的“无新增失联”只对该批成立。A7 Student3链接`run-68f0cf01a0a34db5b56d90443eb133e5`于20:30:30–20:55:30 UTC以lease_expired结束，失联前有两次公开GET超时；任务声明7260秒，不能归为声明超时。原生重试后来成功，此失败原样保留。已有公开回执不足以证明这次事故的唯一阻塞位置。

源码和可控测试进一步确认：`RuntimeStore.register_artifacts`在共享连接锁内校验、复制产物，能挡住别的attempt续租。测试修改前失败，修改后通过。补充修复`dd56c15`把文件托管移到锁外，所有元数据仍在一个事务中提交；重复声明失败时无部分记录，原对象内容校验、路径边界、取消与fencing不变。两项相关回归通过，完整EF回归378通过/1主机条件跳过，类型和11项尺寸/层级门禁通过。store净增3行，1498行/core 9022行的具体审批留存，不扩大其他文件限额。

新wheel在独立临时EF验证服务中完成真实120,460,336字节专业ELF托管及并发OpenROAD身份调用（run-efe47752a1514189bb2c8c26a5ec9063/run-cee79edd9b0d49528bd0df9fce466941）；真实长链接与默认30秒租约测试继续收尾后补记。生产服务仍保留活跃原Goal轮次，先不在活跃进程中替换运行代码。对这次历史事故的完整唯一根因不作过度结论。

默认租约补充验证通过：两项活跃attempt在35秒托管停顿（超过默认30秒lease）期间保持续租，reaper没有误回收，350次状态读取及时返回。回执var/business/a7-quality-20261014/default-lease-custody/receipt.json；这是隔离EF实现fixture，与真实ELF/长链接证据分别记录。

同一锁机制也在ingest_input_file/ingest_input两条输入托管入口被可控复现：修改前两项失败，移出文件I/O后全部通过。不增源码行数，不改返回字段或事务；最终存储55项、完整EF381项通过/1主机条件跳过，类型/边界门禁通过。最终r2 wheel保留于var/business/a7-quality-20261014/runtime-wheels-r2，前一wheel及其真实长链接验证不覆盖。

补充真实长链接通过：新wheel隔离EF的run-afb5c00a60b34721b86401e0828fa9b0正常完成，CPU966.83秒、包含观察/托管的等待979.46秒、峰值RSS4,803,137,536字节/9进程；核对701份源码，120,460,336字节binary的SHA256与原成功构建完全一致（3d1577d4…）。最终含输入修复的r2 wheel另以120MB实际输入冻结/暂存/sha校验与并发OpenROAD身份任务验证通过。原失联失败不覆盖。

## 最终部署与验收补记

补充修复最终commit15d9586及新wheel已在原Goal轮次正常结束、公开API确认无活跃/排队消费者后更新本轮专属服务。EF/DF仍为127.0.0.1:41151/53305，运行状态和历史DB保留；当前配置var/business/a7-quality-20261014/production-runtime/local.json。最终EF381通过/1主机条件跳过，根175通过；临时资格EF5项真实任务全部成功，服务已停止。首批42项与A7112项审计分开记录，A7历史新失联并未被清除。健康慢生命周期及共享文件I/O锁问题均有可控复现、最小修复和实际证据；不声称未来所有主机负载/设计都已验证。A6工程验收通过，老板业务验收待确认。
