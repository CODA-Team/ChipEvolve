# A9：AES真实迁移验证

状态：工程验证完成，待老板业务验收；本轮收尾后暂停新增施工。A8已提交58c0488。本轮新实验在var/business/a8-a9-workflow-20261015/runtime/experiments/aes；历史U4的AES超时、A4/A5固定方法重放均不改写。

## 冻结基准

通过正式run入口从RTL完成ORFS：run-991197d4b6a44fb78760a497cfc1d42e；统一测量run-d9871b41ba024b399c798f44b7dc108d。ASAP7 FF、810ps，同一固定工具/实际Liberty/SDC、完整DRT/RCX。功耗35.107899457mW、单元面积1255.75µm²、core/die1941.63/2321.51µm²；setup/hold TNS均0，setup WS+227.247ps、hold WS+31.1463ps；slew/cap、placement和DRC均0。

与A4/A5旧AES同条件ORFS基准的七项PPA逐值相同；新objective独立冻结，不能把不同objective_id强行混算。三个SDK scope和原始源指标一致。证据aes-reference-check.json。新runtime已采用该基准作为incumbent，后续无合法改善则保留。

## 当前计划与状态

| 项目 | 原生范围 | 状态 |
|---|---|---|
| ORFS | 新RTL→GDS、共同测量和三类DF快照 | 已通过 |
| Query | 真实同一Codex调查，固定AES baseline scope | 已完成：9条确认事实/3条假设，真实上下文已送入Flow |
| Flow | 两轮×三候选，原阶段继承/CP0/评分，10800s | 修复后的r2完整正常结束，六候选统一测量/DF完成；均超全局功耗/面积/轮廓上限，不采用 |
| DPLEvolve | 一轮Teacher/三Student/review，原三基线，14400s | 原生完整轮次完成；修复平台选择接点后Student2真实布局完整交付，功耗−0.717%、cell+0.0231%，仍未达面积上限 |
| GoalEvolve | 一轮Teacher/四Student/review，原AST/EPD/目标/晋升，21600s | 完整结束，Student4晋升；共同条件全部约束通过，129输出证明、独立重放及SDK通过，已本机采用 |
| ECO | 两轮原生操作、完整route校准，5400s | 完整结束，无合格待修路径、有效动作0；输出证明/独立重放/SDK通过；功耗略高，拒绝替换Goal |
| 最终验证 | 正式validate、Query比较、Codex采用/拒绝 | 全部完成；采用Goal，历史不可行候选和失败记录保留 |

这是完整迁移验证，优化收益、专业候选晋升和平台执行成功分别记录。各阶段由Codex选择实际源分支，不放宽约束，不通过关闭专业检查换取成功；未做完项明确保留。

## AES实际发现的迁移缺口与最小修复

第一份a9-flow的原生CP0评分日志显示0寄存器、No paths found，却把TNS=0当有效反馈。已停止本轮自己的业务驱动/模型子进程，保留全部物理结果、模型/失败证据和原生反馈，不采用其评分，也不声称完成有效搜索。

同一份真实AES布局经EF三组控制：实际562个DFFHQNx1_ASAP7_75t_SL；原RVT/SRAM TT模型识别寄存器0，完整TT VT模型识别562个，CP0=590.868ps下TNS=-18442.60ps/WS=-253.76ps；实际FF模型也识别562个，但TNS=-1066.07ps/WS=-58.66ps。证明缺少LVT/SLVT模型是这次空分析原因，并保留TT/FF条件差异，不能混算专业与最终指标。

最小修复：Flow正式eval_tns.sh加载完整RVT/LVT/SLVT/SRAM TT模型；eval_tns.tcl在没有受约束setup路径时失败，不要求一定有寄存器，因此受约束组合设计仍可评分。保留原CP0、TT评分、参数搜索、淘汰、晋升与两轮三候选。根flow_source同步冻结正式eval_tns.sh/tcl，避免只复制Python却沿用旧template评分器。原接口不变。

实际新脚本在AES识别562寄存器、真实非零TNS；GCD识别34寄存器、存在受约束路径。Flow模块2674c7c，62项原生目录回归通过；根185项回归、Ruff、shell语法、pyright及边界检查通过。首次dev.py测试目录及旧开发环境缺新Toolkit导致的测试准备失败保留，资格环境使用实际运行的独立Flow wheel环境，没有修改无关开发环境。

