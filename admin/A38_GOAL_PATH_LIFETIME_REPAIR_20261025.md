# A38：Goal 原崩溃配方修复与短回归

基线为根 `4fad9ed`、Goal `45efa72`。本轮只处理已出现的 C++ 路径生命周期错误；不启动 Teacher/Student 搜索、模型调用、完整 DRT/RCX 或功能证明，不更改历史实验、公共接口、服务和资源容量。

## 业务阻断与修复

GCD/Nangate45 原 measured 策略曾在两种 RC 模式下分别于第 3/9 次提交之后触发 STA assertion/SizeUpGenerator 崩溃。源码核查找到两个具体问题：候选动作试运行及回滚后继续借用旧 STA Path；候选保留 `Target` 引用，但局部目标数组先于最终提交销毁。

新私有源码仅改 `MeasuredCriticalPathPolicy.cc/.hh`：每个 generator 使用原先选定 driver 的当前有效路径；胜出候选持有其 Target 至提交结束；失败试运行回滚后刷新时序。原七类动作、目标排序、评分、接受/拒绝、40 次动作预算与 RC 策略保持。原非 measured 的专业 TNS 机制保持。

发布资产为 Goal 模块的 `toolchain/patches/fix-measured-policy-path-lifetime.patch` 和同目录 README。补丁基底与重建说明明确；只应用于未来私有源码，不修改冻结 lineage 或运行副本，也不默认启用 experimental measured 策略。

## 真实 EF 短验证

| 检查 | EF run | 实际结果 |
|---|---|---|
| 原 global-baseline 崩溃脚本 | `run-d0a253d9c72343d8bd0ab160d5a093f9` | exit0，52.44 秒，40 次 SizeUp 提交，完成标记/原输入时序核验通过 |
| 原 native-incremental 崩溃脚本 | `run-cb608dfd76494a389ad860e5c04cf700` | exit0，4.46 秒，35 次提交，含两次 Reroute，完成标记/原输入时序核验通过 |
| 原非 measured TNS 控制 | `run-6947cab22c8447c291c25afff6deb55f` | exit0，1.02 秒，五阶段全部 25 数值及输出网表与原控制完全一致 |

两份崩溃脚本只替换输出目录、增加完成标记，实际设计输入、250 ps 原 SDC、全部环境策略与七动作序列保持。旧失败 `run-3a42613543f24465b3e4a6a84a076de5`、`run-e273220677fb4e06b1435d17420bb6cd` 不改写。脚本仍保留 40 次预算，35 次是策略自行结束，没有缩小动作数。

**这是崩溃回归，不是新 PPA 收益。** 两份结果末端诊断 TNS/WS 分别为 −8.097768/−0.188635 ns、−7.771219/−0.175375 ns，尚未闭合；RC 模式、原 SPEF 输入时刻和动作后的估计/合法化不同，不能把它们当最终 DRT/RCX 结论或采用。下一轮业务按已有 500 ps 条件另行建基线，这里没有替换原条件。

## 代码与来源检查

重建通过 Goal 原生 COW builder→公开 EF，不直接在宿主运行 EDA。新二进制 SHA256 为 `e4ba970b3edd091d90b32fd691e353c59a92414955e8aa5b902e4a0f5e0500d0`；701 源文件清单、二进制及构建回执绑定通过。AST 用原 RepositoryGraphIndex 重建，160 文件/1989 符号。clang-format 检查、补丁可应用及结果 SHA、六项原策略差异检查通过。原源码及 26 个用户保护文件哈希均保持。

模块回归第一次受到宿主代理干扰，本机 dashboard 测试 HTTP502；原失败日志保留，后续只为测试进程清除代理并走 loopback。去代理后的单元与 artifact 全套 exit0；单元 441 通过/3 原条件跳过，既有 29 子检查保持，见 `module-unit-sanitized.log`、`module-sanitized-regression.log`。根产品源码没有改变，根业务复用 A36 的 658 项通过结果。

证据在 `var/business/a38-goal-path-lifetime-20261025/`：`source-repair.json`、`built-binary.json`、`AST-repair-receipt.json`、`source-policy-and-patch-review-final.json`、`policy-short-verification.json`、`original-tns-regression.json`、`code-check.json` 和各 EF 原件。诊断驱动最初的输出目录准备错误在派发前已纠正，原版本保留，未重跑已完成工具。

## 仍需继续处理

七份 A36 Goal 模板仍选择旧共同源码、没有显式构建 donor；Ariane/Nangate45 已有 TNS restoration，但没有本次寿命修复。下一切片将核查并修正未来任务的源码/构建 donor/read mount 绑定，使用现有接口，不热切历史。Ibex/Nangate45 完整证明、Ariane 全链和八组双次最终 PPA 仍未完成；长搜索保持暂停。

提交检查点：Goal `d41efa2`（补丁与说明），根仓库仅固定该模块、来源清单、本报告和状态文档；无根产品代码变动。公开补丁将空白 diff context 规范化以通过 git diff 检查，已另行实际应用并证明产出的两份源码 SHA 与编译/复测完全相同。
