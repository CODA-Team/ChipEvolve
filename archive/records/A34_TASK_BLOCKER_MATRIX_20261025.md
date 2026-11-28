# A34：逐功能阻断核查与短验证

本轮基线 `7121cfc`，接续 A31–A33；长搜索保持暂停。核查顺序是具体输入/源码诊断、定点修复、短验证、code-check。已有同源码有效验证复用，不将单元测试当成新的物理结果。

## 已确认的运行事实

- 新建八份配置，明确 EF `41151`、DF `43789`、A33 验证后的 Query wheel/解释器、原专业模板、设计时钟与库 SHA。仅清除新配置中失效的历史 PID 元数据，未重写历史输入或切换服务。
- 公共 EF 实际容量为 32 CPU / 32 GiB，八份配置原有资源申请均可容纳。并发等待不等于任务不能消费；没有调大服务容量。
- 八组历史结果经 DF/DI 查询，六项原始汇总指标逐值一致；A33 独立安装包精确 run/snapshot/revision 的 WNS 查询 **8/8 通过**，未调用模型或新 EDA。这里特意使用历史结果，不能将旧 GCD/Nangate45 250 ps 结果充当新 500 ps 基线。
- 已建立老板批准的 GCD/Nangate45 500 ps 新 SDC，仅改变周期变量，保留原 20% I/O 延迟公式及其他约束。EF `run-635baaf34ae34afeb9eed24cfe5cb562` 实际加载物理与虚拟时钟均为 **0.5 ns**。这仅验证加载，完整同条件基线和协作仍未运行。

## 按功能块的核查表

| 功能/任务块 | 当前证据与判断 | 实际阻断及下一项短验证 |
|---|---|---|
| EF 提交、消费、预约、监控、日志 | A32 396 测试及 A34 实际诊断均由原服务接受/执行/留存；本轮容量取自公共接口 | 当前未发现无法消费本轮任务；源码更改才重做对应回归，不新造调度器 |
| EF 失败、取消、恢复、产物读取 | 复用 A23/A25/A31 的真实记录及现有失败/恢复测试；A34 失败子进程原件仍可读取 | 诊断外层进程成功不等于原生动作成功，必须检查各子命令退出码和完成标记 |
| DF 解析、存储、来源 | 八组原件→六汇总指标同值，DF 启动身份已在 A32 查验 | DF 用户工作树、manifest、实际安装包有版本差异；继续分列，不擅自重置/热切 |
| DI 查询契约 | A32 13 测试，本轮实际 SDK scope/metric 查询通过 | 用户在途修改保留；源码检查不能代替运行包身份 |
| Query 简单事实 | A33 179 回归与安装包正反例，本轮八组精确查询通过 | 本阻断已修复，新任务显式绑定 A33 包 |
| Query 比较/诊断/交接 | 复用既有专业事实、父项对比、上下文与原生失败透传测试；根业务回归继续覆盖 | 简单查询不另开 hosted 会话；复杂调查的上下文成本仍需优化，不重造 harness |
| Toolkits/共同工具链 | A32 镜像 SHA、78 测试、八组库绑定；A34 实际工具/时钟加载 | 二进制自报版本为 unknown 时使用实际 SHA 与固定镜像，不捏造版本号 |
| Flow 原生完整能力 | A32 97 测试；已有完整搜索保留 | 500 ps 条件的完整试次未运行；现代源码综合资格不能由旧默认综合收据替代 |
| DPL 检查点/源码构建/交付 | A32 47 测试及既有 GCD 真实布局接力；模板 build32/variant8 可容纳 | 不要求所有设计强跑 DPL；新增输入仍需查适用阶段，不把 HPWL 局部收益当最终收益 |
| Goal 原算法/目标/构建 | A32 441 单元+53 客户端边界，已有专业二进制与原生输出保留 | 实验性 MeasuredCriticalPath 的已知崩溃保持失败，不盲目继续 CPP 补丁；查实际选用 recipe |
| ECO 模型参考/物理输入 | 原执行会话与动作保持 | **新发现：物理加载支持显式库，延迟参考仍只匹配 ASAP7 文件/单位；Nangate45 必须定点修复，下一切片处理** |
| 手工原生 GRT 收尾 | 本轮复现 Ariane/Nangate45 首次 buffer 的 EST-0104，刷新后继续暴露 SIGSEGV/SIGFPE | 不将旧错误消失当修好；按源码检查 RC、名称与合法化网格初始化，验证原两条动作，不改专业算法 |
| 共同交付/采用/功能证明 | A31 恢复 Ibex/ASAP7 完整 PASS、同值重放与采用；既有 GCD/JPEG 证明保留 | Ibex/Nangate45 `run-010c1023e6514e99911eb866bdcbe4ae` 确为 1800 秒超时，尚无完整 PASS，不重启全场证明掩盖 |
| 环境冻结 | 旧 `freeze_environment` 是 ASAP7 完整 Flow 来源资格；本轮八份 local 配置没有绑定它 | 这不是本轮普通业务 CLI 的必经入口。未来双 PDK 正式冻结应按实际能力收据扩展，不直接删限制冒充通过 |
| 四设计×两 PDK×双次 | 复用已完成合法分支，旧负结果保留 | 新 500 ps 同条件基线/协作、部分设计合法结果/证明/双次配对未闭合；本轮不生成新均值或宣称全场完成 |

