# A29：邀请论文案例施工

老板已批准五切片计划：固定 GCD 成果、补齐四专业实际参与、按需扩展 ibex/jpeg/ariane、展示平台操作、汇总论文素材。GCD 优先，10/22 晚目标收口，10/23 前交老师审阅；不以全平台审查清零、完整统计配对或独立 AES 证明为前置。

## 切片一：已完成工程修改，实际业务验证进行中

- Goal 构建归档器修复 `d5a3a95` 已快进合入模块主版本并推送；新实验绑定该正式来源。原有 GCD 结果与验证不重跑、不改写。
- `chip_evolve/native.py`：Goal 原生 TNS 目标读取业务限制（本轮为零），功耗仍沿用原 10% 搜索目标；读取已存在的物理内存配置；ECO 显式八线程，并在新交付记录中声明已完成详细布线。
- `chip_evolve/delivery.py`：只有明确声明已详细布线的新记录走保留布线路径，原检查点保持原语义。
- `chip_evolve/physical.py`：对已布线状态运行 DRC 检查/RCX/共同测量，不清线或重新布线；GRT 检查点仍完成原详细布线。物理任务读取既有设计内存声明。
- Flow `162b80a`：保留 CLI 结构化失败或显式 Error 行，脱敏凭据，不再把所有错误统一写成检查登录。无原生算法/采样/模型重试逻辑改变。

没有新增 EF/DF API、SDK schema、服务或数据库，没有改专业评分/晋升。根新增 `admin/test_invited_paper_relay.py` 覆盖目标与布线交付；`admin/test_eco_pdk_binding.py` 实际执行生成的 launcher，核对显式线程参数。

## 工程验证

- 根当前已跟踪测试及本轮新增测试：549 通过；30 项针对检查通过。
- Flow：从原 flow 工作目录运行完整 test，97 通过。
- Goal：tests/unit XML 450 项，失败/错误 0，原跳过 3；完整 tests 扫描在第三方发布大目录 I/O 上过慢后中断，保留原日志，没有冒称发布产物全审查通过。
- 根产品/新增测试 Ruff、格式与实际安装环境 Pyright 通过。Flow Ruff F 通过；新增函数单独格式化，未批量重排旧代码。整文件 Pyright 仍报告原有四处类型诊断（transport 可空、schema 推断、isfinite 类型、动态 worker 属性），不把它们变成本轮无关重构门禁。
- 首次根/Flow 检查分别遇到旧 Toolkit wheel、缺 Runtime 测试依赖和工作目录错误；已在本轮独立环境安装本机已有 wheel、使用正确模块目录后通过。生产服务和用户 DF/DI 工作树未更新。
- 26 项用户保护文件 SHA 一致；跨模块依赖保持安装 wheel/公开 API。

证据目录：`var/business/a29-paper-delivery-20261020/`。新增本轮独立配置、输入引用和测试环境，不修改历史 runtime。模块提交不等于真实新接力已通过；后续记录实际 EF、PPA、DF/Query 和采用状态。

## 下一步业务验证

1. 已有 GCD routed 产物通过 EF 做一次保留布线的 DRC/提取/测量，确认交付不改变线路。
2. GCD Flow2-37 的原布局检查点启动 DPL 一轮三 Student，复用实际 Query 证据；再对其产物诊断并交给 Goal 一轮四 Student、ECO 最多八轮。
3. 同步准备 ibex/ariane 的实际 RTL/SDC/ORFS 配置，JPEG先复用已有可用候选。平台记录统一，不要求无收益候选成为最终祖先。

本报告后续只补业务结果；不把“已接受排队”写成优化成功。

## 审查反馈后的实际收口

