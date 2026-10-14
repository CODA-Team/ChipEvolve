# A7：专业阶段证据与条件协作

状态：A7工程验收通过，老板业务验收待确认。原Teacher/四Student/review正常结束，无新源码晋升；既有组合父源码切换到原生power_then_timing后得到合法更优结果，逻辑等价、空目录重放、DF/SDK与真实Query反馈均通过，已采用。以下先给最终交付，其后保留过程与历史失败。


## 最终业务交付（2026-10-15）

| 指标 | 旧合法Goal单项 | A7新结果 | 变化 |
|---|---:|---:|---:|
| 功耗 | 1.3784497 mW | 1.1775332 mW | −14.5755% |
| 单元面积 | 43.4047 µm² | 40.2700 µm² | −7.2220% |
| setup TNS | 0 ns | 0 ns | 保持闭合 |
| 最差setup裕量 | +10.2599 ps | +11.5930 ps | +1.3331 ps |

共同条件为ASAP7 FF、310ps、固定实际库/SDC与完整DRT/RCX。hold、slew/cap、布局及DRC通过，core/die为58.7866/78.4819µm²不增。相对ORFS固定基准，功耗−46.1086%、单元面积−28.7041%；setup裕量低于ORFS，但仍满足原约束，不能说所有时序指标均比ORFS更好。

原四Student的recipe匹配gain分别−0.00279132/−0.09242549/0/−0.00368106；第三项机制未激活。原Teacher正常复盘，保持所有评分/晋升规则，无新源码晋升。父源码a9a8fc8…/cc9419aa…不变，原框架完成power_only→power_then_timing阶段重测并更新checkpoint；本轮收益来自这条已有专业机制，不算新Student C++成果。原DPL→Goal输入继承与产物hash保留；这是GCD实际组合分支较旧最好单项的改善，不是同总预算公平对照或四Agent普遍优于单项的证明。四轮ECO与route-only控制仍七项同值，ECO没有新增收益。

完整原生续作在预算内正常结束，最终run-8552eaed8e7a45c98551679eac1bb288入库；空目录重放run-7d0283ffa2d8477aa9a60c65be0b7b0b七项PPA逐值相同，六个SDK scope及摘要/指标身份核查通过。新结果已由Codex采用，旧incumbent及失败分支保留；当前使用var/business/a7-quality-20261014/production-runtime/local.json。

逻辑证明run-4bae10bf2cf843ac955d711be6efba57覆盖全部18个顶层输出位，未证明项为零。原默认证明先遇到TAPCELL/FILLER缺SAT模型；补充证明从EF生成的Yosys JSON核实零端口连接，仅在证明模型中排除这些物理单元与无功能的scope元数据，并隐藏内部名称以免要求可交换引脚逐名相等。Liberty、顺序电路归纳与equiv_status -assert保留，实际网表/ODB/约束未修改。完整脚本、解析JSON、排除类型与日志保存于a7-output-proof-r2；这是固定Liberty数字逻辑证明，不替代物理验收。默认逐内部名证明仍可能对合法换脚过严，输出证明流程由Codex执行现有EF工具完成，没有新评测服务；通用CLI是否增加此选项留给后续独立决策。两个不完整模型尝试及原失败日志保留。

真实Query最终PPA调查inv-3b18c9cb450346868ae8fae89cb0e127提供10条确认事实；首次没有发现已登记stage/Teacher分析子项。根诊断入口现通过既有公开EF接口列出绑定固定run的成功analysis及raw_flow_metadata引用，不扩大权限。补充调查inv-9430303dd2d341c8b682e33188647c5b/a772ffce…提供11条事实、0假设，已实际读到原规则与阶段证据：repair_power开放setup、placement恢复、native GRT再次开放、最终DRT/RCX恢复。观察不证明某一参数唯一因果。它是同一Codex的领域证据增强，不重造通用harness。