新实验a9-flow-r2使用正式修复脚本、同一基准及原两轮三候选，已完整结束。证据：flow-invalid-feedback-stop.json、a9-eval-library-audit-r2/comparison.json、a9-eval-model-qualification/qualification.json及flow-model-diagnosis-receipt.json。初次审计容器未显式传入环境变量的失败、直接脚本调用未找到根模块的准备错误同样保留；有效控制均由EF执行。

本缺口说明“平台执行成功”不能代替专业评分有效性；此前独立测量/等价/重放验证的GCD最终PPA不受此错误反馈的重新解释影响，但不因此为旧多VT Flow轮次补造有效评分。

## Flow实际结果与下一阶段选择

r2完整两轮六候选正常结束，模型17次请求全部成功；原账本报告573106 token，此为本次专业原生用量，不是公平节省指标。六份共同FF结果时序/物理通过，但功耗59.42–89.04mW、单元面积1520.08–1758.84µm²、core2186.87–6587.24µm²，均超过冻结上限。因此保留ORFS基准，DPL以该合法基准为实际来源，不把本轮写成Flow→Code已产生联合收益。依据aes-flow-candidates.json和aes-dpl-source-decision.json。

EF输入审计确认Flow与当前ORFS镜像的七份AES RTL完全同hash。配置/物理脚本存在差异，包括当前ORFS的SYNTH_USE_SYN=1、原Flow的ABC_AREA=1及其原路由调整钩子；这里只证明输入/起点差异，没有逐个配置的反事实因果实验，不把PPA差距唯一归因给某个参数。保留原研究算法，后续是否迁移这些流程需独立切片。

对不可采用Flow分支启动的输出级Yosys证明在AES隐藏状态下开销较大，已通过EF取消，保留不完整记录；取消不证明逻辑不等价。相同RTL也不替代最终网表证明。正在使用镜像已有EQY校准分区证明；若最终采用Code输出，仍须完成真实逻辑验证。全局Yosys原型只在var中，不计正面验收，也没有写入通用新框架。

## 大设计逻辑验证的实际校准

镜像EQY v0.68/SAT不依赖额外模型服务或新平台。默认全名匹配会对扁平化库引脚形成过大依赖矩阵；全局隐藏内部名则对AES状态归纳开销较大。原型排除全部带点名称时，自检1004分区通过、32分区UNKNOWN，原因是同时丢掉了原网表声明的轮密钥状态切分点；这不构成设计错误结论。

保留真实顶层端口与原网表中声明的层级信号，再排除新生库引脚别名后，同一真实AES基准1072分区全部通过（89秒）；将该网表的text_out[0]故意翻转，1071分区通过，准确拒绝text_out[0]，保留原生FAIL和非零退出码（89秒）。两个控制均由EF执行，原固定15份Liberty、全部129个输出、模型排除证据不变，没有修改真实设计或关闭断言。

正式logic.py增加可选eqy后端，eqy.py只配置/调用已有工具并要求全局PASS及每分区PASS；默认GCD Yosys路径保持。新增4个回归覆盖原设计状态保留、部分证明/无全局标记/空分区拒绝；根189测试、Ruff/format及变动模块pyright通过。正式a9-reference-validation已通过：129输出/1072分区、独立RTL重放七项PPA逐值相同、三个DF/SDK身份及源指标一致；再次进入复用原8个EF任务，新增0。默认GCD Yosys路径复核仍通过。尚不代表新专业候选通过。

## AES相同交接路径控制

a9-handoff-control直接提取已登记ORFS archive中的3_5_place_dp.odb，保存producer及输入hash，经现有delivery/EF接口原样进入与专业输出相同的CTS/route_finish、共同测量与DF。两阶段消费校验通过；没有新专业优化，也没有改平台源码。

相对stock ORFS，最终setup/hold TNS仍0，WS从227.247ps到232.025ps；功耗35.107899457→34.952811897mW（−0.4417%），cell1255.75→1255.94µm²（+0.01513%），core/die完全相同。仍违反冻结的cell area上限，不采用。说明统一交接后的物理流程本身可带来小差异；后续DPL同时与stock ORFS和该控制比较，不将流程差异全部归于源码算法。证据aes-handoff-control-comparison.json、控制实验cts/route_finish-consumption.json。

## 完整轮次收尾暴露的晋升/溯源接点修复