- 老板已明确批准停止旧 JPEG 剩余搜索。核验原 supervisor PID/start ticks 后，仅停止该树 14 个进程；公开 EF 对其 3 个活动任务请求取消，全部完成结果保留。没有停止 EF/DF 服务或其他人的计算。
- GCD 新 DPL 已通过原三条基线并进入一轮三 Student；G03 的 Query 已完成4事实/4假设，实际定位 reg2reg 关键路径及驱动12负载的小 SLVT 反相器。G03→ECO最多8轮已提交；保留合法G02，独立新runtime的select已复用其原18输出PDR/重放验证完成，不重复证明。
- 修正本报告上节的初版功耗目标口径：平台不再生成通用×0.9目标，直接保留各实验专业模板声明的功耗目标，只映射业务TNS限制。本轮新GCD模板显式声明原目标函数的功耗最小化方向（零理想点），这是优化方向，不是声称零功耗可达或最终约束。
- 新保留布线分支增加“输入存在信号线”检查。第一次实际EF验证发现最新版工具把check_drc放在drt命名空间；修正为drt::check_drc后真实提取/测量/DF交付完成，组件、线路、引脚DEF段完全一致，七PPA精确同值。
- 该独立checker对同一G02返回5377个marker，而原详细布线流程报告0；不能把两者当同种指标。ECO模块090f866在原生best选择时记录当次DRT计数，导出与最终ODB SHA绑定的原件；平台保留原计数，独立checker值作为补充诊断。它的物理含义尚待专项核实，不宣称独立DRC检查为零。ECO原评分、best选择和回滚未改。
- 补充NOTICE明确ASU-VDA-Lab来源和原提交；没有虚构或替第三方授予许可证。
- 新根回归551通过；ECO15项通过；根/相关ECO产品与测试静态、格式、类型检查通过。
- ibex实际Slang综合完成，因绑定全VT库但原配置只加载RVT LEF而失败；新配置显式加载RVT/LVT/SLVT。为落实GCD优先，已收尾本轮自己的ibex并保留证据，相同配置在ECO前端结束后自动继续，不称原样默认ORFS。
- Ariane原研究ASAP7 placed基准和SRAM模型已找到并准备：210295组件、136 SRAM实例、21 Liberty和11 LEF。它不是原样ORFS RTL基准；尚未派发导入/布线，不把“缺ASAP7原生ORFS配置”误写为“所有PDK资料都缺失”。
- 四设计论文素材开始持续导出：[当前指标与接力图](INVITED_PAPER_RESULTS_20261020.md)、[11节点完整指标CSV](INVITED_PAPER_METRICS_20261020.csv)。新增DPL/ECO计算未终态前不填新PPA。

运行与取消回执、原失败和全部成本记录仍在本轮var目录。用户新提供的DeepSeek独立审查文档保持原样，不提交它或其他用户修改。

## 小设计资源接续与同一 Codex 的 Query 展示

- 本轮根 `native.py` 只向 ECO 私有运行 profile 传递 `session_memory_gib`，模块 `platform_execution.py` 将其映射为既有 EF 内存申请；默认仍24GiB，本轮GCD显式16GiB。八线程、八轮及原生算法不变，JPEG不套用GCD设置。当前两项DPL各8GiB占用16/32GiB，旧ECO24GiB排队属于正确资源等待；配置准备期间DPL一项构建完成，原ECO已按24GiB实际开始；保留这份正在运行的原case，不取消、不重跑，新选项仅供后续实验。未修改冻结现场或杀掉DPL构建。
- 根552项回归、ECO15项回归通过，两个接入文件和相关测试Ruff/格式/Pyright通过。首次误用旧模块venv缺Toolkit/pytest，改用本轮已安装公共wheel的独立测试环境；没有改生产环境或将测试依赖故障写成业务故障。
- `same-codex-query-demo-r2` 已由当前Codex用现有`--model host`完成两次实际DF事实读取及证据回答：保留G02，G03作为ECO探索分支；额外Query内部模型调用0，父Codex推理token未单独计量，不声称总token为零或节约百分比。两读取及初始化墙钟约1.346秒，回答另有原回执。
- 论文CSV把正时序余量列更正为WS，并另列规范WNS=min(0, WS)；没有修改原PPA数据。

## GCD G03→ECO 八轮：完成执行与数据交付，按原约束拒绝

实际最终共同测量：功耗0.77087164391mW，cell/core/die面积38.9432/57.9701/75.8293um²，setup WS−32.4331ps、TNS−0.264783ns，hold WS+34.9914ps、TNS0，slew/cap/fanout/布局违反均0，原生DRT计数54。相对G03，绝对setup TNS减少69.0726%，但时序仍未闭合、功耗略升、DRT违反原约束，不能采用；合法G02保持。独立checker5924另列，不与原生DRT混为一谈。