## 手工 GRT 定点诊断

原失败脚本已有 `global_route -start_incremental`，因此不是漏加这一句。

1. 原顺序单动作：`run-c2811ade99e24b639aa266e921c53baf` 子命令复现 EST-0104，exit 1。
2. 同一诊断中的 RC 刷新：EST-0104 消失，但 exit −11，未创建 buffer，**失败**。
3. `run-c28d57ce836545c9843900bd569b4329` 加显式 buffer/net 名称后仍 exit −8，未完成动作，**失败**。

4. `run-1e7c961c34ac4c489d5c16c944ec72e3` 增加网格初始化后 exit **0**：原始两条 resize/buffer 动作连续完成，实际新增 **2 个 BUF_X4 实例及 2 条网线**，incremental GRT 正常结束且最终 GRT RC 刷新通过。没有运行完整 repair/DRT/PPA、模型或采用。

源码解释：`sta::replace_cell` 留下 invalid parasitics；placement refresh 清理后必须恢复 GRT。原 native wrapper 将默认空 buffer 名传给 OpenDB，显式名称绕开该路径。进一步发现 native `insert_buffer` 调用 `legalCellPos`，入口只 `initBlock`，并未初始化合法化网格。原生 `check_placement` 可初始化网格且不运行优化，新副本已通过上述两动作短验证。

代码仅增加 `admin/manual_grt_compatibility.py`（既有手工 Tcl 的内部迁移）及针对性测试，不改变物理策略、选中驱动、X4 单元、评分或公共接口。旧脚本/失败原件保持。不是把该手工任务冒充新 Student/ECO 会话。

## 验证和留存

运行证据：`var/business/a34-task-blockers-20261025/`，包括 `prepared-runtime-bindings.json`、`gcd-500ps-clock-validation.json`、`eight-existing-facts-check.json`、原/修正诊断收据和日志。

最初误用 `pytest admin` 收集了历史 `legacy-integration`，12 个旧路径依赖错误留在 `root-regression.log`；当前业务约定入口为 `pytest admin/test_*.py`，最终版本 **642 passed**。新增 4 项针对性测试、Ruff、格式、Pyright、`git diff --check` 均通过，26 个用户保护文件哈希全部保持。代码审查确认原驱动/单元/动作顺序不变；代码仅调用已有原生命令，跨模块仍走 EF/DF/DI，未引入新的服务/数据库或跨源码路径。未据此放行长实验。

逐文件职责：`admin/manual_grt_compatibility.py` 迁移指定手工脚本；`admin/test_manual_grt_compatibility.py` 检查两动作顺序、RC 模型恢复与无关策略不改写；本报告维护全功能阻断表；`TASKS.md`、`ARCHITECTURE.md`、`admin/STATUS.md` 记录可续接状态。若修改这类手工收尾的兼容顺序，修改前述内部迁移函数即可；历史任务不变，新副本显式调用。完整双次实验与老板业务验收尚未完成。
