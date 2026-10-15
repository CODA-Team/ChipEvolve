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
| Flow | 两轮×三候选，原阶段继承/CP0/评分，10800s | 进行中：第一轮三候选已进入route_finish；尚未记完整专业成功 |
| DPLEvolve | 一轮Teacher/三Student/review，原三基线，14400s | 待做 |
| GoalEvolve | 一轮Teacher/四Student/review，原AST/EPD/目标/晋升，21600s | 待做 |
| ECO | 两轮原生操作、完整route校准，5400s | 待做 |
| 最终验证 | 正式validate、Query比较、Codex采用/拒绝 | 待做 |

这是完整迁移验证，优化收益、专业候选晋升和平台执行成功分别记录。各阶段由Codex选择实际源分支，不放宽约束，不通过关闭专业检查换取成功；未做完项明确保留。

## AES实际发现的迁移缺口与最小修复

第一份a9-flow的原生CP0评分日志显示0寄存器、No paths found，却把TNS=0当有效反馈。已停止本轮自己的业务驱动/模型子进程，保留全部物理结果、模型/失败证据和原生反馈，不采用其评分，也不声称完成有效搜索。

同一份真实AES布局经EF三组控制：实际562个DFFHQNx1_ASAP7_75t_SL；原RVT/SRAM TT模型识别寄存器0，完整TT VT模型识别562个，CP0=590.868ps下TNS=-18442.60ps/WS=-253.76ps；实际FF模型也识别562个，但TNS=-1066.07ps/WS=-58.66ps。证明缺少LVT/SLVT模型是这次空分析原因，并保留TT/FF条件差异，不能混算专业与最终指标。

最小修复：Flow正式eval_tns.sh加载完整RVT/LVT/SLVT/SRAM TT模型；eval_tns.tcl在没有受约束setup路径时失败，不要求一定有寄存器，因此受约束组合设计仍可评分。保留原CP0、TT评分、参数搜索、淘汰、晋升与两轮三候选。根flow_source同步冻结正式eval_tns.sh/tcl，避免只复制Python却沿用旧template评分器。原接口不变。

实际新脚本在AES识别562寄存器、真实非零TNS；GCD识别34寄存器、存在受约束路径。Flow模块2674c7c，62项原生目录回归通过；根185项回归、Ruff、shell语法、pyright及边界检查通过。首次dev.py测试目录及旧开发环境缺新Toolkit导致的测试准备失败保留，资格环境使用实际运行的独立Flow wheel环境，没有修改无关开发环境。

新实验a9-flow-r2使用正式修复脚本、同一基准及原两轮三候选，正在运行。证据：flow-invalid-feedback-stop.json、a9-eval-library-audit-r2/comparison.json、a9-eval-model-qualification/qualification.json及flow-model-diagnosis-receipt.json。初次审计容器未显式传入环境变量的失败、直接脚本调用未找到根模块的准备错误同样保留；有效控制均由EF执行。

本缺口说明“平台执行成功”不能代替专业评分有效性；此前独立测量/等价/重放验证的GCD最终PPA不受此错误反馈的重新解释影响，但不因此为旧多VT Flow轮次补造有效评分。