EF最终381项通过/1主机条件跳过，根最终175项回归通过；新增源文件lint/格式/pyright、逐文件差异及边界检查通过。A7审计112项运行全终态（104成功/6失败/1失联/1取消）；失联发生于托管锁修复前，事故唯一阻塞位置仍不能从旧回执推出。新wheel的真实979秒链接、120MB输入/产物及默认30秒lease跨35秒托管测试通过；活跃原轮次收尾后升级本轮服务。26份用户文件原hash不变，临时资格服务已停止，数据与失败保留。AES只验本片公共接点/固定方法与Query，七项PPA同值，不宣称AES四专业全搜索。

权威回执：var/business/a7-quality-20261014/acceptance.json、closeout.json、adoption.json、continuation-vs-incumbent.json、continuation-vs-orfs.json、continuation-empty-replay.json、continuation-logic-output.json、final-sdk-query.json及两份final-*-diagnosis-receipt.json。

## 过程记录：已查明的业务问题

DPL→Goal的时序退化首次可见于Goal的功耗优化阶段，早于最终布线。原生父源码的evaluation_mode是`power_only`，晋升并不代表最终setup可行。原生placement/GRT估计与最终DRT/RCX的分析条件不同，原算法、原指标与原晋升均保留，Codex单独判断采用。

| 阶段 | Goal单项TNS / WS ns | DPL→Goal TNS / WS ns | 同轮另一Student TNS / WS ns |
|---|---|---|---|
| pre_repair | 0 / +0.0231921 | 0 / +0.0232460 | 0 / +0.0232460 |
| post_repair_design | 0 / +0.0231921 | 0 / +0.0232460 | 0 / +0.0232460 |
| post_repair_power | 0 / +0.0061621 | −0.135796 / −0.0210309 | −0.310255 / −0.0236192 |
| post_placement | 0 / +0.0109810 | −0.0829742 / −0.0151664 | −0.257079 / −0.0176171 |
| native post_route | 0 / +0.0023597 | −0.410836 / −0.0288806 | −0.666620 / −0.0312567 |
| final DRT/RCX | 0 / +0.0102599 | −0.0421773 / −0.0133413 | −0.235888 / −0.0164200 |

这是阶段命令前后的真实观察，不是“某个参数唯一导致”的证明。合法Goal单项继续作为incumbent，没有被更低功耗但时序未闭合的组合覆盖。

## Query提供的决策依据

原生日志来自EF已注册的`data_snapshot` ZIP中的`evaluation.log`，核验ZIP和成员hash；不是空的外层`extractor_log`。三份plain日志/阶段JSON经既有EF接口登记成只读analysis产物，使用既有`analysis_of_run_id`归属当前固定最终scope，因此Query无需扩大读取权限。

真实Codex调查：`inv-ee472ee8035548859927da491c34d559`，context_id `db60ddaddc973d3f8b66b8292b6e7332f6297e826cd4134ab28955a9b68f8a9a`。上下文9条确认项含重复项，2条假设；引用阶段原始产物、DF的最终指标/路径和原始报告，并区分事实、机制支持及资料缺口。本片不额外修复重复确认项。

Query核查了全部已存setup路径，并从原始报告确认最差的是`u31/QN→resp_msg[15]`，属于虚拟时钟输出组，缺约13.34ps；两侧required一致，候选arrival更晚。完整路径包含36个点：数据单元增量较参考更大，u32/u33/u34/u129等RVT单元及其驱动/负载值得检查。候选部分点反而更快，因此不能说整条路径每一级都退化。

两个可复用的查询要点进入了领域提示：按`sort=slack/order=worst`跨全部组查询，不把记录顺序当成全局最差顺序；point响应`truncated`时，使用分页或`get_timing_points`读全，不将`detail=full`误当无限返回。公开SDK的排序与分页本身可用，没有修改DF/DI。

ECO默认报告只聚焦reg2reg，但resize/Vt/buffer原语仍可能作用于实际输出路径。Query建议一次有边界的原生ECO，并保留原源码范围/原评分；失败后才考虑Goal已有的时序恢复机制，避免重复派发缺乏适配依据的工作。

## 当前实际动作与范围

