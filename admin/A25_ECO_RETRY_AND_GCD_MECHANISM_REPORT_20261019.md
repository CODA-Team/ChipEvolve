# A25：真实ECO交付、重试证据修复与GCD配方控制

本轮继续正式实验前资格；PPA团队不要求与单项同总预算。尚未冻结A25，A26/A27/A28未完成。活动源和算法不热改，未通过原约束的结果不采用。

## GCD：区分原Goal配方和Student02源码增量

复用已完成原生搜索中、未经Student修改的`power_then_timing/wns_path_deep`匹配基线checkpoint，经相同现有qualify→EF完整DRT/RCX→共同测量→DF/SDK交付。没有重跑原模型搜索或构建。

独立核对基线与Student02的native Tcl，仅替换输出目录后完全一致；两份实际二进制SHA匹配各自构建记录，工具链与CMake参数相同，701份声明源码指纹只有RepairPowerPolicy.cc不同。该文件实际父源/候选差分与原记录完全一致；新增策略是保护早期已闭合setup的阶段，不含GCD名称、特定实例或GCD数值目标。此为声明范围及该文件审查，不代表全部OpenROAD文件或跨设计泛化已证明。

| FF/310ps | 功耗mW | 单元面积µm² | setup余量ps | setup TNS ns | 原约束 |
|---|---:|---:|---:|---:|---|
| 实际Flow2-37交接源 | 0.890911557 | 44.8918 | 12.289 | 0 | 面积超限 |
| 原Goal相同配方，无Student源码增量 | 0.767353689 | 38.9869 | −85.1976 | −0.890416 | setup不通过 |
| Goal Student02 | 0.715648639 | 39.1181 | 0.0834055 | 0 | 通过 |

Student02相对未修改配方功耗降低6.7381%、单元面积增加0.3365%，恢复原时序约束。Student02此前已完成全部18输出PDR与独立物理重放；本轮没有重新采用。控制因setup失败被拒绝，没有为它新增完整功能证明或第二次独立物理重放。这是单次开发匹配控制，支持收益不只是原配方本身；不是正式重复实验、最强单项/团队结论或普遍因果定律。

公开EF父身份、原checkpoint注册归档成员SHA、实际route.tcl/read_db及捕获输入字节、完整路由/RCX、原始功耗行、指标与SDK/三类summary已独立核验。原命令运输登记request并在证据归档收集其引用文件，不能将它描述成另行staging了ODB TaskInput。首次审计误要求独立ODB TaskInput，失败保留；r2按既有真实传输验证，没有重跑EDA。

证据：`var/business/a25-gcd-native-recipe-control-20261019/`中的`receipt.json`、`student02-source-review.json`、`native-recipe-script-diff.txt`及`independent-audit-r2/acceptance.json`。

## JPEG：Goal03→ECO原8轮完整交付，但未修复setup

实际ECO会话、原8轮、最终完整DRT/RCX及三类数据交付均结束，原共同PDK与FF/545ps保持。结果如下，不能用GRT阶段的一点WNS改善替代最终PPA。

| 共同条件 | 功耗mW | 单元面积µm² | setup余量ps | setup TNS ns | 布线DRC |
|---|---:|---:|---:|---:|---:|
| 实际Goal03源 | 150.86801350 | 6243.33 | −12.5853 | −0.0701142 | 0 |
| 完整ECO交付 | 151.72357857 | 6243.36 | −12.9088 | −0.170005 | 0 |

ECO仍不满足原setup条件且较该源退化，不采用。动作/探针与逐轮指标保留：不能把它写成“没有运行”，也不把局部估计、原选择门槛或下述记录缺陷之一推断为最终退化的唯一原因。源码保留原评分、动作原语、best-state/backtrace和全布线校准。

现有唯一主管1557962已正常转入新JPEG Goal完整一轮四Student，实际业务PID943596；request指向导出器修复后的配置及精确environment，baseline/parent已实际记录`timing_only/legacy_setup`，没有再把未知模式当已知模式。其后仍是原完整参数域JPEG Flow2×50和72000秒、8/8/12GiB阶段资源。实际状态以`var/business/a25-post-export-continuation-r2-20261019/receipt.json`及公开EF为准。

## ECO发现并隔离修复的两个证据缺陷

