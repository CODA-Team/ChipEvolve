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

## ibex匹配原生基线与阶段图

通过DI取回原timing_only和power_then_timing基线日志并核对EF产物SHA，分别为`run-85b23423d9724a9f94f45672d92a0184`和`run-0931489eb57841b2be0740d9d6c151b8`。原基线GRT后已有TNS−7.253585/−20.217288ns，后者469slew/22cap。首Student01/02使用相同legacy时序配方，相对匹配阶段基线降低TNS债务23.46%/8.60%；03/04使用不同深时序配方，TNS较大仅作描述，不作同配方C++增益比较；不能把完整ORFS与原生GRT阶段差异全部归为新源码或平台影响。原修复仍继续，最终物理测量后再判断。

诊断表和下一步记录在`A29_IBEX_NATIVE_STAGE_DIAGNOSIS_20261020.md`；`paper-assets/ibex-native-stage-diagnosis-r2.pdf/.svg`展示六原生评价阶段曲线，并明确未计作最终PPA。六份原日志SHA、阶段值和图渲染均已核对，无新增EDA或模型调用。

## 19:19 JPEG证明终态与Ariane实际启动

JPEG已保存Flow10的24GiB全输出证明`run-f70ca7ca66cf44df9466283b2b045cdc`按原3600秒限额终止，EF为timed_out/timeout；原EQY停在partition，未生成PASS或logical-equivalence回执，也未给出功能反例。峰值11126919168字节，采样CPU3744.19秒、最大6进程。与8GiB旧失败不同，本次不是内存限额终止；本轮不重复同一证明或重开旧搜索，Flow10只保留为实测PPA可行但功能未验证、未采用。

EF托管超时清理后，原GCD DPL第三Student评价`run-581315e918f74518b8354dd2104a7c0e`于19:19:03开始、19:19:29成功；随后Ariane完整原网表/含宏floorplan ORFS `run-c40e2257df494a38a1d941901dfc8952`于19:19:29实际开始，已进入物理优化。ibex12GiB任务仍因Ariane32GiB预约等待，不把排队当作失败或重启它。

失败证据通过公共DI取回EF登记的runtime_evidence_log并逐SHA核对，gold/candidate两原结果SHA保持；原件/用量和不重复决策分别保存`jpeg-flow10-proof24-{final-ef,outcome}.json`及`jpeg-flow10-proof24-final-sdk.log`。原G02和新DG1的验证与采用决定不受影响。

## 六页审阅版r5

`paper-assets/teacher-review-overview-r5.pdf`为六页矢量PDF，保留19个逐SHA核对完成节点，加入ibex原生阶段/参考曲线，标明深配方差别、JPEG证明终态及Ariane实际运行。GCD英文案例可单独编辑；报告/CSV/方法说明和根TASKS/ARCHITECTURE当前状态同步，不改模块边界。新增成本快照`cost-snapshot-20261020T112310Z.json`包含153份已闭合EF执行回执/采样CPU44348.44秒，13份列明Goal模型回执的用量范围保持；当前原DPL/ibex后续及Ariane活动部分不计作完整总成本，不报告节约比例。

## 19:49 Ariane阶段与业务入口观察

Ariane的全局布局、详细布局和CTS已实际完成，CTS后的negotiation合法化两轮达到零非法单元，保留136个63行高SRAM宏。完整ORFS仍在运行，不填最终PPA或宣布全约束通过。原SDC的900ps及全部I/O约束与本次输入一致，只增加显式ps单位前缀；实际EF登记inputs/design.sdc摘要也匹配，来源核对在`ariane-original-constraints-provenance.json`。

三设计现有status及ibex watch均已真实调用，能直接区分运行、成功、历史失败及明确的资源等待；四份回复和Codex解释冻结在`business-status-demo-r1/`，补入平台操作记录。未新增EDA、模型、服务或公共接口；原DPL和ibex句柄保持。

## 已完成DPL调用用量与Ariane后继策略准备