七项最终原件与公开DF/DI SDK逐值核验通过；新ECO自身原生DEF与共同交付DEF的COMPONENTS、NETS、PINS逐段完全相同，交付没有偷偷重布线。原生会话8次模型调用，输入800212、输出16873token，cached64768为输入的子集；不包含先前Flow/Goal/Query，货币费用未知。

本轮实测发现原控制器循环末尾才建立outputs目录，导致此前best写报告失败，但best ODB已正确保存。没有修改正在运行的源码：只创建运行输出目录，从最后一次best选择的原始控制台块恢复唯一原生计数54，并记录当时best ODB SHA；后续没有更好的best。恢复记录已实际随EF data_snapshot归档登记，重新取回核对SHA与best身份通过。不是推测零，也不是新跑一次路由。future模块67889a6在叶任务启动原循环前建立输出目录；缺原生计数且产物已变更时禁止继承baseline计数。17模块回归/静态类型通过，原研究动作与排名未改。

证据：本轮`gcd-eco-final-acceptance.json`、`gcd-eco-comparison.json`、`gcd-eco-native-model-cost.json`、`eco-native-counter-recovery.json`。拒绝候选不新增昂贵功能证明。ibex已由原守候程序实际接续；DPL仍在原生Student试验中，不能把首轮编译/评价通过写成整轮完成。

## 已布线与已收敛的交接区分

进一步回到原脚本和真实日志，确认ECO每轮实际为`detailed_route -droute_end_iter 1`；注释中的FULL不能当作完整迭代收敛证据。这解释了为什么原生候选仍有54个DRT违反，不能据此宣称专业策略无效或交付完整。

未来`delivery.py`只在明确详细布线且原生DRT=0时保留线路；原生DRT非零/未知的检查点继续既有完整DRT/RCX。没有改专业迭代次数、选择或重写原结果。新增针对原生0、54和unknown及两个设计的交接回归，根556项及Ruff/格式/Pyright通过。当前ECO原生实测结果保留，另开“ECO→完整布线补全”子实验；分别报告原生动作与补全影响，不把补全收益全归给ECO。

## ibex基线完成与Ariane配置准备

ibex完整ORFS已完成：FF/900ps下29.243746772mW，cell/core/die面积2403.75/5330.16/5961.54um²，setup/hold WS+25.478/+25.4172ps，setup/hold TNS0，slew/cap/fanout/布局/原生DRT违反均0，三事实快照已入库。它是显式多VT库配置的ORFS基线。Query实际完成4事实/1假设，支持降低早期功耗回收强度的探索；由当前Codex核实原源码已支持的20%设置后，实际派发Goal一轮四Student，保留Teacher/AST/EPD和晋升规则，未提前宣称新收益。

Ariane原DEF已核实136个SRAM实例是FIXED，原顶层时钟尚未经过CTS。已核实共同ORFS支持`SYNTH_NETLIST_FILES`和`FLOORPLAN_DEF`，可从原映射网表及楼层规划继续，不替换CPU RTL。根`physical.py`允许内部设计绑定提供`orfs_config_template`，把该文件及原有overrides写入已存在的staged design.mk，现有设计保持include逻辑；不新增CLI/EF/DF接口。`test_orfs_resource_binding.py`覆盖默认/显式配置、资源、SDC和配置源不变，18针对/559根回归及静态格式类型通过。准备`local-ariane-orfs.json`和原映射配置；32GiB完整大设计任务暂不抢占GCD专业实验。

ECO完整布线子实验已完成：原生DRT54→0，最终0.77061523916mW/38.9432um²，setup WS−32.4934ps、TNS−0.266838ns；时序仍不合格，继续拒绝，G02保持。原生结果与补全结果分列，不重复调用模型。

## 本次检查点：交付与剩余任务

|切片|当前状态|剩余|
|---|---|---|
|一 固定GCD起点|既有G02及原18输出证明/重放保留；保留线路交付真实验证完成|不重复相同证明|
|二 GCD专业协作|G03→ECO八轮、原生事实、独立布线补全与拒绝记录完成；DPL首两个Student完成首试后正作原生调整|收取一轮三Student及原Teacher结论，再从实际选中布局进行Goal接力|
|三 扩展设计|ibex完整基线/三事实/Query完成，Goal实际进入EF；JPEG可复用记录保留；Ariane原布局导入通过、映射网表完整ORFS配置准备好|完成ibex专业结果；GCD资源后启动Ariane32GiB完整基线；不重开旧JPEG搜索|
|四 平台帮助|同一Codex的Query事实读取/证据回答和真实专业派发链已有记录|不填写未测量的token节约率|
|五 论文素材|14个SHA核对实测节点及CSV、Mermaid；本机生成架构/GCD接力PDF与SVG|随真实专业结果增量更新，四设计尚未全部结束|

