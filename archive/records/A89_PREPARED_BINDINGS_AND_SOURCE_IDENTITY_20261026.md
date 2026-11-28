# A89：八组待用绑定核查与 Goal 源码身份修复

根基线 `f883ee2`、Goal基线 `33661a5`。**八组待用入口核查通过；一项真实来源记录缺陷已修复。** Goal提交 `0ca32cc`，未来冻结使用新控制代码，历史实验与配置不改。未恢复长搜索，没有新EDA、模型或PPA结果。

## 核查结果

以A73 `prepared-bindings.json` 的八份配置为准，逐项核对：

- 原八配置SHA保持，设计/PDK、时钟、SDC、库SHA、原campaign参数及资源不变；GCD/Nangate45保持老板批准的500ps，ASAP7的310/545/900ps及其他Nangate条件保持。
- EF `41151`、DF `43789`和共同镜像绑定一致；关键源目录、解释器、模板、PDK和候选源码路径存在。不是仅查看同名文件或旧PID。
- A72原专业源码 **701份文件** 与已验证构建逐SHA匹配，原二进制SHA仍为 `275790d63baa00404494f8fd7b707e19d463d6ac7ae65edeef863aec1d0e3da6`，不重编译未变C++。
- Query实际安装包 **97份源码** 与正式源码逐字节一致，保留字面venv路径，不将解释器软链接resolve到基础环境。
- 使用根业务真实 `freeze` 入口冻结Goal和ECO，关键源码与正式版本同SHA；A79功耗、A86对象定位、A87报告修复在新副本中保留。
- 八组分别用准备配置中的Query解释器，经DF/DI读取指定历史run/snapshot的setup WS，全部原值/精确scope通过。**这是入口短验证，旧250ps等历史结果不成为新500ps基线或本轮合格优化。**

Goal的推理解释器与确定性委派client解释器分工保持。数据SDK实际在后者运行；不因前者未装该SDK就错误宣称委派失败，也未额外安装包。

## 实际缺陷与定点修复

`platform.execution.toolchain_evidence` 在无自身Git元数据的源码副本内直接 `git rev-parse HEAD`，Git会找到上层ChipEvolve仓库。真实A72源码目录没有 `.git`，原函数却把根提交 `f883ee2420ea6d21930882bcd6760472d77eaad9` 返回为 `source_git_commit`，与源码含义不符。

只在源码目录本身为 `git rev-parse --show-toplevel` 时记录HEAD，其他情况保留现有可空字段。真实冻结副本修复后返回 `source_git_commit=null`；源码文件哈希与已验证二进制收据仍提供准确身份，没有填造提交。真实独立Git仓库和worktree仍返回自己的提交。只修未来来源记录，不回填或覆盖历史。

| 模块文件 | 职责 |
|---|---|
| `goalevolve/platform/execution.py` | 仅改平台来源Git根判断；原EF版本查询和二进制收据保持。 |
| `tests/unit/test_platform_source_identity.py` | 五场景：嵌套无Git源码的显式/默认入口、独立仓库、worktree、独立无Git快照。 |
| `tests/unit/test_platform_codex.py` | 原版本查询测试使用真实两阶段Git响应，并明确非空结果；继续验证版本调用经EF。 |

数据流仍是原专业控制 → 已安装client/EF → 原工具 → DF/DI/Query。公共函数签名、字段类型、source_files验签、算法、评分、目标和晋升不变。AST比较确认除该函数的Git判断外所有模块节点相同，该函数中原EF版本查询部分也相同。

## code-check 与交付

新回归在旧实现 **2失败/3通过**，修复后针对集 **14通过**；Goal全回归 **479通过/71子项通过**，根接点 **39通过**。产品/测试/两份私有脚本lint、格式、Pyright通过；桥接脚本按client环境检查，测试按Goal环境检查。已有文件仅格式化改动区域，未重排整个模块。

根产品Python未改，复用A82同源 **754项根回归**；26用户保护文件、generic_agent.py、DF/DI WIP和生产服务保持。模块推到ChipEvolve `modules/goalevolve`，保留上游来源，不推原研究仓库。根只更新gitlink、manifest的Goal commit/tree、本报告、STATUS、A54和TASKS。

证据目录 `var/business/a89-prepared-bindings-source-identity-20261026/` 包含修复前后真实身份、冻结源码、701文件/二进制与八组绑定核验、八次Query原文、完整回归和 `code-check.json`、`continuation.json`。工程检查通过，老板业务验收独立。

`long_search_ready=false` 保持。下一项从GCD/Nangate45已验证500ps来源核对原Goal联合策略的真实baseline与固定原生接续，先核来源和构建收据，只做有界验证，不恢复Teacher/Student长搜索。Ariane最终电气/ASAP7 setup、GCD完整协作、八组双次及DF实际大写入延迟仍未关闭。