读取DPL原Teacher规划、Student01/02三份已结束的codex_usage_summary，并逐行核对原codex_events.jsonl的turn.completed用量，完全一致：input58717906，其中cached input58096128为子集，二者差621778；output207606。原始摘要/事件SHA和各自elapsed保存在`dpl-completed-native-usage.json`。不把缓存量再加到输入总量，也不把并发子调用elapsed之和当整场墙钟；Student03、后续Teacher review、旧实验及宿主推理未包括，货币成本未知。已纳入`cost-snapshot-20261020T120220Z.json`，EF仍仅覆盖153闭合回执/采样CPU44348.44秒，非全场总成本或节约比。

Ariane已进入详细布线。为最终Query若判定需时序修复而准备原Goal已有single_stage/timing_only配置：选择原生strict_evidence插件和TNS权重，保留1轮4Student、AST/EPD、源码范围/完整性及原评分实现；平台最终功耗、面积、时序、电气/布线约束仍按源objective，不由原生局部TNS改善授权采用。此配置未派发、未被当结果；现有PowerFirst实验及运行参数不变。原native load_config解析通过，无工具/模型调用。`ariane-timing-strategy-preparation.json`记录原生策略与准备文件，实际启用取决于完成基线和DF/DI/Query。

后续不在ibex原轮次/共同交付收尾前再派发32GiB物理分支，先利用小任务完成Ariane数据/Query及当前案例收尾，避免大预约再阻塞接力。没有新服务、公共API、产品源码或旧任务修改。

## JPEG重新调查与Ariane详细布线收尾

旧JPEG Flow搜索保持停止。对已有Goal03和旧拒绝ECO执行一次新的只读Query，调查`inv-ec2f15f9292047b5afaf133a3abc6cfb`完成8步、60次工具调用，形成4事实/3假设及专业上下文。它是实际使用Codex hosted后端的新调查，不计作零模型调用。source固定为Goal03 `run-479b9b902ff541198d0e5c51b1493215`，reference是其旧ECO后代，不是ORFS baseline或已采用incumbent。

调查确认源设计有多个负reg2reg端点，重点是`_118520_`半加器及`place9038`共享缓冲驱动，而非直接复制旧ECO最佳状态中的实例名。一个匹配端点在旧ECO中略好、全局TNS却更差，说明局部收益不能代替整体目标。原Goal03仍是150.8680135mW/6243.33um²/setup WS−12.5853ps/TNS−0.0701142ns，没有因诊断产生新PPA收益。

补充通过公开DI取回两份完整SDC（各2262288字节）及317193字节压缩Liberty，并逐EF登记SHA核对。两SDC去除注释/空行/行首尾空白后指令文本完全一致，原Query关于完整约束差异的未决项由独立补充记录闭合；原Query导出不改写。Liberty完整解压后提取HA原声明，避免把gzip二进制片段当作单元属性。补充原件及结果在`jpeg-focused-query-supplement.json`和`jpeg-focused-supplement/`。

新八轮原生ECO命令仅准备，尚未派发；见`jpeg-focused-eco-prepared-decision.json`。继续原评分、估计收益门槛和回滚/最佳状态策略，实际备选单元由原生上下文重新生成，不硬编码动作；20GiB/8线程按旧JPEG实际峰值14.04GiB留余量。先完成在途ibex原轮次及共同交付。原命令校验主要检查命令种类/参数形状；`allow_insts`参数尚未被使用，Tcl是机械修改器，不将它写成完整的对象权限/功能证明。采用仍须完成最终物理与功能核验；本轮不顺手改研究算法或增加防御框架。

Ariane原完整ORFS已完成详细布线，最终原生DRT计数0、布线峰值23487.93MB；继续原流程后续工作和交付。观察到新版ORFS内置`kepler-formal`检查仍在EF任务树中运行，不是另行发起新证明；最终PPA/DF事实尚未产生，不能先填结果。GCD DPL/ibex原句柄均保持，仍按EF实际资源预约等待；没有重启或修改冻结请求。

## 21:16 Ariane内置证明退役，原物理检查点接续

