# A24：JPEG完整专业预演与预算校准

承接老板批准的A23–A28连续验收计划，根基线 `f27311c`、EF `6ace0e2`。A23原目录并发及原位更新/在线复测均通过。运行资产放 `var/business/a24-jpeg-pilot-20261016/`；26份用户工作继续按hash保护，专业源码及公共契约不预先修改。

## 业务验收

1. 使用已冻结的JPEG显式完整旋钮来源、545ps时钟、原FF/库/目标/轮廓约束，在统一EF上完成真实Flow搜索，不以固定重放或一条基线冒充搜索。
2. 分别运行两个Code原生最小完整Teacher/Student轮次，保留原算法、研究增量、评分及晋升；结合实际瓶颈检查ECO适用性/原生调用。无有效动作、拒绝晋升和预算耗尽分别如实记录。
3. 用Query事实和诊断选择合法来源及交接，实际消费上游结果；不强制所有专业固定串联，不向下游隐瞒输入违例。单项/接力的最终共同条件PPA与转换成本分列。
4. 合法拟采用结果完成原功能参考的全输出证明、独立物理重放及SDK身份/指标核对。不能以专业内部结构检查替代完整逻辑证明。
5. 记录准备/编译/模型/EDA/数据/恢复/验证成本和运行稳定性，给A25同总预算提供依据；本片为预演，不是正式公平输赢表。

## 实现范围和数据流

- 本计划、后续报告、TASKS/状态文档：登记真实进度、证据与预算，不改写历史。
- `var/.../runtime/local.json`、原输入hash/阶段请求与进度：复用已验证业务配置，另设本片工作空间，EF41151/DF43789及已安装公共wheel保持。
- 复用 `chip-evolve.py diagnose/run/candidates/compare/validate`；不新造控制器/搜索器/服务。必要运行监督脚本只记录当前命令/退出/原产物，专业推理与取舍仍由原专业和Codex负责。
- 如实测发现兼容/交接缺陷，先在本片说明受影响文件与证据，再做最小修复和对应门禁；不编辑活跃运行副本。

数据为已冻结JPEG来源→SDK/Query诊断→Codex选专业→原控制器→EF执行/产物→DF/SDK最终事实→Codex选择交接/验证。工具链及各专业私有源码身份保持。

### 预演实际发现的共享接点修复

第一次真实JPEG Query诊断正确报告缺少完整原验收约束：根准备器只给目标ID、测量和违例列表，没有交付目标正文。原部分诊断及模型成本保留。改动 `chip_evolve/diagnosis.py`，复用公共Toolkit的冻结目标加载、条件ID及已有提示格式，校验design/objective/condition与测量绑定后，把原目标完整交付Query；明确它是调用者提供的业务要求，观测事实仍由SDK/证据支持。对应 `admin/test_query_objective_handoff.py` 验证全约束/条件实际进入模型请求、错绑在模型调用前拒绝。影响所有专业共用的诊断准备器，不改函数签名、数据底座/API/SDK或专业算法，不编辑活跃副本；静态/相关/根回归通过后再做新诊断。

JPEG首次DPL发现声明profile为JPEG、原生case仍指GCD：真实任务执行GCD，并在根收集JPEG报告时失败，未发布/采用。新增根 `dpl_case.py` 根据登记design生成私有原生problem的四项身份头，完整保留原目标/guardrail/patch_surface；`professional.py`仅DPL分支准备/传递实际case ID，原GCD/AES配置保持同名；DPL `scripts/platform/execution.py`在提交前调用已有原生case解析CLI，拒绝case与profile的design/platform错绑，防止错误实验被标记成另一设计。对应根/模块测试验证未知设计、原生CLI解析、原算法字段保留和错误绑定的提交前拒绝。原失败副本不改，模块检查点发布并重新冻结同物理来源资格后，新建DPL实验重试；不修改正在运行的Flow/Goal私有副本或配置。

ORFS对照入口审计发现 `run --capability orfs --objective` 只记录参数、未传给已有 `physical.baseline(..., objective=...)`。仅修改根 `cli.py` 这一调用，沿用已有关键词参数；新增 `admin/test_orfs_objective_handoff.py`，验证相对目标路径传入物理边界、未指定时保留原基线派生行为。该CLI由全部能力共用，但改动局限ORFS分支，不改公共签名、目标内容或专业算法。JPEG默认内置综合实际因缺少目标单元的物理master失败，保留失败；另设明确Yosys来源对照，不能将其称为未修改的默认配置。

