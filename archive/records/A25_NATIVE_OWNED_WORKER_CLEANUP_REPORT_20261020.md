# A25：显式原生 worker 收尾与有效策略消费核验

本轮补齐正式直接侧对照的一项清理缺口，并取得JPEG有效20%参数对照的原生结果。A25仍未冻结，A26/A27正式试次与A28未完成。新增代码仅在隔离分支`a25-native-owned-worker-cleanup-20261020`、提交`7b9bdbd`，没有热切活动入口或专业源码。

## 问题、改动和边界

旧记录器在超时后捕获前端树，但直接侧持久worker可能经启动者退出后成为PID 1的子进程，并使用独立session。新增真实重挂父进程测试在旧版失败：记录器已经超时，登记worker仍存活；测试自身随后清理该夹具，未遗留进程。

隔离改动仅三文件：

- `admin/native_worker_cleanup.py`：可选`native_worker_cleanup`配置，要求新实验状态目录及其中的显式worker回执，依PID/start ticks、同账号和实际cwd确认归属，捕获其后代再收尾并报告终态。回执缺失或身份不符不能算清理成功，不处理无关任务。
- `admin/run_native_codex_episode.py`：准备上述可选计划，在实际结束后的finally执行并将清理开销包含在墙钟/原观察CPU范围；正常答案若仍有登记工作未结束，则标为失败。原超时/中断状态保留，未声明此选项的调用保持原行为。
- `admin/test_native_worker_cleanup.py`：10项检查覆盖重挂父进程、正常/异常结束、状态保留及无关或旧身份不被终止。

这不是新Agent harness、调度服务或评测底座，不改变EF/DF/DI、专业策略、评分、资源额度或模块公共接口。内部`prepare(spec) -> WorkerPlan | None`、`retire(plan) -> dict`只服务实验记录器；正式直接侧仍保留原项目源码/CLI/AST/EPD和普通脚本能力。它仅覆盖显式登记worker及捕获后代，不能宣称自动发现所有任意脱离的进程。正式运行方式需要可靠登记其持久监督进程，实际完整业务仍须独立验收。

## 工程与真实工具验证

Ruff F/I、格式、生产文件按实际client解释器的Pyright、测试按query验证解释器的Pyright均零错误/警告。最初把含pytest的测试交给未安装pytest的client解释器，诊断保留；没有为此改源码或注入路径。

37项生命周期针对检查和完整555项根回归通过。首份完整回归为551通过/4失败，原因是隔离工作树未初始化DPL，既有测试找不到其原case_registry.py；补入固定83a77bb提交的原文件、相同版本测试环境/Goal CLI/admission后全通过，没有改断言或部署模块。逐文件差异及内部依赖边界检查通过，未读取或运行用户评测修改。

另用真实原生GCD验证：复用已资格的原ORFS命令，仅改变私有输出绑定及key，在真实floorplan阶段向本次记录器注入SIGINT。登记的持久worker已重挂到PID 1；新逻辑收尾10个实际工具/监督进程，逐PID/start ticks复查无同一存活进程，独立进程保持运行。总资格墙钟约8.79秒，记录器保留interrupted；这不是PPA失败，也不是完整物理、正式A27或专业优化成功。

该检查使用本地协议传输夹具启动真实EDA，模型调用0；没有把它称为实际Codex完整业务。它是直接侧ablation执行方式的资格，非生产Agent绕过EF。实际物理CPU不全在记录器已回收后代范围内，未知部分保留，不填零、不与EF采样CPU盲加。证据在`var/business/a25-native-owned-worker-cleanup-20261020/engineering-acceptance.json`及`actual-native-gcd/`。

## JPEG20%：原生已交付，最终PPA仍待计算

公开EF run-ee17837aad8545cebbbc57379abdfb0d已成功。独立核对注册zip/SHA、12项捕获、原pre_repair网表、c2ff…二进制和701份声明源码、原目标与26用户文件均通过。共同最终DRT/RCX run-0c48727de91241a6b46fd3ed7bfcf498仍等待24GiB资源，不能采用或宣布最终改善。

原80%的实际接受动作为9774次，20%为9730次，仅少约0.4502%；动作预算虽已变化，实际动作量没有按请求比例下降。原源码withinPhaseBudget按baseline绝对TNS乘以(1+扩张比例)限制阶段接受，本次扩张比例仍6；原生功耗阶段TNS约−0.013701ns/−0.013786ns，均接近原0.013835ns预算。日志同时有phase_budget/window_phase_budget拒绝，因此不能仅凭动作上限认定策略力度充分改变，也不把某一种保护当作最终退化唯一原因。

20%原生全局布线TNS约−5.03109ns，比原80%约−5.32922ns略少，但仍有违例，且不是共同最终寄生条件。保留原参数与目标，等待既有五组最终物理结果后再决定策略，不追加盲目比例扫描。实际证据为`var/business/a25-jpeg-effective-reclaim20-20261020/independent-native20-acceptance.json`。

## 成本与继续入口