- `a7-targeted-eco`：四轮、5400秒，输入为已有DPL→Goal结果，实际新Query上下文送入原ECO提示；整个会话继续由EF监管。
- `a7-routing-control`：相同源结果，仅做完整route/RCX共同测量，不加入优化；用于区分重新布线与专业操作。
- 偏好是在时序闭合的同时保留功耗不高于合法incumbent的0.0013784497278W、单元面积不高于43.4047µm²；原公共objective的硬条件不变。
- 如果新结果合法且有价值，再做独立逻辑等价与空目录重放；没有增益时保留incumbent。实验结束前不声称联合收益。

### ECO与控制的实际结论

四轮ECO正常结束，实际Codex提示包含本片context_id和u129等路径事实；不是上下文未送达。四次模型回复均为原生只读probe，没有实际resize/Vt/buffer变更；原live报告/allowed实例仍聚焦reg2reg。最终setup TNS/WS为−0.034748/−0.0128986ns、功耗0.0011774579762W、单元面积40.3283µm²，与不改动route控制7项PPA逐值相同。因此不记ECO新增收益，也不能把上一轮同值结果的小幅变化单独归给ECO。原约束不放松，incumbent保留。

### 原Goal的时序恢复续作

`a7-goal-timing-continuation`使用已有public CLI的initial_parent字段导入验证过的a9a8fc8…/cc9419aa…父源码、原metrics和原checkpoint；原benchmark、baseline、targets、权重、hard_metrics、promotion、power_stage_tns_ceiling及protected rounds不变。父源码已满足原两项功耗目标，原PowerFirstPromotion自动选择timing_recovery，真实日志已启动`power_then_timing`阶段基线复测，然后原Teacher/四Student/审核继续。预算6小时、只新增一轮，不改算法或筛选规则。

新增`admin/continue_goal_timing.py`是本片有限原生续作/验收驱动，所有构建/版本/原检查/物理都沿用EF桥接，结束后共同复测及DF入库。测试确认原契约字段逐项保留；不是新评测服务或新通用harness。

### 续作状态查询故障及最小修复

首轮阶段基线的真实EF链接任务`run-9e8d48372c2b4946898a349363238683`于18:11:22 UTC启动，18:30:09被桥接主动取消。原delegate把一次60秒GET超时当成执行失败；公开服务随后仍健康，取消回执明确为cancelled，不能归为租约失联或C++错误。共享主机当时约247GiB内存已用、swap满、系统负载约100，此为环境观察，不证明唯一超时原因。

最小修复限定Goal平台桥接：已经成功提交的任务，状态读取遇到KernelUnavailable最多尝试三次，逐次保留只读观察错误，服从原实验deadline；不重交任务、不延长算法/工具预算，不吞掉其他错误，最终仍走原取消路径。新增三个测试覆盖恢复不重交/不取消、持续不可达停止及原截止时间。原生不安装EF客户端的测试环境按依赖跳过该三项；已安装公共SDK的独立环境实测13项桥接测试通过。没有改动Teacher、四Student、评分和晋升。

新`a7-goal-timing-continuation-r2`保留失败目录与契约，19500秒续作预算早于首轮原截止时间；不在历史目录替换源码或失败证据。其最终业务状态继续按真实实验收尾记录。

### AES相关接点

新EF下AES原Goal固定方法重放及完整DRT/RCX实际完成：7项最终PPA与A5固定方法逐值相同，三个公共scope均为design_id=aes/native top=aes_cipher_top；SDK指标查询通过。真实新Query `inv-9693a3dd29424e83b12e240d5bf241c2`导出context_id `2b86f0a79b10325f21e08f5419c8af63bd77c3d141c85e8be88e7317faf9749a`，确认可行基线并建议不做无必要ECO，未冒称AES四专业搜索。新调查从A7独立结果副本进行，原A5结果不改写。

## 文件职责与接口影响

| 文件 | 变化 |
|---|---|
| `chip_evolve/comparisons.py` | `professional_facts`同时给出原native_method和最终PPA/约束，compare返回两侧事实；不新增评分 |
| `chip_evolve/diagnosis.py` | 准备原判定/最终条件；提示全组排序、ECO默认关注范围及原能力边界，沿用原调查与context导出 |
| `chip_evolve/jobs.py` | 根内部command新增可选analysis_parent/extra_paths传递，用已存在的TaskSpec标签和原始产物声明登记证据；原调用默认行为不变 |
| `admin/run_local_quality.py` | 有限Goal阶段日志取证及归属登记，source/成员/结果身份可复查；不新增优化循环 |
| `admin/test_local_quality.py` | 阶段符号/完整性、内部晋升与最终可行性分离、分析归属与产物声明回归 |