a9-dpl的原三Student及Teacher审查均正常结束，三候选均通过原生工件检查；HPWL依次33873.7/33785.0/34058.8µm。平台selection却返回accepted=false。源码与真实路径核实：原orchestrator通过runtime_with_round_outputs将operations定位到STATE_ROOT/round_id/checkpoints/operations；平台只解析全局runtime，查错为STATE_ROOT/checkpoints/operations，因此误认为原生证据缺失。不是算法未胜出，不能通过降低筛选规则处理。

正式DPLEvolve selection.py复用原runtime_with_round_outputs，仅补齐轮次定位；原best_round_candidate(require_baseline_beat=True)、合法性、源码与证据门禁均保持。新增真实文件/临时Git回归证明：只有轮次目录存在原生usage时接受；不胜出或缺证据仍拒绝。21项模块回归、原静态release gate通过。模块186153d已推ChipEvolve modules/dplevolve，不推研究上游。

同一Student原生修订会复用run tag。root professional.py不再仅按tag假定唯一producer，改为同时匹配原生成功回执中的最终ODB内容hash；新增多次同名试验/失败/异tag/未登记内容回归。根190测试、Ruff/format、指定已安装client环境的完整chip_evolve pyright通过。首次client未装pytest及未指定解释器的类型检查缺依赖错误保留，不修改服务或无关环境。

不改活跃/历史controller副本，也不覆盖a9-dpl旧选择及交付检查点。用正式修复选择器只读重查同一已完成原生轮次，得到Student2/candidate ref14a59657…；建立新a9-dpl-delivery-r2交付，原布局hash及真实producer按内容绑定，重新CTS/route/测量/DF。模型搜索没有重跑。新交付已完成，Goal以其实际布局、测量及来源决策继续。

## DPL实际交付与Goal来源

Student2的a9-dpl-delivery-r2已完成完整CTS/DRT/RCX、共同测量及三类DF快照，run-7ec6bc1c72ba42e19796b25ea34ed62a。相对stock ORFS：功耗34.856114537mW（−0.71717%）、cell1256.04µm²（+0.02309%，超上限0.29µm²），core/die不变、setup/hold TNS均0、setupWS197.350ps（较原227.247ps减少）。相对相同交接控制：功耗−0.27665%、cell+0.007962%、setup余量也减少。原生HPWL收益不能等同于全部最终PPA改善。

Codex在该节点不采用DPL中间分支，保留ORFS incumbent；芯片轮廓和时序闭合、面积缺口很小，选择让原Goal在该真实DPL输出上继续原功耗/时序源码优化，最终仍须满足原全局约束。a9-goal以原一轮四Student、21600s预算启动，后续完整结果见下文；同时a9-dpl-validation通过可选EQY执行输出证明及独立重放。来源与两种对照见aes-goal-source-decision.json、aes-dpl-final-comparisons.json。

补充同专业框架控制：首次错误回退的a9-dpl实际用了冻结baseline_probe_evolve_default，可作为相同交接路径的原框架控制。其共同功耗34.840602428mW、cell1256.04µm²、WS201.145ps。Student2新源码虽将原生HPWL从34071.3降到33785.0µm（约−0.840%），最终功耗却比原框架高0.04452%、WS少3.795ps、面积相同。不能将相对ORFS的−0.717%全部写成新源码贡献。该补充在Goal启动后确认，保留已冻结的真实新源码接力分支用于迁移验证；不改活跃输入，也不宣称其为最终PPA最佳方案。所有控制保留供Codex判断，该节点仍保留ORFS，Goal完成资格验证后才替换。

## Goal完整原生轮次与实际采用结果

原Teacher/四Student/review已正常结束；基线build/flow/metrics/placement及原四项official检查全部通过。四Student的真实模型输入均包含本轮相同全局目标和来自真实DPL输出的Query context，不是只将上下文写在旁边的文件。原AST/EPD、目标、候选筛选和每个失败Student最多一次原生电气修复均保持。

Student1修复后仍有3052条slew违例、1条cap违例，setup TNS约−14.817ns；Student2/3修复后仍有2964条slew违例、1条cap违例，setup TNS约−15.571ns，均被原规则refuted。它们较低的原生功耗和占位distance_gain不能推翻拒绝结论。构建、执行环境均正常，失败是专业候选本身不合法。Student3两次评价约1001s，实际执行原候选新增的逐窗口功耗/slew观测；原循环有界且正常结束，没有当作卡死强行打补丁。