r56沿r55已计费ID去重，新增3成功EF任务、采样CPU10937.94秒、未知attempt用量0，包含native20；31项本次观察未终态任务不当作已闭合费用。真实直接侧清理资格单列一次EDA/0模型和约8.79秒墙钟，不混入EF CPU。原生模型/源码复制/服务/本轮测试及主Codex未知范围继续保留，账本不是全场完整费用。

继续原完整JPEG2×50、四策略最终物理及20%最终复测、Goal路径隔离构建/两项原回归、AES129输出PDR，随后完成原生完整参考和实际Flow→Query→Goal接力。活动主管及公开任务必须重新核验，不因一次观察超时重启。根700f46e变量时钟、本隔离清理及后续真实合格的源码修复待固定消费者安全结束后收口，重绑最终环境/原AST与EPD/模型/来源及停止政策，才能冻结A25并执行正式双核心实验。

本次主根文档改动清单：本报告、TASKS.md、ARCHITECTURE.md、正式实验协议。26份用户文件保持；私有脚本、夹具和实验数据留var，未推送运行产物。

## 同日续查：两项已验证修复组合为一个未来入口

独立分支`a25-future-integrated-root-20261020`、提交`09f95a551c7c78fa028dbb0e8df6e0c993bca881`组合700f46e变量时钟和7b9bdbd显式worker收尾，根基线为2b62e0c。五份涉及文件与各自原合格版本逐字节相同，没有新增专业策略或公共接口。组合46针对/564完整根回归一次通过，Ruff F/I、格式及按实际生产/验证解释器分开的Pyright零错误/警告。独立工作树补入原固定测试环境、admission、Goal CLI与DPL registry文件，未改测试断言、生产模块或服务。

用现有三设计合格配置在组合根执行Flow/DPL/Goal/ECO共12项check_environment，原三个实际EF探针公开回读均成功；工具、来源和专业版本未变，不重复派发新工具探针。真实AES原始变量SDC经过组合flow_sdc后保持原字节，再提取当前原生run_sequential.sh的实际AWK改写程序，分别产生810/900ps候选；真实Tcl求值得到clock810/input162/output162及clock900/input180/output180。时钟/IO命令使用观察桩，此检查证明原生配置改写与表达式传播，不是OpenSTA物理分析或AES完整调参。

四份活动规格的55/53/10/219固定输入与各自26用户文件SHA均通过。新`local-combined-root-qualified.json`沿用现有专业/工具/来源绑定，仅给未来实验独立state_root；状态目录未创建，未派发新EDA或模型，也未切换活动Root、等待者、包或服务。组合验证证据在`var/business/a25-future-integrated-root-20261020/engineering-acceptance.json`及`integrated-binding-acceptance.json`。

本轮已发布可统一收口的候选，不能把它写成最终正式环境：Goal路径适配真实构建/回归、完整JPEG搜索与实际接力、原生完整专业参考、AES完整证明及最后的源码/AST/EPD/模型/冷热点/停止规则绑定仍待完成。成本沿r56保持；组合验证没有派发新的EF任务/EDA/模型，原主管仍会按既定步骤产生后继任务，费用需继续闭合。测试、读回及主Codex推理成本仍为其已声明的未知范围，不声称零总成本。主根只更新本报告、TASKS.md、ARCHITECTURE.md和正式协议，A25仍未冻结。

最后公开构建分阶段核对：run-f63203a897834ef9b594c6c010949f0d成功只代表SetupLegacyBase.cc.o编译完成；原主管随后派发rsz_lib链接run-5be86217fcc24c7bbee31b2d3284e0d1，目前queued16GiB，不能把前一子任务成功写成整个新OpenROAD已构建、二进制身份已确定或崩溃已修复。原2674189和回放2691230仍在，继续同一流程。实际命令及公开状态见`var/business/a25-goal-path-lifetime-diagnosis-20261019/actual-build-stages-observation.json`；这些后继与已完成编译的费用不假称已包含在r56。

## 同日实际等待与构建后继

本续查开始时公开首轮route为28成功/2运行/20排队；随后两份当时running任务aa7a3c…及e4a0e3…均成功，源码rsz静态库链接5be862也由queued→running→succeeded。原主管自动派发最终OpenROAD链接6d4e57…，公开仍queued16GiB（池内可用8GiB）；没有取消、重启或修改这些任务。当前主管1557962/2674189/2691230的实际PID/start ticks匹配；局部进展不能替代整个二进制构建或故障回归。

编译实际CPU20.36秒/峰值1241264128字节，静态库链接CPU8.42秒/峰值119455744字节；其等待与原生执行时长分开保留。尚未测得最终可执行文件链接峰值，不能由静态归档的低内存推断整个构建都能缩小额度。后续正式配置应基于完整实测校准，当前32GiB服务池、各专业算法/线程和原任务保持。

r57从r56已计费ID去重，6新增终态均成功、采样CPU18721.19秒、未知attempt用量0，包含该编译/静态链接及四项原Flow任务。最终链接与27项本次未终态观察任务不提前计费；原生live模型用量、服务/测试/主Codex等未知范围保持，非全场费用或正式结果。原始公开收据位于`var/business/a25-goal-path-lifetime-diagnosis-20261019/cost-r57-public-runs.json`；26用户文件SHA通过。本次只更新本报告与TASKS.md，没有产品源码、配置、资源或服务修改。
