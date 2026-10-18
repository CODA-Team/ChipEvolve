# A25：Code 后续物理来源不一致的核查与修正

2026-10-18约22:31。DPL完整原生一轮、三份候选的完整物理及数据交付均已完成；当前正式实验尚未冻结或启动。最新重要发现是后续物理模板与原ORFS来源不同，不能直接把现有退化归因给专业算法。

## 实际交付与业务判断

原生Teacher计划、三Student及review全部正常返回，原规则选择Student02；三份稳定源码/编译/原生评价身份、原布局消费、完整DRT/RCX及公开DF/SDK已独立核验。原业务路径失败保留，恢复没有重跑模型搜索。共同FF/545ps测量如下：

| 候选 | 功耗mW | 单元面积µm² | setup余量ps | 布线DRC | 原约束结论 |
|---|---:|---:|---:|---:|---|
| Student01 | 180.43208122 | 6749.74 | 8.5969 | 1 | 功耗、面积、DRC超限 |
| Student02 | 180.38398027 | 6750.60 | 0.53868 | 0 | 功耗、面积超限 |
| Student03 | 179.94214594 | 6747.70 | 6.23751 | 1 | 功耗、面积、DRC超限 |

原功耗上限178.33724618mW、单元面积上限6734.18µm²保持。Codex未采用这些结果，原合法来源保留。原生局部HPWL收益与共同PPA不是同一结论；以下来源差异又限制了上述结果作为算法比较的解释。

## 有证据的默认配置差异

独立核验两份完整归档SHA与公开EF登记，再读取真实5_2_route.log，确认原ORFS实际命令是`-droute_end_iter 64`，Code交付旧模板实际是`-droute_end_iter 5`。不是根据配置文件猜测。两边OpenROAD共同基础版本相同，并不能保证ORFS脚本和默认行为相同。

根因是`delivery.finish→professional.resume_layout`只对已有flow_recipe继承来源；直接ORFS结果有native_inputs却没有flow_recipe，因此退回全局旧flow_template。先前辅助脚本路径修复解决了任务能运行的问题，这一缺口会继续缩减物理能力。

没有简单把5手动改成64：必须继承实际注册ORFS镜像、脚本和原提交配置，否则其他默认行为和物理动作仍可能不同。新旧整个物理来源的影响还要通过匹配控制验证，不能把全部PPA差异单独归因于迭代上限。

另外一项实际EF核查把原生序列化SDC与声明SDC应用在同一注册ODB上：26,511行仅生成时间注释不同，其余26,510行完全一致，且注册归档内原件已核对。这不构成已发现的SDC问题，因此没有新增SDC补丁。

## 隔离候选与验证范围

根候选dfa4f78747ab07dbec24ee5444acda2dfe58e1c6已发布到独立分支a25-registered-source-handoff-20261018，尚未合入主工作树。

- `chip_evolve/delivery.py`：新增内部layout_source接点，新ORFS布局交付复用既有flow_recipe.prepare_flow_recipe→EF准备真实来源，再交给原resume_layout；原生物理SDC、配置和后续来源引用保持。
- `admin/test_registered_physical_handoff.py`：覆盖新来源、已完成准备、同准备任务pending恢复、错误来源拒绝、既有Flow/非ORFS路径及finish真实调用交接。

不改公共函数签名、HTTP/SDK或研究算法。已存在的旧源目录/旧作业继续原绑定，不自动升级历史实验；新重放使用独立key。61项针对检查、482项根回归、Pyright零错误/警告及Ruff/差异检查通过。首次全回归因独立工作树缺少真实模块入口和环境出现7个依赖失败；补入对应提交的入口文件及两个独立wheel环境后通过，没有删改原测试。

这些是实现门禁，真实现代物理控制尚未执行，不能将候选写为运行资格通过。

## 已启动的后续顺序

旧r8续接把Goal原生四Student策略错误表达成不支持的`--candidates 4`，CLI在创建实验前返回2，没有Goal EDA或模型工作。r9只去掉这一参数，保留原生四Student、轮次、原目标和预算，复用已通过的DPL独立验收。