实际8轮包含10次原生Codex调用：两次回复验证后重试。原LLM_call只从first/retry选择一份usage，token_log每轮仅一行，导致原迭代表显示8次；分析sidecar和reply原文仍使用primary，而执行Tcl可能来自retry。该错配还会误导后续原生预测校准，必须在正式冻结前处理。

候选228cb150f5bc70238ae9e5927755aa9dceb9ca5b，仅修改：

- `src/LLM_call.py`：分析与执行选中的回复绑定；每次实际模型调用各写一行usage，保留原缓存字段语义及未知金额；汇总头记录全部用量。提示、重试/验证规则、动作、评分和回退不改。顺带清除两条涉及打印的旧F541。
- `src/test_reply_evidence.py`：实际运行单轮driver，验证primary成功、retry动作对应分析、两次调用均入账且未知金额不记零。

旧版本1项通过/2项失败；最终8项模块回归、Ruff F、改动区域/新测试格式、Pyright零错误/警告及差异检查通过。用此次真实10份原始回复离线重放全部8轮，执行Tcl逐轮相同，所选分析与10次成本全部对应；没有新增模型或EDA。原session/history不回写，原始raw日志仍保留每次调用。

候选只发布到ChipEvolve的`modules/timing-eco-agent-a25-retry-evidence`，不推第三方上游；当前主模块4246dc9及活动副本不变。**尚未生产启用**，正式前须在消费者安全收尾后合入、重新绑定精确环境并实际验收。初次隔离checkout遇上游已知缺失LFS基准对象，改用skip-smudge取得源码，不宣称复现了那些缺失基准。

证据：`var/business/a25-eco-retry-evidence-20261019/`中的`baseline-reproduction.json`、`actual-response-replay.json`、`acceptance.json`和隔离worktree。

## 成本与剩余交付

r43闭合12项成功EF任务（ECO会话/最终交付及GCD控制），采样CPU63704.95秒。原ECO10次原生调用均逐事件核对：输入997918、输出22309，共1020227 token；缓存88704是输入子集。原表只记8次，不拿它充当完整成本。新JPEG Goal仍运行，不纳入本次闭合账；旧Goal搜索/构建不重复计算，主推理/服务/导入/审计未知成本不填零。

仍需完成新JPEG Goal、健康完整Flow及真正由Flow结果驱动的后续接力；合入尚未启用的模块修复并完成精确环境验收；取得原生直接专业操作资格，固定各方法充分运行的轮次、来源、模型、停止和成本口径，再运行正式双核心实验。ECO记录修复和本次GCD控制不能替代这些门槛。

## Goal正式模块收口（活动副本不变）

主Goal从c17139f线性快进至7b03c33，已推送ChipEvolve的modules/goalevolve；根gitlink与SOURCE_MANIFEST仅更新Goal一项。保留回退tag a25-before-qualified-main-20261019，不改当前JPEG独立源/配置、原生搜索或服务；其精确环境在主模块更新后已再次检查通过。现有后继Flow配置依旧引用其原隔离Goal源，并未被暗改；后续正式配置再明确绑定主版本。

三项已获资格的修复为：cli.py/contest2026.py保留实际baseline模式并恢复原同模式比较；execution.py提供可选操作资源；candidate_evidence.py区分EPD检索零轮与真正不完整Student。对应三份测试文件随源合入，共七文件；原Teacher/四Student/AST/EPD及筛选算法保持。完整tests回归440通过、3条件跳过、另24子检查，根集成545项全通过，Ruff F、Pyright零错误/警告和差异检查通过，实际记录为goal-main-integration.json及完整JUnit。

首轮unit测试遇本机代理将localhost转发造成HTTP502，保留失败XML，修正测试进程NO_PROXY后通过；随后完整tests（含原发布快照/图谱测试）也通过。桥接代码类型检查使用其实际生产client wheel环境，不能拿不负责SDK执行的原生Goal解释器缺少client-only SDK当源码错误，也未为此给原生环境塞入跨项目源码。

ECO228cb15仍为未启用隔离候选；DPL资源主版本收口、后继完整Flow及真正的Flow结果接力、全部候选而非只看Teacher晋升结果的审核、直接专业操作资格和正式冻结依然待完成。

本轮根文件清单：PROJECT.md记录当前业务能力；ARCHITECTURE.md记录来源/执行边界与收口；TASKS.md保留未完成项和运行入口；SOURCE_MANIFEST.json及goalevolve gitlink固定已发布7b03c33；本报告保存实验及门禁证据。ECO候选两个文件在独立模块分支，未替换活动主版本。
