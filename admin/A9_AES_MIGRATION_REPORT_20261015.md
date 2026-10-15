# A9：AES真实迁移验证

状态：进行中。A8已提交58c0488，老板业务验收独立。本轮新实验在var/business/a8-a9-workflow-20261015/runtime/experiments/aes；历史U4的AES超时、A4/A5固定方法重放均不改写。

## 冻结基准

通过正式run入口从RTL完成ORFS：run-991197d4b6a44fb78760a497cfc1d42e；统一测量run-d9871b41ba024b399c798f44b7dc108d。ASAP7 FF、810ps，同一固定工具/实际Liberty/SDC、完整DRT/RCX。功耗35.107899457mW、单元面积1255.75µm²、core/die1941.63/2321.51µm²；setup/hold TNS均0，setup WS+227.247ps、hold WS+31.1463ps；slew/cap、placement和DRC均0。

与A4/A5旧AES同条件ORFS基准的七项PPA逐值相同；新objective独立冻结，不能把不同objective_id强行混算。三个SDK scope和原始源指标一致。证据aes-reference-check.json。新runtime已采用该基准作为incumbent，后续无合法改善则保留。

## 当前计划与状态

| 项目 | 原生范围 | 状态 |
|---|---|---|
| ORFS | 新RTL→GDS、共同测量和三类DF快照 | 已通过 |
| Query | 真实同一Codex调查，固定AES baseline scope | 已完成：9条确认事实/3条假设，真实上下文已送入Flow |
| Flow | 两轮×三候选，原阶段继承/CP0/评分，10800s | 修复后的r2完整正常结束，六候选统一测量/DF完成；均超全局功耗/面积/轮廓上限，不采用 |
| DPLEvolve | 一轮Teacher/三Student/review，原三基线，14400s | 进行中：三条基线成功，三Student均已真实构建/布局评价；模型连接曾中断，后已继续，整轮审查/交付尚未完成 |
| GoalEvolve | 一轮Teacher/四Student/review，原AST/EPD/目标/晋升，21600s | 待做 |
| ECO | 两轮原生操作、完整route校准，5400s | 待做 |
| 最终验证 | 正式validate、Query比较、Codex采用/拒绝 | 待做 |

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

不改活跃/历史controller副本，也不覆盖a9-dpl旧选择及交付检查点。用正式修复选择器只读重查同一已完成原生轮次，得到Student2/candidate ref14a59657…；建立新a9-dpl-delivery-r2交付，原布局hash及真实producer按内容绑定，重新CTS/route/测量/DF。模型搜索没有重跑。当前新交付仍在进行，后续Goal以实际测量及来源决策为准。