Student4原生validated、mechanism_fired=true，晋升为round_001:student_4；源码内容hash为f20120a3463c7d3dd4937000ad8dfb59558cc1b034d3d3c0b552db236fd2acee。原生goal_distance从0.2降至0.19825553415232638，原10%功耗目标没有全部达到。source_commit字段41260cad…是原生指纹，不将其误写成已发布Git提交。可选Sfinal观测器因缺竞赛baseline CSV未产生分数；源码核实它不参与EPD、Teacher和晋升，因此未伪造资料或改原规则。

最终共同测量run-b6fccbd5cf944ca185f6f94374a3d913：功耗34.931797534mW（比ORFS−0.501602%），cell1254.13µm²（−0.129007%），core/die不变；setup/hold TNS=0、slew/cap/placement/DRC=0。setup WS191.954ps，比原227.247ps少35.293ps；这是保持时序闭合前提下的小幅功耗/面积改善，不是所有PPA维度都改善。

正式a9-goal-validation通过全部129功能输出、1071个EQY分区，独立空目录完整DRT/RCX后七项PPA逐值相同，原结果和重放的三个DF/SDK scope及原始指标均一致。证明run-7e165c8cbecd48c2ba262a343d9e67dc。Codex经正式select采用该合法结果，回执aes-goal-adoption.json；未改变全局上限。DPL交付及相同交接控制也都通过129输出/独立重放/SDK核对，但最终验收因各自cell上限失败，保留失败状态。

## Query证据交付与ECO实际行为

四个Goal候选的原生判定、原始CSV指标及hash、父项和共同测量通过既有Jobs/EF接口登记为Goal结果的analysis子运行run-708d0b4192474f5caeca34efe461e862，raw_flow_metadata为7600字节。未增加服务、评分器、公共契约或通用推理框架。既有diagnosis.scoped_analysis_references自动将其交给Query；实际Goal→ECO调查读取原始判定，解释了前三拒绝/第四晋升以及原生代理与共同指标区别。

正式a9-eco以已验证的Goal输出为源，Query context为9ab315cac9541cbf58f28b7910f81a36a9d0e44e74201eee701ebd289a3b6493，9事实/2假设/19证据。原生会话run-67c873f473d84c6490ba3d50c7a9d386正常完成两轮：每轮allowed instances=0，无有效Tcl命令，保留原生空输出重试及pass-through记录；最终仍选择baseline iter0。此处“完成两轮”不代表执行了两次有效ECO修复。

其完整DRT/RCX后的共同功耗34.947250038mW、cell1254.13µm²、setup WS194.646ps，其余硬约束通过。相比Goal功耗增加0.044236%、WS增加2.692ps、面积不变；没有有效修改，差异不能算作ECO算法收益。保留更低功耗且已闭合时序的Goal。另一次独立ECO预检也因输入已闭合而有效动作0，该分支cell超上限，不采用。两分支原日志和失败记录保留。

正式a9-eco-validation也通过129输出/1071分区，证明run-d14f4a5565014614a29066433b5c9884；独立目录完整DRT/RCX后七项PPA逐值相同，DF/SDK身份及源指标一致。正式select拒绝用它替换已采用Goal，原因dominated_incumbent及Codex书面取舍；不是物理/逻辑验证失败。回执aes-eco-validation-receipt.json、aes-eco-adoption.json。

统一RCX规则hash为32a117e5e866d3de1406e8f18d65b6f1857781f156638941a4769e25ef5252cc；原生setRC.tcl用于各研究方法的估计评分，不因其与最终提取规则不同而改写专业算法。物理验收读取实际native-metrics.json的route__drc_errors，未把DRC硬编码为0。

## 最终Query核查与保留缺口

阶段事实通过既有EF analysis子运行run-b0d9f53ac20a45cb9b2d3a24e9a483f4登记为workflow-summary.json（42350字节），属于实际Goal共同结果scope。最终正式diagnose --against调查inv-9b12a150621f4cf59c1eb38f0a402d4f读取该文件和原native-round-facts.json，再经SDK和原始metrics核查双方指标、SDC及受限时序路径样本，得到11事实、0假设、30证据；context为5b66328cef299ed19b5cd1edfd26fb7f73b0f9d0458eac521af68fdacfee3495。解释与Codex取舍一致，没有追加实验或把未经验证的机制写成因果结论。

