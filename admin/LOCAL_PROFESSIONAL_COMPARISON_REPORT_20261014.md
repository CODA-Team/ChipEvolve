# A5：专业单项与组合的本机对照

已授权第四项的本机对照及工程收尾完成，老板业务验收待确认；联合增益未达到，补充DPL新轮次因预算截止未通过完整轮次验收。工程入口见 [A4报告](LOCAL_BUSINESS_ENTRY_REPORT_20261014.md)。本轮不是公开公平benchmark，也没有测量数据增强节约token的第五项。

## 当前业务结论

共同条件下，GCD 的 Goal 新源码结果满足时序、功耗、面积、电气、布局和DRC条件，已通过与原ORFS网表的逻辑等价检查。相对本轮ORFS，功耗约降低36.9%，单元面积约降低23.2%，core/die不增加。Codex采用该结果作为本轮incumbent。

多专业接力已有真实结果，但已完成的组合没有胜过这份合法单项结果：Goal→ECO略增功耗；DPL→Goal进一步降低功耗/面积但留下约13ps setup缺口，四轮ECO后仍未闭合。Flow的24个完整候选都不满足本轮全部硬约束，原内部选择不能自动成为最终采用结果。保留原生筛选与所有失败，没有把“不晋升”或“执行成功”写成优化收益。

完整Flow→DPL原框架→Goal新源码→ECO四轮已正常完成、共同完整复测及入库；最终setup仍欠约76.653ps，不能采用。DPL修复后加跑的一轮三个Student都取得真实构建/布局评价，其中两个正常收尾，第三个及Teacher收尾超过预设10800s预算，原失败保留，不记作完整原生轮次成功。

## 固定条件与方法对照

工具：ORFS `5105b0a77` / OpenROAD `27288f5c90` / OpenSTA `e983e15`，镜像SHA `8e6ee7aac233da07…`。ASAP7实际15份RVT/LVT/SLVT FF Liberty文件逐hash冻结；同一原始SDC、传播时钟、完整DRT/RCX后SPEF、ns/W/µm²单位。GCD周期0.31ns，AES周期0.81ns。不是只比较同名库或不同专业自己的归一化分数。

EF探测进一步确认：镜像及Goal/ECO的最终RCX规则文件逐hash相同（`32a117e5…`）。原专业`setRC.tcl`的早期估计参数存在差异并保留，不能宣称各专业搜索环境逐值相同；最终比较读取各设计真实完整路由、同一RCX规则提取的SPEF。同方法匹配控制组沿用完全相同的原参数。探测回执见`experiments/toolchain/parasitic-identity-r2/parasitics.json`。

GCD objective_id=`39bd06296a395880b9d00601319d88b09a01fc7b945698ded9594f4bea165711`；condition_id=`3b4c2d9fc3c086bf8e9eac5e733c63601668ca92d4972d44dca66fcf1e3d7dec`。每个结果保留实际源run、专业source/binary、输入hash及三个DF快照；异条件或异设计/目标比较直接拒绝。

GCD与AES匹配复测：同一Goal原生输入、二进制、原Tcl，分别通过专业EF桥接和直接EF命令执行，再做相同完整route/RCX/共同测量。两设计各 **7项PPA差值全部为零**。回执 `experiments/gcd/native-goal-matched/matched-replay.json`及`experiments/aes/native-goal-matched-r2/matched-replay.json`。参考臂也受EF监管，没有绕过统一执行。

这验证指定固定方法的包装保真，不能推定所有搜索路径逐值相同，也不是有无平台的全量运行成本公平对照。原搜索模型、随机过程、专业评分和预算分别保留，未将不同专业分数混成综合评分。

## GCD共同最终PPA