确认原新版ORFS的`LEC_CHECK`默认取1，`formal_check.tcl`直接同步执行Kepler且没有独立时限。原详细布线已经DRT0，但全局内置LEC从21:00开始、约十五分钟仍在solver，没有通过或反例；它占着整个32GiB任务预约，阻塞了原DPL和ibex。按近期计划不把Ariane证明设为本轮前置，通过公开EF cancel停止`run-c40e2257df494a38a1d941901dfc8952`。EF终态为cancelled，原任务不计完整ORFS成功，不伪造LEC结论。其闭合采样CPU29733.53秒、峰值24710152192字节，原成本和取消证据保留。

取消前原最终ODB（380815639字节）、网表、DEF、完成阶段SDC、原DRT JSON及LEC配置/日志已保存；每份复制前后size/mtime稳定，记录SHA。归档在`ariane-completed-physical-checkpoint/manifest.json`，原EF公开日志及取消决定/回执另存。本次使用的Goal PDK和原ORFS RCX规则SHA完全相同（`32a117e5...252cc`），不是换模型重测。

一次性运行脚本复用现有Jobs/container/measure/freeze_goal/annotate/publish，已提交`run-9a39f8411779473f9602ec220c7db8a5`：只对同一最终ODB提取RC并按现有共同测量/三快照发布至DF。没有重做布局/布线，没有新增服务、公共接口、数据库或产品逻辑；后续结果明确标注原LEC未建立功能证明。运行记录`ariane-saved-physical-final-launch.json`、独立case `a29-ariane-saved-orfs-physical-final-r2`；当前仍在EF资源等待，最终PPA未出。

原任务资源释放后，GCD原DPL构建`run-29b1a33e5d9346bd9ccea6e2fc4ea537`与ibex原修复评价`run-c86add5b87444698b4c566157bce5b64`随即实际运行，未重启或改它们的冻结输入。JPEG新ECO继续仅准备，旧Flow不重开。Query完成调用成本单独登记：input1558866，其中cached1420416为子集，output9505、318.89秒；`jpeg-focused-query-model-cost.json`及`cost-snapshot-20261020T130734Z.json`保留范围，不能与先前确定性status读取的0内部调用混用。

## Ariane共同测量完成，事实导出按设计放宽时限

同一已保存最终ODB的RCX任务`run-9a39f8411779473f9602ec220c7db8a5`与共同测量`run-22470f85c938424597bb7a55bb18c881`均已成功；没有重跑布局/布线。测量原件已落盘，但三事实尚未完整入DF，因此未加入当前19节点论文表。其900ps/全布线提取下setup和slew仍失败，需完成真实Query后再选专业接力；不把参考设计自动称为全约束合格。

首次OpenDB导出`run-51f78ee104704bb281b8b6af9c3db018`在原300秒限额终止，采样CPU297.0秒/峰值900083712字节，明确不是8GiB内存耗尽。只检查公开EF工作区的输出进度计数：已有约212万对象行、333万关系行及212万几何记录行，共约3GB部分输出；它们未当作完整DF事实消费。代码审查确认导出逐对象/引脚/网络流式处理，先给完整大设计足够时间，不改导出内容或搭建性能框架。

本轮产品仅修改`chip_evolve/physical.py`的publish：读取现有内部设计绑定`fact_execution.timeout_seconds`，默认300保持；显式不同限额使用独立任务key后缀，旧请求/失败证据不改。Ariane新绑定1800秒，内存8GiB/线程2、数据格式/逻辑快照ID/目标/条件及物理结果均不变。新增`admin/test_fact_execution_budget.py`验证默认与显式预算、缓存重入不发新任务、保留超时任务后独立接续且原PPA/条件不变。32针对、566根回归及Ruff/格式/Pyright通过；真实大设计新导出待执行。没有修改工具包、EF/DF/DI模块或公共SDK，也没有修改运行中的专业源码。