jobs.py是根组合层共用接点，影响其所有命令委派；修改只透传既有语义，不改公共EF/DF HTTP、SDK或数据库。没有修改专业算法、晋升规则或第三方来源，也没有另造评测服务/harness。

GCD实例名称只出现在本片实际证据/实验上下文中，未写入通用业务代码。阶段collector识别原Goal的明确checkpoint格式，不能自动宣称已覆盖其他专业所有阶段。

## 证据与检查点

主目录`var/business/a7-quality-20261014/`：三个`*-stages-r2/stage-evidence.json`、`diagnostic-question.txt`、`diagnosis/`、`diagnosis-receipt.json`、`dpl-goal-paths.json`、`worst-path-full-points.json`和后续真实验收回执。

首次三份取证误选外层空日志而失败，失败目录保留；r2改为原注册ZIP成员，未伪造阶段。新调查trace已复制到A7，旧A5诊断指针按原字节恢复，原物理结果和失败不改写。原缺失corner/analysis/unit元数据及严格逐edit反事实缺口保留。

根静态/类型/格式、差异/边界及回归检查与真实结果在最终收尾补齐。AES只验证本片相关公共接点与反馈身份，不在本片重跑四专业全搜索。公开benchmark、Tutorial和token节约第五项继续排除。

截至续作启动，根回归167项通过，新代码Ruff/格式/pyright通过。最终真实收尾另记，不把这份工程检查点当作联合优化已经成功。


续作r2的原两个LTO链接尝试分别以resource_exceeded结束，公开进程树RSS75,676,360,704/96,423,223,296 bytes、35/42进程，超过原64GiB；不是心跳或模型错误。EF只读检查镜像编译器wrapper及GCC dry-link，确认同一链接同时携带-flto=auto/-flto=1。平台bridge仅在明确两旗冲突的单行链接中移除auto，把已有显式单worker要求落实，继续使用原-O3/LTO/源码/库/输出与工作目录；多行静态归档及仅auto调用原样。原脚本作为冻结输入登记，实际执行argv进入leaf receipt。新增两项测试覆盖参数边界/不改其他调用及链接输入hash。r3预算17500秒早于原截止，失败r1/r2目录保留，实际内存改善和正常轮次仍待验证。

Goal完整既有回归393通过/3依赖跳过，桥接SDK环境13通过；LTO修复后桥接15通过、专业单元回归通过，未重做不受修改影响的八份历史源码归档hash校验。记录在var/business/a7-quality-20261014/goal-regression-qualified-final.log与goal-regression-lto-final.log。首次误用Query环境缺tree-sitter、代理导致dashboard 502及错误测试目录的门禁失败保留，改用原Goal环境且本机HTTP不经代理；未据此修无关业务代码。


r3真实验证：链接run-8438816f49c940c8bad0c361a9be9657于19:16:05–19:37:43 UTC正常成功，实际leaf argv只含-flto=1，峰值RSS4,821,483,520 bytes、10进程；CPU1266.35秒，链接1297.4秒，原64GiB配额未增。相同父源码的power_then_timing基线通过，原生TNS abs由0.410835504532降至0.00229744007811ns，dynamic power1,232,783,159.821338pW、leakage993,289.404505pW、DRV0。它是原生阶段估计，不代替最终共同DRT/RCX或FF约束；Teacher/四Student继续，原targets/promotion未改。

A6新DPL完整轮次已正常收尾，无源码晋升：Teacher识别第一候选orientation/pin回滚缺陷，即使HPWL领先也拒绝。公开分析产物run-3929c0eec11d49a29a7b6927057b9293归属于最终run-ca33897503094510aae669c6f6c78c45，文本hash经公开ZIP核验。新DPL默认方法的合法最终PPA也未优于原Goal单项，不替换incumbent。


## 收尾可靠性复核