| 方法/运行key | Setup TNS ns | 总功耗mW | 单元面积µm² | 共同验收与解释 |
|---|---:|---:|---:|---|
| ORFS `reference-r3` | 0 | 2.185011 | 56.4829 | 合法基线 |
| 仅重新布线 `routing-control` | 0 | 2.204026 | 56.4829 | 功耗越界；用于分开路由效果和专业效果 |
| Flow `flow-single-r8`显示分支 | -0.776273 | 1.348884 | 44.1774 | setup及core/die越界；全部24个候选均无可行者 |
| DPL原框架 `dpl-single-r5` | 0 | 2.030551 | 53.3336 | 合法；本轮新Student因旧构建环境失败，不能算新源码晋升 |
| DPL保存新Student源码重建 `dpl-student-replay-r3` | 0 | 2.057494 | 54.2084 | 合法，最终PPA弱于原框架；重建证实SWIG环境修复有效 |
| Goal原生固定源码 `goal-native-reference` | 0 | 2.165320 | 56.4829 | 合法无新搜索控制组 |
| Goal新源码 `goal-single-r3` | 0 | **1.378450** | **43.4047** | 合法且逻辑等价已证明；当前采用 |
| ECO `eco-single-r2` | 0 | 2.204026 | 56.4829 | 与reroute控制组逐值相同，模型没有提出有效变更；不记ECO收益 |
| Goal→ECO `goal-eco-combination` | 0 | 1.379677 | 43.4047 | 硬约束合法，功耗被Goal单项支配；拒绝替换 |
| DPL→Goal `dpl-goal-combination` | -0.0421773 | 1.179055 | 40.3283 | 新源码原生晋升，但最终setup未闭合，不采用 |
| 同轮Goal Student 2共同复测 | -0.235888 | 1.326744 | 41.3197 | 原完整性通过，但setup未闭合 |
| 同轮Goal Student 3共同复测 | -0.202762 | 1.325277 | 41.3780 | 原完整性通过，但setup未闭合 |
| 同轮Goal Student 4共同复测 | -0.280816 | 1.324968 | 41.3780 | 原完整性通过，但setup未闭合 |
| DPL→Goal→ECO四轮 `dpl-goal-eco-combination` | -0.034748 | 1.177458 | 40.3283 | setup略改善但仍欠12.899ps，不采用 |
| Flow→DPL `flow-dpl-combination` | -0.848591 | 0.897259 | 46.6560 | 真实placement→CTS接续，探索分支仍有setup缺口 |
| Flow→DPL→Goal `flow-dpl-goal-combination` | -1.02709 | 0.796381 | 40.6490 | 原四Student正常完成及晋升，最终setup未达，不采用 |
| Flow→DPL→Goal→ECO四轮 `flow-dpl-goal-eco-combination` | -1.03048 | 0.795866 | 40.6490 | 完整四专业调用/交接/入库成功，setup未达，不采用 |

表内ORFS、DPL、Goal、ECO单项及DPL/Goal/ECO组合的core/die为58.7866/78.4819µm²；显示的Flow分支为99.8001/121.882µm²，超限。完整Flow探索源取其已完成`iteration-1-1`：原配置被checkpoint保留，core/die为53.9314/71.5039µm²、满足基线范围，后续Flow接力保持该范围。各分支hold TNS/电气/布局/DRC干净，但探索源setup未闭合，Codex只选择进一步探索。它不是已采用设计。

当前Goal源码原生晋升student_4，source_hash=`294c2e3ee4d368d1949dc63fd1f288c013cc3db57e484dd3e6321b50fae342ab`，source_commit=`10e17e3a7d35f2adc284c2a2147c1ac0bbae9f34fee3e1bba6205178b27a42f3`；实际四Student、Teacher收尾与原规则正常完成。最终setup worst slack +10.2599ps、hold +29.5672ps。与原ORFS网表的Yosys证明1746个等价点、0个未证明，见`experiments/gcd/goal-single-logic-r2/logical-equivalence.json`。原Goal四项结构检查与该独立证明分别留证。

原Goal的Sfinal观察记录仍缺`metrics.csv`前置资料；原主指标、四项检查及实际晋升正常完成，但不能记作公开Sfinal评分复现通过。原失败与观察错误保留。

DPL→Goal该轮另外三个Student也逐一完成共同DRT/RCX、测量及DF入库，保存原native verdict及其源producer。四个原生候选均未满足最终setup条件，因此这轮联合收益不足并非只漏看一个较好候选；没有修改原晋升规则或把未晋升者写成已晋升。回执在`experiments/gcd/dpl-goal-student_{2,3,4}-common/`。

Flow→DPL→Goal原生新轮次正常完成四Student、原修复和原Teacher审核，晋升student_2；source_hash=`dd8e4f3ce531d51af44649a5507cb9d0e4a518c9331b294aa5c1767a866e66d4`，source_commit=`aaa175209c94e66102bdaab54faa35529ed449ee386c20acdd255003dedf0ec1`，保留power_only及legacy_setup。其最终功耗/面积下降而setup更差，不能将原晋升当作整体成功。该轮一个Student经历三次工程修复，原记录显示候选C++字符串类型/日志代码错误；没有为它修改平台公共源码或放宽原筛选。