ibex最初启动参数误带只适用于Flow/DPL的`--candidates`，CLI在建实验/发EDA前拒绝；已移除该参数，按原生固定四Student重新启动。实际准备/工具身份任务`run-9375cdbcbd064101802758ff13c5e37e`已running。不把前端参数错误掩盖成一次成功实验，也没有重复物理计算。

本次文件清单：根产品`chip_evolve/{native,delivery,physical}.py`；针对回归`admin/test_{eco_pdk_binding,invited_paper_relay,orfs_resource_binding}.py`；ECO模块`src/{platform_execution,platform_drc,test_platform_execution,test_platform_drc}.py`及`PLATFORM.md`；固定版本`SOURCE_MANIFEST.json`和gitlink；项目资产`ARCHITECTURE.md`/`TASKS.md`；本轮A29执行/操作记录与GCD既有追踪、论文结果/CSV。各自职责在上文对应段落中说明。其他用户文件保持原样。

可直接查看的本机图：`var/business/a29-paper-delivery-20261020/paper-assets/chipevolve-architecture.pdf`、`gcd-measured-relay.pdf`，同时保留SVG及DOT源。图中未完成DPL仍为虚线，不冒充四专业连续成功。

## 本轮续作：原生策略校准、已完成候选提前交付

- ibex原生初始timing-only测量/构建成功，但受保护power-only阶段的同源码基线产生469项slew及1项cap违反（原生聚合DRV469），原控制器在Teacher启动前按原规则拒绝。完整ORFS源基线仍合格。保留失败及成本，使用现有`power_stage_protected_rounds=0`进入原adaptive_tradeoff/power_then_timing，继续20%回收、一轮四Student和相同晋升类/电气门禁；新r2阶段已实际运行，不改研究源码或硬约束。
- JPEG旧完整搜索保持停止。复用已测量可行Flow slot10（原始SHA6456bbea…），只通过既有EF/PDR接口补全部27输出的功能证明；原本未证明/未采用的口径在实际证明结束前保持。不重新搜索或优化，不声称公平预算优势。
- GCD Student01原生门禁已完成：530.9um HPWL，较Diamond原对照536.9下降1.1175%，较framework基线531.9下降约0.188%，runtime3.191s/原2.327s，原2倍预算内、布局合法。通过原项目只读candidate_evidence导出，eligible=true、problems=[]；Student02尚未结束并被原门禁正确排除。平台单独交付已结束Student01，不改变原生Teacher选择；第三Student继续原程序。
- 实际发现根`resume_layout`未将已有设计`orfs_execution.memory_gib`传到CTS/route_finish；本轮GCD声明4GiB却申请默认24GiB，任务真实queued且只剩4GiB可用。`professional.py`仅补传原字段，默认24保持；源阶段SDC、8线程、算法和物理步骤保持。`test_flow_recipe.py`将原时钟继承测试扩至默认/GCD4GiB/ibex12GiB，27针对及563完整回归通过，产品/涉及测试Ruff、格式、Pyright通过。三个既有SimpleNamespace测试桩增加显式cast以满足文件类型检查，不改变测试行为。

## 2026-10-20 16:03：DPL第一份最终测量、真实后续与审阅快照