真实并发期间，EF公开资源视图显示两项8/24GiB任务可领取，但在64GiB等待任务之后长期排队。审计 `RuntimeWorker.serve_forever`：每轮从队首重新遍历、先占线程槽再进行权威资源领取，资源不足的旧任务能反复占满异步尝试槽，后面的可执行任务被跳过。拟只改EF内部 `worker.py`，跨监控轮次保留当前等待队列迭代位置，空槽继续尝试后续任务，扫描耗尽再刷新；不另建队列，原写事务仍原子核验/预约，资源/租约/取消/专业接口不变。新增隔离的真实Runtime/Store回归：保留大任务资源，队首大任务不可领取、队尾小任务可领取；异步服务必须实际完成小任务且不超额预约。先复现再修复，静态/单元/边界/回归通过后发布独立模块检查点，服务仅在本轮任务排空并核查后原位更新，不编辑活跃安装。

Flow第二轮三候选批次因一项密度非法而不满足原clean identity quota，原失败保留。按原项目建议的50候选、两轮新建完整批次，保留原10份身份保障、完整参数域、阶段淘汰及模型行为；这是预演预算校准，不放宽算法或将失败批次改记成功。

批量交付审计发现 `collect_flow` 为每份完成的候选都调用完整 `publish`，而A23已测到单JPEG OpenDB大写入692秒。改根 `physical.publish` 的私有可选模式选择，默认三类交付保持；仅Flow批量候选先导入全部最终PPA/硬约束和原OpenSTA时序事实，保留所有原生/物理产物，缺少的OpenDB索引以显式 `deferred_facts` 元数据登记原发布目录。新增根 `design_facts.ensure` 复用原EF导出/DF导入按需补齐，保留同一测量run及原不可变result字节；`professional.execute`、`diagnosis.diagnose`、`validation._validate` 在实际消费所选结果前调用。新增测试验证默认完整交付、轻交付不伪造对象快照、补齐不重新计算PPA且幂等复用导出、Query/Code/验证均消费补齐后的真实scope。此可选结果元数据不增加公共模块API/服务或专业算法，不编辑活跃副本。当前旧根进程在原生搜索正常结束后才能交付接管，以已有 `collect-flow` 恢复确定性交付，保留所有尝试及人工交付恢复成本。

## 初始预演预算与验证

原生DPL事件又确认队列等待造成多次模型/工具状态轮询。仅给后续平台模式的原生Codex请求补入模板 `prompt_templates/teacher_loop/shared/platform_execution.md`：生成的构建/评价助手本身等待终态，保留同一命令会话，由EF监控；真正基础设施失败交给父级处理，不在Student里反复改资源profile。`scripts/codex_exec/runner.py`在现有目标/上下文追加之后保存该说明，原生非平台模式保持；`validation/test_shared_objective.py`在实际原生调用边界核查平台/非平台prompt及原目标/诊断仍保留。仅改说明和请求准备，不做新harness、不改模型/算法/评分/晋升或活跃私有副本；原轮询及失败成本保留，后续实测前不声称token节约。

候选验收接点审计确认 `validation.replay` 只能识别Code交付检查点或ORFS根请求，不能直接重放Flow候选。新增根私有 `flow_replay.py`，从原候选archive提取真实`3_place.odb`，绑定原result/config/recipe/objective及archive内容hash，复用已有`checkpoint→finish→resume_layout`完成CTS、完整route/RCX及共同测量；保留原生stage SDC和实际参数，明确重放范围从pre-CTS开始，不声称重新搜索或从RTL重演。`validation.py`仅在无既有Code检查点且有原生candidate/recipe时选择此分支。五项回归验证实际placement、重接身份/改源拒绝和Code优先级，先4失败/1通过、后5通过；根328项通过，改动文件Ruff/格式和实际wheel测试环境Pyright通过，26用户文件hash不变。复用历史GCD真实候选在线核对七项PPA，JPEG业务验收仍待原生搜索完成。公共API、专业算法、DF/DI和活跃控制器不改。

这些是预演上界，不是正式实验预算，也不是给团队每项分配一份正式总预算：Flow两轮、每轮三候选，原生执行最多14400秒；DPL一轮三Student最多21600秒；Goal一轮四Student最多28800秒；ECO适用时原生两轮最多7200秒。先运行Query与Flow，Code可从同一合法来源分别运行，再按瓶颈选择真实接力。保留原源代码最低轮次，不以缩减Student或参数域通过。

每个阶段通过公开状态观察任务是否消费、健康运行、资源等待和终态。先检查输入/环境身份，再运行真实阶段，逐项核对原约束/原生筛选、最后证明/独立重放。已有接口不改时不重复无关全仓测试；有实际修复时执行对应静态/单元/差异/边界/回归。预算不足保留未完成，不重启整个实验抹去成本。