A6首批42次运行的“无新增失联”只对该批成立。A7 Student3链接`run-68f0cf01a0a34db5b56d90443eb133e5`于20:30:30–20:55:30 UTC以lease_expired结束，失联前有两次公开GET超时；任务声明7260秒，不能归为声明超时。原生重试后来成功，此失败原样保留。已有公开回执不足以证明这次事故的唯一阻塞位置。

源码和可控测试进一步确认：`RuntimeStore.register_artifacts`在共享连接锁内校验、复制产物，能挡住别的attempt续租。测试修改前失败，修改后通过。补充修复`dd56c15`把文件托管移到锁外，所有元数据仍在一个事务中提交；重复声明失败时无部分记录，原对象内容校验、路径边界、取消与fencing不变。两项相关回归通过，完整EF回归378通过/1主机条件跳过，类型和11项尺寸/层级门禁通过。store净增3行，1498行/core 9022行的具体审批留存，不扩大其他文件限额。

新wheel在独立临时EF验证服务中完成真实120,460,336字节专业ELF托管及并发OpenROAD身份调用（run-efe47752a1514189bb2c8c26a5ec9063/run-cee79edd9b0d49528bd0df9fce466941）；真实长链接与默认30秒租约测试继续收尾后补记。生产服务仍保留活跃原Goal轮次，先不在活跃进程中替换运行代码。对这次历史事故的完整唯一根因不作过度结论。

同一锁机制也在ingest_input_file/ingest_input两条输入托管入口被可控复现：修改前两项失败，移出文件I/O后全部通过。不增源码行数，不改返回字段或事务；最终存储55项、完整EF381项通过/1主机条件跳过，类型/边界门禁通过。最终r2 wheel保留于var/business/a7-quality-20261014/runtime-wheels-r2，前一wheel及其真实长链接验证不覆盖。

## 未晋升输出的真实来源交接

原续作收尾只在本轮operations找选中checkpoint的EF捕获；未晋升、沿用导入的原checkpoint时，没有本轮新生产者，严格校验会拒绝收尾。新增checkpoint_producer：只有源码hash与原导入父项一致、ODB hash与原已验收输入一致时，查原实验的实际EF physical捕获；任一变化就查本轮，缺失仍报错，不把final metrics的run_id当作来源。三个分支测试及根170项回归通过，新文件Ruff/格式/pyright通过。

真实公开验证从本轮EF生产者的注册data_snapshot ZIP找到与阶段重测后选中ODB相同hash的成员，证据见var/business/a7-quality-20261014/inherited-checkpoint-evidence.json。活跃旧Python驱动已加载旧代码，若其在原生正常结束后被严格producer检查拒绝，只续做共同测量/入库，保留收尾异常、不重跑Teacher/四Student，不伪造leaf记录或修改专业算法。

## 最终改动清单

- chip_evolve/diagnosis.py：发现固定scope内已登记分析证据并交给Codex。
- admin/continue_goal_timing.py：有限原生续作、继承/新checkpoint生产者及实际测量方法。
- admin/run_local_quality.py：从注册日志提取阶段事实，以选中方法验证指标。
- admin/verify_long_task_reliability.py：空目录验证可显式复用实际冻结PDK。
- admin/test_local_quality.py、admin/test_long_task_reliability.py：对应来源、模式、证据发现与PDK回归。
- PROJECT.md、ARCHITECTURE.md、TASKS.md、admin/NEXT_RELIABILITY_COLLABORATION_PLAN_20261014.md：同步最终目标/边界/状态，保留原验收标准。
- admin/A6_LONG_TASK_RELIABILITY_REPORT_20261014.md、admin/A7_COLLABORATION_QUALITY_REPORT_20261014.md：实际验收、失败与范围。
- execution-foundation gitlink、SOURCE_MANIFEST.json：固定已推送EF修复15d9586及来源tree；其他模块指针/用户修改保持。

运行数据、wheel、凭据、镜像和环境均留在var，不纳入Git。模块内实际改动为store/lease/runtime与对应测试及精确尺寸审批；本轮Goal桥接的GET观察和显式LTO冲突修复已在独立模块提交，不改专业算法。