ibex Student01原修复评价成功，公开DI日志641060字节/登记SHA核对通过：原生slew/cap从首版533/23降至33/3，但post-GRT TNS为−16.1516511404ns，尚非最终共同PPA。原功耗后TNS−6.987679ns经时序修复闭合，GRT估计又出现债务；这个阶段差异需在最终事实与后续Query中解释，不能当成全部由新C++导致。原控制器正在下一次修复构建，仍由原规则决定整轮与晋升。证据在`ibex-student01-repair-native-diagnosis.json`。

## 2026-10-20 23:01 本轮最新核查（覆盖上文历史进行中口径）

- GCD原DPL一轮三Student与Teacher已完成，原生选中Student02；其共同CTS/布线交付仍排队。Student03合法化在原定时间内未结束（124），框架按原规则保留失败并完成轮次。已验证的DPL01→Goal DG1不改父项，保留功耗更低的G02。
- ibex原Goal一轮四Student与Teacher已完成，晋升Student01修复版。主分支最终为28.18046324mW /2339.71µm² /setup WS−28.3996ps /TNS−1.59699ns、slew32/cap1，不采用；12原始指标和三快照身份已通过DF/DI核对。其余候选共同交付排队。
- ibex主分支Query已完成，证据支持检查`_17624_`共享逻辑与`place4192`/`place4191`输出缓冲；故准备独立原生Goal timing-only修复。沿用已测网表/布局与900ps/库/SDC，原生prepare清除信号线和fillers、之后完成原详细布线；不把修复隐藏在测量里，不称Student01 C++源码已自动合并到新执行文件。当前只准备，尚未派发。
- ibex后续`run-58bdc4163b2940a796f3621ca48b1108`已通过EF原请求更正为**同源码last_gasp_deep匹配基线**，不是repair2。公开原件SHA核验显示该基线与Student03/04的ODB/V/DEF逐字节一致；不能声称这两个深策略已产生原生QoR收益。
- Ariane完整物理参考的RCX、共同测量及三类事实已经完成：642.41528511mW /43672.8µm² /setup WS−285.396ps /TNS−155.146ns /slew436，原生DRT0。1800秒事实导出成功，12值/3身份通过。原ORFS inline LEC被明确取消、功能尚未证明，不称完整原任务成功。
- Ariane Query已完成并指出深标准单元reg2out逻辑时序问题，已派发原Goal timing-only/StrictEvidence一轮四Student；32GiB原生基线当前等待资源。该设计保留原SRAM模型，不宣称所有宏均FF或完整签核。
- JPEG旧Flow搜索保持停止。以原Goal03为父的新定向ECO会话实际运行，最多八轮；尚无新的共同最终PPA。保留原负接力与Flow10证明超时。
- 新源码固定00199d3：仅按实测时间配置Ariane共同物理收尾7200秒；既有默认1800秒不变。事实导出配置1800秒的修复bc89146已通过针对检查；最近根570回归和静态/格式/类型检查通过。两修改均只用现有内部设计绑定，不增服务/API/数据库。

本轮实测等待为内存预约冲突：JPEG20GiB运行时，GCD与ibex的**冻结共同物理请求各24GiB**、Ariane32GiB不能进入余下12GiB。ibex原生评价12GiB不等于共同收尾24GiB，不改动冻结任务或把等待写成派发丢失。

论文表已有21个SHA核对完成节点（含Ariane参考、ibex主结果），新r7审阅包将持续导出；未完成四设计收口，不声称协同全面优于最强单项或token节约比例。

### 23:20 JPEG定向ECO原生收尾

原生EF `run-d0633a27d4f543008de7e7df8b826b3f`成功，八轮结束，10次模型调用包含两次空动作回复后的原生重试，不能少记为8次模型。原生WNS best为第4轮，原生详细布线计数9592，最终ODB与原计数证据已绑定；这不是共同最终PPA。按已确认边界另行完成完整布线/RCX/测量，EF `run-c37bb3b08fa34c659ff53973c05fc695`排队；旧Flow搜索保持停止。ibex原排队Student02共同交付已随资源释放开始，没有重启原控制器。