- DPL Student01已由原只读导出器确认eligible，公开EF完成CTS/route最终测量（run-ad5a14082d164feb8cb90f7b7bf0c33c）：0.93751552049mW、cell44.9793um²、setup WS+10.4943ps/TNS0，原生DRT及电气/布局违反0。它的原生HPWL530.9um优于Diamond536.9um，但最终功耗和面积比F37更大且超原面积上限，不采用。原Teacher仍在等待另外两个Student，不把提前测量称为原生获胜者。
- 原4GiB配置已被真实CTS/route消费，峰值分别454307840/872058880字节；完成后七项PPA通过公开DI SDK逐项核验。先前仅排队的24GiB错误预约已取消并留回执，没有重算已完成物理任务。
- DPL01的真实Query完成4事实/3假设，诊断局部HPWL与最终PPA冲突，产物/证据与上下文固定。随后新增原生1轮4Student的Goal探索，保留80% GCD回收，使用原有adaptive_tradeoff/power_then_timing模式，不改筛选或硬约束；G02始终保留。当前阶段基线和Teacher draft已完成，Teacher plan进行中，不能填未完成收益。
- DPL原生门禁、HPWL、源码引用和最终比较已以现有candidate-brief格式注册到EF（run-251bcd0008b84ee3b5d0461593f2e3b9，art-ccc455b49114426c91279ab20e58a7ba），并实际从公开SDK取回核对SHA。它在已完成Query之后登记，不回写旧签名上下文。
- ibex adaptive原一轮四Student已实际规划并进入源码构建/评价。阶段基线仍有原电气违反，只有最终候选通过原门禁才能成为新结果。JPEG旧搜索保持停止；新的Flow10功能证明因8GiB预约不足中止，24GiB重试配置仅准备好，未派发。
- 论文表已增至15份SHA核对的最终测量结果。已有G02原验证、输入17项SHA、18输出PDR/1整体分区、零未证明点、独立DRT/RCX七值同值及SDK身份已重新核对；这是复用原证明，不是重跑。
- 已生成本机老师审阅快照`var/business/a29-paper-delivery-20261020/paper-assets/teacher-review-snapshot-r1.zip`：53文件/330503字节，含15原始结果JSON、完整CSV、两种GCD接力图、架构图、采用/验证与平台调用证据，逐成员SHA及ZIP完整性通过。快照明确GCD合法主线、拒绝侧枝、进行中任务和不同综合来源的比较口径，不声称四设计或四棒连续成功。

本次只有论文结果MD/CSV、本文、平台操作记录和项目资产状态更新；没有新增产品代码、服务、接口或实验数据库。运行中的冻结源码、JPEG已完成结果及用户DF/DI/ablation修改保持原样。

## 论文阅读版与成本范围补充

三页本机阅读版`var/business/a29-paper-delivery-20261020/paper-assets/teacher-review-overview-r2.pdf`包含15节点完整数值概览、架构和GCD真实接力图；PDF实际渲染后检查中文和表格，首版字体映射失败已用Type3重导出，交付r2。ZIP r2新增该PDF，共54文件/436431字节，逐文件SHA与压缩包完整性通过；原r1快照保留。

当前离线成本快照`cost-snapshot-20261020T080903Z.json`从已有EF公开执行回执去重94任务：89成功/3失败/2取消，采样CPU合计22826.46秒，8项operation提交尚无闭合执行回执；有记录的12次原生Goal调用输入7444904、输出132101token，cached是输入子集。它不含先前Flow/Goal、当前未结束调用、全部DPL模型成本、服务开销或宿主推理；不当作全场总成本、节约比例或失败均由平台导致的结论。ECO原8调用另有独立范围记录。

## 原生构建收尾与ibex阶段诊断（时间见原回执）

ibex四Student共8项已观察到的链接操作全部成功，按Student分组及最新回执保存在`ibex-four-native-links-verified.json`；没有将“4 Student”误算成“只有4次链接”，也没有据此宣称完整功能验证或最终PPA已通过。当前GCD两项链接实际运行，DPL两项24GiB评价仍等资源；原前端身份均保持。

通过公共`EdaAiClient.artifact_bytes`取回已成功Student04原生物理叶任务`run-b621057ae0654e97910f9ad081aeb6de`的311877字节日志，与EF登记SHA逐字节一致。实际TNS序列：源0 → 功耗回收−6.97113764223ns → timing修复−0.015354828954ns → 布局−0.103289768551ns → 全局布线/寄生估计−23.0848591221ns；原报告最终表中469条slew、22条cap违反。源码和实际执行Tcl都表明该原生配方最后一次repair_timing发生在详细布局/global_route之前，后面只估寄生并测量。

这定位的是原生阶段测量变化，不是对某个参数的唯一因果证明，也不是最终DRT/RCX指标；原始字段虽名为tns_abs_ns，日志值实际有符号，本次按原符号保留。证据及作用域见`ibex-student04-native-stage-diagnosis.json`和SDK取回日志。下一步仍收齐原一轮四Student，按已有门禁交付可测检查点，再通过共同测量/DF/Query决定是否将真实布线后的时序债务交给ECO；不为消除负结果改写Goal原生流程或晋升规则。

