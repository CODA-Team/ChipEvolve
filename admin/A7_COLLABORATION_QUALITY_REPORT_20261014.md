# A7：专业阶段证据与条件协作

状态：比较/诊断增强、三候选阶段查证、真实Query调查、四轮ECO/控制及AES公共接点验证通过；ECO没有新增收益，已按原Goal能力进入一轮四Student时序恢复续作。其最终PPA及重放待验收，A6的新DPL完整轮次独立继续。

## 已查明的业务问题

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