### 23:30 ibex第二候选最终交付

Student02共同结果27.968287468mW/2335.44µm²/setup WS−36.3866ps/TNS−4.41515ns，slew408/cap18、原生DRT0；12项原始指标与公开DF/DI逐值核对、ORFS/OpenSTA两个快照身份通过。拒绝候选OpenDB按既有机制延后，不冒称三类事实齐全。其电气/时序比主Student01更差，仍保留合法IB0，prepared timing-only继续以Student01为源。CSV增至22完成测量节点；r8审阅包固定21节点时点，不改写已发布快照，下一次统一导出再纳入新结果。

## 23:50 收取真实交付并继续按诊断修复

- GCD选中DPL Student02最终为0.89124625083mW /44.6148µm² /setup WS+14.3074ps /TNS0，hold WS+33.8957ps、hold TNS0，电气/布局/原生DRT均0。12原始指标、三DF/DI快照身份与实际F37父项一致；功耗+0.03757%、cell面积−0.61704%，仍超过原面积上限42.6757，拒绝。未改DG1的DPL01父项，G02和DG1原18输出证明/独立重放再次核SHA后复用。GCD四专业真实参与、两条合法接力和拒绝分支的业务证据已齐；原DPL框架仍收取兄弟候选交付，不冒称整个前端已退出。
- ibex基于主Student01的独立timing-only/legacy_setup已经派发并完成原生评价，实际只执行repair_design和repair_timing -setup，没有再次功耗回收；原生GRT估计TNS−11.090138ns/DRV26。该阶段是理想时钟/估计寄生，不能与主候选最终TNS−1.59699ns直接算收益；共同DRT/RCX任务仍排队。使用12GiB的实测短原生任务与JPEG20GiB共存，未改冻结请求或抢占。
- JPEG定向ECO的完整布线/共同测量/三事实已经结束，12值及三身份一致：151.72843635mW /6243.39µm² /setup WS−15.6584ps /TNS−0.238709ns，slew0/cap0/**fanout1**，原生DRT9592→完整DRT0。最终setup和fanout均失败；功耗较实际Goal03增0.570315%，拒绝。全字段核对捕获了扇出违反，不能只看PPA主表就宣称电气通过。
- 根据已完成Goal03 Query，另从更好的Goal03发起一次明确的native OpenROAD post-route finishing：加载原实际SPEF/传播时钟并先核原TNS/WS，执行原生repair_design和repair_timing -setup -repair_tns 100、合法化，再另行完整DRT/RCX/DF。是Codex下发的原生收尾动作，不是新增Goal Teacher/Student或合并其C++源码，也不是隐藏在共同测量里的优化；原目标/时钟/库不变。所有工具由EF启动，目前run-a1e12cc7f8ac46548e81ddfbed3b1052排队；没有重启旧Flow搜索、复跑八轮ECO或重复相同策略。
- Ariane原Goal原生基线已实际运行，STA确认5093个setup违例端点，支持全局专业接力选择。23:49核实原OpenROAD PID2498415仍运行，累计CPU约67分钟/墙钟614秒、约657%CPU、RSS约1.8GiB；不能把日志暂未更新当作卡死或重启。此为原生placement寄生/ideal-clock阶段，不是最终PPA。

当前CSV增至24完成测量节点。r8九页审阅包固定21节点时点，后续统一导出再纳入新节点，不改写已发布快照。原件/SDK记录、GCD业务证据摘要、两个独立修复的真实启动/EF回执均在本轮var目录；仍未完成四设计目标。

## 2026-10-21 00:55：收齐原轮次，定位新增收尾协议问题

1. 原GCD DPL前端完成所选Student02及Student01兄弟的最终交付。原框架Student01重复交付的12项指标与已用于DG1的早期Student01逐项相同，不新增论文行、不改DG1父项，重复工作成本仍保留。原ibex一轮四Student/Teacher及最终交付已齐；Student03/04最终均27.995452285mW/原TNS−4.26612ns/slew421，setup/slew/cap拒绝。两份最终12指标和两快照身份独立核对，同原生物理输出一致性记录一起保留；不是新Cpp收益。
2. ibex独立原生timing-only最终28.110442683mW/2340.26µm²/setup WS−26.2704ps/TNS−1.74221ns，hold WS+27.7896ps/TNS0，slew13/cap0/fanout0/DRT0，12指标/三身份通过。相比主Student01功耗−0.24847%、电气改善，但时序仍不合格。
3. 当前Codex直接使用Query host完成该新状态调查，六次成功DF/DI读取共109190字节；另四次首轮请求将参数错误放进path而被拒，改为已有separate arguments后成功，保留失败。Query观察墙钟223.63秒、服务内active0.410秒，不能把后者当总回答用时；额外Query子模型调用0，父Codex token未单独计量，不报节约率。新上下文实际交给独立native postroute收尾，所有工具仍由EF启动。
4. JPEG新增收尾r1原生用21次VT替换把报告中的19个setup违例消为0，合法化移动0，但完整新GRT/DRT/RCX后的最终为151.75381303mW/6243.33µm²/setup WS−26.2502ps/TNS−0.306245ns，原生DRT与电气/布局0，setup拒绝；12指标和三快照身份通过。它与原生估计不同，不能冒充闭合。已提交同一修复ODB、保留现有线路的RCX诊断，原生DRT状态保留unknown，现有select会拒绝，不从诊断采用。该诊断区分重布线与内部模型影响，尚未证明唯一原因。
5. 日志EST0027与原生源码审计确认：新增SPEF-only收尾脚本没有初始化Resizer的增量估计模式。r2显式先estimate_parasitics -placement再读回源actual SPEF，核原TNS/WS与estimated-mode后才改设计；改变的网络使用已声明placement估计，不声称全程都是新提取RC。另用原工具支持的内部setup_margin（ibex15ps/JPEG30ps）应对r1完成路由后的10.33ps/26.25ps债务；900ps/545ps及最终零TNS等硬约束完全不改。两个r2为有明确新协议和策略的独立任务，均已通过EF派发；旧r1产物/失败保留，不重启Flow/ECO/Teacher/Student，不改产品API、服务或其他模块。
6. Ariane原生基线已完成，24分16秒的实际EF执行/1093秒原生resizer计时分别记录；五项原检查通过（四项结构LEC不等于完整功能证明），原生GRT债务427.967529ns不当作最终PPA。原Teacher、AST/EPD和四Student已经生成四个真实C++变体：前两份修改SetupTnsPolicy.cc，第三份MeasuredVtSwapCandidate.cc，第四份SetupMt1Policy.cc；各701份源声明和不同请求哈希已核对。两份LTO正在实际消耗CPU并推进分区，两份归档/构建排队，不是失联，不重启。

当前CSV28个完成测量节点，四设计目标仍未结束。r9 PDF/ZIP固定24节点时点；后续统一纳入新最终结果。源证据见本轮var的ibex-students03-04-final-sdk-facts.json、ibex-timing-finish-final-sdk-facts.json、ibex-postroute-source-query-r1/、jpeg-postroute-finishing-fullroute-final-sdk-facts.json、native-postroute-estimation-protocol-audit.json、两份r2启动回执及ariane-four-source-builds-status.json。

### 01:00补核：r2初始化已实际验证

ibex r2原生步骤已成功结束，公开原始日志SHA核对通过：输入TNS−1.7422088709ns/WS−26.270431ps与源测量一致，EST estimated-mode明确为1，旧EST0027 wire-load fallback警告消失。内部15ps目标下完成33次resize（4 sizeup、29 VT）、timing阶段8个新buffer，原生报告余量+15ps；这仍是原生阶段，不声明最终闭合。完整DRT/RCX任务run-9abcab90805e44aca2788c7f072315d0排队。JPEG r2及同候选保留线路诊断继续独立排队。Ariane前两份完整OpenROAD链接已结束，后两份链接继续；原模型/四Student流程没有重启。