1. r9 PID2656200已正常启动Goal业务PID2656225；真实配置仍是student_1至student_4，Teacher draft/plan正常结束并开始Student01；其后执行原完整域GCD2×50。
2. 来源启用PID2694606等待r9完成后，启用先前来源指纹/线程/阶段资源修复及本次dfa4f78，再回归并恢复JPEG94份成功分支共同事实，原超时失败不改写。
3. 资源资格PID2694607随后做两份10线程/16GiB实际并发构建和完整业务重放，保持原算法及共同数据链路。新源码已包含实际ORFS来源继承，不能沿用旧5迭代物理资格代表新版本。
4. 匹配控制PID3443353只在前序实际通过后执行五份固定布局：原布局→冻结旧模板5；同一原布局→注册来源64；三个原稳定Student布局→注册来源64。固定1,471份旧物理源文件和实际EF布局来源，在隔离dfa4f78工作树经正常包入口执行，不改活动主源码、不调用新模型/搜索/编译。逐项核验实际布线命令、原条件、最终PPA及DF/SDK，保留成本和不合格结果。准备和干运行通过，当前只是等待。

真实控制、最终候选完整PDR/独立重放、真实专业接力与预算校准仍需完成，然后才能冻结A25并执行A26–A28。JPEG继续作为开发/校准设计。

## 权威证据

`var/business/a25-jpeg-matched-control-20261018/`：registered-route-policy-difference.json、sdc-probe-receipt.json、sdc-canonical-interpretation.json、registered-source-acceptance.json、matched-routing-specification-r2.json和matched-routing-receipt-r2.json。

原三候选数据验收在`var/business/a25-dpl-operation-resources-20261018/selected-route-recovery-r1/independent-acceptance.json`；当前续接见该目录上层CURRENT.json。本报告只涉及上述两个候选源码文件、私有实验脚本和文档，不部署用户DF/DI/evaluation修改或触碰其他会话。

## 22:57续查：实际Goal输入与等待程序启动修正

对当前Goal的Teacher两次调用及四Student逐份核查：六份实际prompt中的完整Query包与本轮输入完全一致，绑定原JPEG来源、目标和条件；四份候选的六项已提交构建请求，各自701份声明源码均与工作区实际SHA一致。每份候选相对原共同源码的变化仅在其原生计划指定的RepairPowerPolicy.cc。公开EF的实际请求同时保留同父run、目标、条件及上下文身份。该检查证明输入确实送达、提交的源码对应实际文件；不把prompt送达等同于模型正确理解或最终PPA成功。

上述六次已完成模型调用的原始事件与收据用量一致，均无观察到的追踪错误：已知输入3,645,808、输出75,724，合计3,721,532 token；缓存输入3,202,048属于输入子集。Teacher最终评审、后续强化、物理执行、数据服务和主宿主推理尚不在这份模型子账本中，整轮尚未完成。

新复现的后续启动错误发生在私有验收程序，尚未发生于真实94分支恢复：post-r3原计划直接执行var目录下的audit_timeout_flow_delivery.py，连`--help`也会报ModuleNotFoundError: chip_evolve。修正为从项目根cwd用runpy执行原核查脚本；从新程序AST提取的实际参数列表已通过真实导入和参数解析。没有增加PYTHONPATH、软链接或跨项目源码导入。

确认原三个监督程序均仍处于等待、没有子进程和任何派发后，仅停止并替换这三个本轮程序：post-r4 PID3684493、qualification-r4 PID3684494、五组固定布局控制r3 PID3684495。旧脚本、清单和回执原件保持，另存停止身份/原回执SHA/替换差异。新旧逐字段比较确认：R9命令、候选提交、算法、业务key、两份构建和五个控制、各自预算及原等待截止时间全部保持；仅核查调用方式和监督引用路径改变。三份新准备干运行、Ruff格式/F检查、实际子命令启动及启动后等待状态通过。

当前R9 PID2656200及Goal业务PID2656225均继续原计算，未被暂停或重启；活动77份输入及26份用户文件哈希保持。Student04正在真实LTO链接，其余三个构建因32GiB预约占满本池而等待，链接进程仍有进展；不是已发现的任务丢失。整轮构建资源峰值及队列成本仍须在终态后核验，不能现在降低预约或报告并发提速。

本次未修改产品/专业源码或服务，因此不重复全仓回归争用正在运行的链接任务；既有482项根回归与来源候选静态门禁的适用范围保持。新增证据为`var/business/a25-dpl-operation-resources-20261018/goal-live-input-audit-r1/acceptance.json`和`var/business/a25-jpeg-matched-control-20261018/waiter-launch-correction-r1/`。真实来源控制、完整专业接力、证明/重放和正式预算冻结仍未完成，A25–A28继续。