同一已登记日志实际出现Student04自定义`last_gasp_single_epoch_entered/changed/refreshed/retained`信号，各两次正值1，与Teacher指定机制相符。这证明候选钩子在真实EF工具执行中触发，不能据此推断QoR改善或已获原生晋升。

## PPA论文图件增量

已从15节点CSV选择6个已完成GCD节点，逐原结果SHA及相同condition/objective核对后生成`paper-assets/gcd-ppa-observations-r1.pdf/.svg`。图中保留B0方法来源区别、F37→G02实际增量、DPL01面积拒绝及G03→ECO→独立布线补全的时序拒绝；横向排列不表示连续接力，完整数据仍在CSV。已检查PNG与实际PDF渲染，修正原面积上限标注与数值重叠。四页阅读版`teacher-review-overview-r3.pdf`在原架构/接力/指标阅读版上加入这张图。没有新跑EDA或将未完成候选加入指标。

阅读版和原件已汇入`paper-assets/teacher-review-snapshot-r3.zip`：63文件、560392字节、15份完成节点，逐成员SHA和ZIP完整性通过；新增方法/英文图注、PPA矢量图及其源数据元数据、ibex原生阶段SDK原日志/诊断和四Student链接回执。`cost-snapshot-20261020T085245Z.json`只覆盖106份已闭合EF公开执行回执，已知采样CPU26300.96秒、7项operation尚未闭合；模型12次Goal调用范围与上次相同，不能当作全场总成本或效率节约率。

## JPEG历史接力图与父子核验

已生成`paper-assets/jpeg-measured-relay-r1.pdf/.svg/.dot`：JB0→DPL Student03和JB0→Goal03→旧ECO为真实分支，Flow10为单独保存结果。5结果原件SHA及共同条件/目标通过；另外逐个读取原DPL/Goal/ECO实验input-receipt，实际source结果SHA与所画3条父边逐项一致。图已检查实际渲染，原面积上限6734.18um²保持，DPL多0.91um²仍拒绝；Goal/ECO时序负接力保留，旧ECO交付包括重布线标明。没有重开JPEG搜索，没有给Flow10补造父边或功能通过结论。原数据及父收据路径/SHA保存在该图metadata JSON，图生成脚本每次都会重核。

## ibex两个原生策略的实际结果重合

已通过DI分别取回Student03/04已成功物理叶日志并与EF登记SHA核对。规范化输出目录后两份实际Tcl完全相同，环境变量键值相同，源文件身份字典仅`SetupLastGaspPolicy.cc`不同；两个二进制SHA和inode均不同，原日志各自有对应`last_gasp_frontier_*`及`last_gasp_single_epoch_*`正值信号。完成的本机`post_route.odb`、`post_route.v`、原生DEF及checkpoint_metrics四份产物分别逐字节同值；两者原生全局布线估计均TNS−23.0848591221ns、469 slew/22cap违反。

这是两个已执行策略在本次输入上落到同一设计状态的证据，不能计作两份独立收益或用它代替最终共同测量。其余两个Student作用于功耗策略，原一轮四Student仍继续；新实验只有在有明确不同动作/诊断依据时再启动。原控制器仍负责原生晋升，最终采用另按共同PPA/功能证据判断。完整比较、源码/二进制身份和原件引用在`ibex-two-native-physical-comparison.json`，未修改任何活动源码或实验记录。

## 新增Flow→DPL→Query→Goal：完整验证通过

原Goal一轮四Student及所有交付完成，原控制器晋升Student01；原候选源码/检查/原生评分均保留，未改专业晋升。共同最终结果`run-13f4b205b4594b1eafb9867662fb3a9e`：0.81929122098mW、cell/core/die 39.6139/57.9701/75.8293um²，setup WS+1.31586ps/TNS0、hold WS+34.0384ps/TNS0，DRT、slew/cap/fanout及布局违反0。相对实际DPL01父项功耗−12.6104%、cell面积−11.9286%，修复父项面积超限。其他3候选最终setup拒绝，其中Student03/04最终PPA相同。