加跑DPL `dpl-single-r6` 保留完整失败：在修复后的共同构建环境中，三个Student的新源码均取得真实原评价。首次最终HPWL分别583.0/596.8/587.9µm，评价耗时2.001/2.284/2.677s，原三条参考基线约605.9/590.4/589.8µm；这些是布局阶段指标，**不是最终PPA**。Student 1/2正常结束，Student 3和Teacher未在10800s内正常收尾；没有宣称原生晋升，也没有把部分较好HPWL当成PPA收益。原回执在其native-state/operations/orfs目录。终态检查未发现该轮残留进程，EF无运行或排队任务；历史超时记录不覆盖。

## AES跨设计与包装验证

| 运行 | Setup TNS ns | Setup WS ns | 总功耗W | 单元面积µm² |
|---|---:|---:|---:|---:|
| ORFS `reference-r3` | 0 | 0.227247 | 0.035107899457 | 1255.75 |
| Goal原生基线 `goal-native-reference-r3` | 0 | 0.22118 | 0.035017892718 | 1255.75 |
| 同方法直接EF `native-goal-matched-r2` | 0 | 0.22118 | 0.035017892718 | 1255.75 |

三者core/die=1941.63/2321.51µm²，物理条件合法。AES支持统一注册、原生top映射、原Goal基线、实际EF/DF/SDK/Query数据交付；没有在AES重跑四专业全搜索。与GCD一起说明当前接入不是固定GCD源码实例补丁，不代表所有新设计无需环境资格验证。

## 成本与预算记录

本节只列真实记录，**不推定美元花费或token节约**。缓存token已经包含在原报告input/total中，不能再相加；专业内部多次工具调用/恢复会累积到原模型用量。各专业使用其原配置模型，不是相同模型和相同搜索预算的公平排名。Query诊断用量单独保留，不计入下表专业原账本。

| 运行 | 原模型调用数 | 原报告total token | 其中cached input | 该阶段预算 |
|---|---:|---:|---:|---|
| Flow两轮12候选 | 22 | 623425 | 29056 | 10800s |
| DPL旧新源码失败轮次 | 5 | 15477879 | 14788992 | 10800s；不得记优化成功 |
| Goal新源码单项 | 14 | 9011204 | 7843328 | 10800s，一轮四Student |
| ECO单项 | 2 | 154585 | 19712 | 3600s，一轮 |
| Goal→ECO | 2 | 159334 | 19712 | 3600s，一轮 |
| DPL→Goal | 13 | 10444785 | 9191552 | 10800s，一轮四Student |
| DPL→Goal→ECO | 4 | 379159 | 39424 | 5400s，四轮 |
| Flow→DPL→Goal新增阶段 | 15 | 14720408 | 12792064 | 10800s，一轮四Student，正常结束 |
| Flow→DPL→Goal→ECO新增阶段 | 4 | 434301 | 39424 | 5400s，四轮，正常结束 |
| DPL加跑轮次已完成部分 | 3份回执 | 49418348（部分） | 48635392（部分） | 10800s截止；第三Student用量未完整报告，不能按零计 |

每条有最终结果的路线的公共EF任务数量、终态、队列等待、CPU秒、最大单任务进程树RSS和时间窗见`var/business/a4-a5-20261014/comparison-facts.json`；部分异常终态没有资源用量，缺失项单独计数，累计值只涵盖已记录部分。加跑DPL的失败和完成部分用量单独保留于`dpl-supplement-failure.json`，不与成功运行合并。时间窗是首次EF任务创建到最后终态，包括中间推理、排队及交付；不是纯工具运行耗时，组合表内每行是新增阶段，前置搜索成本不能消失。匹配控制组复用同一已资格验证binary，不能把复用构建误当成本省略。

## 暴露的问题与业务判断

