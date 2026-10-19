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