新增分支已实际通过全部18输出PDR（`run-6a604e61ebf14fc7bec3031834bcfcfd`）、独立完整DRT/RCX七值同值（`run-ceda82eb8b604b98ac43ddf7c5ce8052`）和DF/DI身份/数值核验。四份共同测量共48个raw值及相应快照身份逐项通过；收据在`gcd-dpl-goal-all-final-sdk-facts.json`及`runtime/experiments/gcd/a29-gcd-dpl01-goal01-validated-r1/validation.json`。先确认原frontend已退出、结果SHA稳定后才绑定验证，避免在追加原候选库存期间冻结半成品摘要。

Codex保持旧G02为最低功耗incumbent，新DG1作为已验证合法接力分支归档。本分支时序已闭合，ECO不另起无必要动作；原G03→ECO八轮及拒绝侧枝仍是实际ECO参与记录。新旧Goal阶段/策略不同，不能把分支差异当成DPL独立因果效应。决策及验证/原件引用在`gcd-dpl-goal-next-decision.json`。

JPEG只重试已保存Flow10的功能证明：24GiB新case `a29-jpeg-flow10-functional-proof-r2`、EF `run-f70ca7ca66cf44df9466283b2b045cdc`，当前按EF容量排队；8GiB失败和所有原搜索记录保留，不重开搜索。GCD原DPL另外两个Student/Teacher轮次仍未结束；ibex继续其原生修复/评价。Ariane完整基线待当前关键资源释放，不能把未启动写成完成。

论文结果表增至19个SHA核对最终节点，新增GCD完成接力图r2、7节点PPA图r2及5页老师阅读版r4；已检查实际PDF渲染、中文、表格与图标注。没有新增产品代码、服务、公共API或评测数据库。

## 18:49继续执行：资源队列与交接语义

GCD新增DPL01→Goal分支已完整验证，保留原G02的决策不变。七份实际交接文件重新按声明SHA核对通过，Goal的profile/request确认其使用独立prepared source seed、未指定code_source；DPL专业源码保留来源身份，未自动合并进Goal。原prepare明确移除filler和信号线路，后续重新测量，不把旧寄生当新事实。说明及原引用在`gcd-dpl-goal-handoff-inheritance.json`与论文方法表。

JPEG只对已有Flow10作24GiB功能证明，EF `run-f70ca7ca66cf44df9466283b2b045cdc`实际运行，18:38已进入partition。原旧搜索保持停止；证明未终态前不填写通过。原DPL第三Student后续评价`run-581315e918f74518b8354dd2104a7c0e`需要24GiB、ibex修复评价`run-c86add5b87444698b4c566157bce5b64`需要12GiB，当前剩8GiB，因此为明确资源等待，不是任务未被消费。没有改活动profile或重启控制器。

Ariane完整原映射网表/含固定宏floorplan的ORFS已由原准备命令提交，EF `run-c40e2257df494a38a1d941901dfc8952`排队，预约32GiB；原网表、SRAM模型与来源保持，不换成别的设计。GCD已完成合法接力后才派发，既有任务不抢占；最终PPA尚无。启动收据`ariane-baseline-launch.json`固定PID613551及启动身份。

更新`CURRENT.json`至19节点/r4材料及真实活动句柄。26个受保护用户文件SHA全部保持；本次仅报告/方法说明及var运行记录变化，产品代码、公共API、服务和研究算法未变。

## GCD论文案例正文交付

新增`INVITED_PAPER_GCD_CASE_TEXT_20261020.md`，提供可编辑英文案例正文、七节点指标变化表、中文业务要点及证据入口。围绕已验证F37→G02、Flow→DPL01→DG1合法分支和G03→ECO拒绝分支写出“任务—测量—诊断—继续/保留”的实际过程；未把未完成DPL整轮或四设计写成完成。引用结果SHA、七行表、两合法分支原约束/验证、链接及26受保护文件摘要核对通过。仅文档变化，不重复产品回归或EDA。

补收ibex Student01/02原首物理叶日志，经公共DI取回并对EF登记SHA核对；结合已核对03/04，四个首原生GRT估计分别TNS−15.4737/−18.4791/−23.0849/−23.0849ns，slew/cap为533/23、458/22、469/22、469/22。原时序修复后的估计明显优于GRT后，说明阶段衔接值得最终测量后继续诊断；这不是最终DRT/RCX PPA或唯一原因判断。原生修复轮次不动，证据在`ibex-four-native-stage-diagnosis.json`。