1. **原专业代理目标与共同最终验收有落差。** DPL主要优化合法HPWL及位移/时间；Flow保留原CP0评分；Goal保留原power_only/recipe和晋升规则。它们收到共同目标仍需最终DRT/RCX及硬约束检验。不能因原native晋升就宣告平台PPA闭合。
2. **串行拼接不保证收益叠加。** Goal单项在本轮小设计上做了显著源码优化；DPL改变其输入后，进一步降低功耗/面积却牺牲了时序。ECO四轮仍不能补足此缺口。这是当前机制/预算下的结果，不能仅凭这些关联唯一归因为DPL，亦不能承诺增加轮数一定解决。
3. **交接覆盖、环境和搜索成本已分开处理。** 本轮DPL placement在CTS前保留hash并真实消费；原SWIG缺头文件是构建问题，旧Student失败不叫算法拒绝。保存源码重建及修复后三个Student真实评价已运行；新轮次的后续源码试验/排队/链接消耗了三小时预算，未正常收尾，不能叫完整通过。后续应针对源码增量构建和预算分配改善效率，保留原专业搜索规则。
4. **底座帮助管理而不决定优化。** 所有EDA/构建/测量/专业检查有EF回执，数据经DF/SDK回流，专业模型收到实际Query证据。排队确有成本，已避免将正常等待误算短导出执行超时；没有全局EDA互斥锁、重造harness或关闭专业机制。
5. **Query不是严格因果证明。** 比较和路径调查有原数据出处、事实/假设/未知区分。部分OpenSTA路径缺corner/analysis元数据，SDC序列化有时间戳差异，功耗活动设置不能从现有摘要独立恢复；保留这些限制。共同PPA的原冻结SDC/库身份单独核实，不伪造数据端点可比状态。
6. **长构建的EF心跳稳定性仍有真实缺口。** 最终审查查到三个构建以`lease_expired`终止（DPL加跑两个、Flow→Goal一个），原公共终态不是C++编译错误；因此不能把全部重试和DPL超时只归因于专业搜索。公共回执/时间线/原日志在`lease-failures.json`及对应`*-lost.log`。当前运行配置使用默认30s租约，心跳与guardian轮询相连；本轮未测得哪个环节拖延心跳，不能断言只有租约长度一个原因。后续应优先用可控延迟复现并修正心跳覆盖/配置，保持真实死进程回收，不盲目增加补丁或关闭保护。EF/DF的基本任务、产物、查询与协同链路可用，但**完整长构建稳定性验收未通过**。

当前合理工作方式是Codex根据证据选择专业与预算、保留分支、完整复测后采用合法较好结果；不强制每个设计经过全部Agent，也不让后续坏分支覆盖最好结果。后续提高联合收益，应先验证专业原晋升与共同最终时序之间的偏差，再决定是否单独升级该接点；不能用放宽时序或关闭原算法换取“1+1>2”。

下一优先级先处理上述EF心跳/长构建中断，再核查原专业评分与共同最终时序的偏差；本切片保存现状和复现证据，没有把新增公共底座改造夹带进已授权的有限对照提交。

## 验证和可复查入口

本机所有证据在`var/business/a4-a5-20261014/`：`comparison-facts.json`、`public-audit.json`、`public-facts.json`及各实验`result.json`/原筛选/提示/执行/采用回执。权威采用指针为`runtime/designs/gcd/incumbent.json`。失败目录和错误建议的Query调查保留。

最终公共核查：647个运行均终态（614成功、27失败、3取消、3异常lost），45份最终结果有OpenDB/指标/OpenSTA三类公共快照，覆盖GCD/AES；EF无运行/排队任务，26份原用户文件hash保持。原生开发失败、工程辅助探测错误和预算截止没有被计作成功。静态/类型/5项对照测试通过，根已有回归加本轮测试共157项通过，六模块门禁见A4及`engineering-gates.json`。

对应测试覆盖异条件比较拒绝、低功耗但时序开放结果不可记为合法、非空完整逻辑证明及原A4工程边界。Query/Toolkit/四专业回归与模块边界见A4报告。A5没有改专业算法或底座公共接口，只新增`chip_evolve/comparisons.py`、`admin/run_local_comparisons.py`、`admin/test_local_comparisons.py`、本报告及项目状态说明；26份用户修改保持。

```bash
# 使用部署client Python，所有EDA仍走EF
python -m chip_evolve.comparisons --config /absolute/path/local.json compare --reference /absolute/path/reference/result.json --candidate /absolute/path/candidate/result.json --output /absolute/path/comparison.json
python -m chip_evolve.comparisons --config /absolute/path/local.json replay-goal --result /absolute/path/native-baseline/result.json --key new-matched-key
python -m chip_evolve.comparisons --config /absolute/path/local.json verify-logic --reference /absolute/path/reference/result.json --candidate /absolute/path/candidate/result.json --key new-proof-key
```