Query同时暴露尚未补齐的数据细节：OpenSTA路径索引缺少完整corner/analysis/unit比较元数据，现有比较接口不能独立认证全路径匹配；路径样本有舍入且不等于全路径。共同条件仍由已冻结objective、实际库/SDC/toolchain hash和原始测量核验；工程侧select逐项检查原上限，Query本次没有逐条读取全部caps原文，因此其“可行”陈述依赖登记判定和已核查指标。上述缺口如实保留，不动用户正在修改的DF/DI、不在收尾扩展新协议。

## 本轮文件职责与检查点

| 文件/项目 | 最终职责与影响 |
|---|---|
| flow-agent/flow/eval_tns.sh、eval_tns.tcl及test_cp0_paths.py | 原TT评分补齐VT模型、拒绝空setup分析；保留搜索与晋升 |
| dplevolve/scripts/platform/selection.py及test_platform_selection.py | 按原生轮次目录读取真实晋升证据；不改专业规则 |
| chip_evolve/professional.py | 固定正式评分器；按实际ODB内容和原成功回执选择producer |
| chip_evolve/logic.py、eqy.py | 复用既有EQY完成较大顺序网表证明；保留默认GCD后端 |
| admin/test_aes_migration.py、test_dpl_delivery.py、test_local_eqy.py | 错模板、同名修订溯源、部分证明拒绝等对应回归 |
| SOURCE_MANIFEST.json及两gitlink | 固定正式模块来源，保留研究上游；已提交到ChipEvolve模块分支 |
| PROJECT.md、ARCHITECTURE.md、TASKS.md、chip_evolve/README.md和本报告 | 同步用户效果、接口/数据边界、真实状态、验收与技术债 |

原A8文件职责和数据流详见A8报告，不重复扩展源码范围。运行证据全部留在var；用户26份修改不纳入提交。模型候选源码属于原专业实验及EF证据，不将本机环境、镜像或实验树混入平台源码提交。

后续应优先定位专业原生代理与最终PPA之间的落差：对Flow原流程和现代ORFS起点做少量匹配控制，对DPL的HPWL收益与布线后功耗/时序并列分析；Codex按真实问题决定是否启动ECO。随后独立补齐路径索引比较元数据。是否修改专业策略由这些证据决定，不在本片加厚底座或启动新的搜索/公平benchmark。

## 最终验收与业务结论

| 项目 | 本轮结果 |
|---|---|
| 本机工作流收口A8 | 正式运行/恢复/续作/比较/证明/独立重放/Query/采用；GCD真实中断验证通过 |
| AES迁移A9 | 四专业原生计划轮次、真实新C++交接、统一EF执行、完整物理测量、DF/SDK/Query均完成 |
| 采用结果 | ORFS→DPL Student2→Goal Student4；功耗−0.501602%、cell−0.129007%，core/die不变，全部原硬约束通过；setup余量少35.293ps |
| 验证 | Goal及ECO各129输出/1071分区，独立完整DRT/RCX七项PPA同值、SDK身份/指标一致；ORFS自身129输出/1072分区、RTL重放同值；负控制准确拒绝 |
| 最终工程门禁 | Ruff/format、指定实际client解释器的完整chip_evolve pyright通过；15专项测试和190根回归通过；差异/模块边界/26份用户文件hash通过 |
| 模块原门禁 | Flow62项、DPL21项及原静态检查已在对应正式源码提交通过；后续无源码改动，不重复扩展无关测试 |
| 未达成 | Flow候选不可采用、DPL HPWL改善不保证最终功耗改善、ECO有效动作0；原Goal10%功耗目标及公平总预算团队优势未证明 |
| 保留缺口 | 非同PDK/宏/多时钟设计未验证；专业代理与最终PPA落差、路径比较元数据、未完成原生模型搜索恢复仍需后续独立切片 |

权威工程回执var/business/a8-a9-workflow-20261015/a9-acceptance.json，最终状态aes-business-status-final.json，阶段进度a9-progress.json；各实验result/validation/任务回执保留原文。最终门禁日志a9-final-gates-r2.log。首次门禁脚本将虚拟环境python软链接解析成/usr/bin/python3.12，导致类型检查找不到已安装wheel；改为显式保留虚拟环境解释器路径后通过，未修改环境/依赖/源码以掩盖错误，原日志保留。工程完成和老板业务验收分别记录。

本轮通用接点已从GCD迁移到第二个真实ASAP7设计AES，原专业算法、筛选和约束保留；这支持本机流程可迁移的结论，不支持所有设计通用或四专业联合一定优于单项的结论。全部可查询实验和当前合法最好结果保留，本片不再自动启动新研究轮次。
