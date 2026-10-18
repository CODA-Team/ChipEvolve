# A25：同任务续接、四候选最终交付与下一棒

2026-10-19凌晨。JPEG Goal原一轮及全部四候选的共同物理/DF/SDK交付均已完成；原GCD完整域2×50已开始。四候选都违反setup约束，没有采用。A25未冻结，A26–A28未执行。

## 实际业务结果

共同FF/545ps、完整DRT/RCX下，四候选的原日志、公开EF父子身份、单次attempt、全部指标及实际快照作用域已独立核对。原参考是178.33724618mW、6734.18µm²，原目标与时序/电气/布局/DRC约束不变。

| 候选 | 最终功耗mW | 单元面积µm² | setup slack ps | hold slack ps | 最终可采用 |
|---|---:|---:|---:|---:|---|
| Student01，原Teacher晋升 | 156.00880980 | 6385.85 | −13.1307 | 21.0726 | 否，setup失败 |
| Student02 | 155.03130853 | 6378.88 | −30.8414 | 22.5453 | 否，setup失败 |
| Student03 | 150.86801350 | 6243.33 | −12.5853 | 9.33334 | 否，setup失败 |
| Student04 | 154.73461151 | 6380.34 | −28.6949 | 21.2735 | 否，setup失败 |

四份DRC均为0；原电气/布局及其他硬条件逐项检查通过，setup是当前共同缺口。原4/4结构检查不是完整输出证明。

Student02与独立无改源码power_only控制的五阶段网表和post_route ODB逐字节相同，两个原生producer归档均已核对；Student02对这一相同checkpoint的实际最终测量可供控制引用。真实父run仍是Student02，不改名、不算两次物理执行或独立重放。

Student03相对这个同模式控制的最终功耗再降2.68545436%，相对原参考降15.40297009%。这是有控制证据的一次观测，尚未成为可采用的PPA收益。Student03功耗、面积和setup优于其他候选，但hold余量更少；它是下一棒的优先探索来源，不能直接宣称团队成功。

## 已恢复的真实中断

原R9在一次状态读取持续不可用后，从业务CLI收到3（durable pending）。外层只接受0，把仍在运行的Student02详细布线误当终止，后面三个未派发监督也随之停止。原回执/错误全部保留。

R10通过原`resume --design jpeg --key a24-jpeg-goal-healthy-r2`接回同一交付。公开EF证实原物理run `run-529d44ea746048c0b76c6807a4b0cffc`只有原attempt一次，物理/测量/SDK完成；原原生轮次、11份prompt及模型用量没有重开。随后原GCD命令完整执行，轮数/每轮候选数/原预算不变。

后续已改为一条串行续接：R10退出成功→post-r5安全启用/94份JPEG事实恢复→qualification-r5真实资源资格→matched-r4五组物理控制。旧post-r4/qualification-r4/matched-r3均为已停失败原件，不再等待或重启。业务命令返回3时只对相同key续接；真正非零失败仍保留并停止该阶段，不重开搜索。固定方法、控制病例、源码与预算比较已通过，三个新入口干运行通过。

## 客户端监控的最小修正

隔离分支`a25-diagnostic-observation-20261019`的608a53f、fe61dd0仅修改：

- `chip_evolve/lifecycle.py`：已读到running时，辅助health/resources诊断的瞬时失败不再推翻这个事实；继续原间隔观测。queued工作保持原有有界失联/worker/资源判断，真正run读取失联和执行失败不隐藏。
- `admin/test_auxiliary_execution_observation.py`：6个运行/排队/间隔/编程错误场景。

初始5失败/1通过；修正后29项相关、481项根回归通过，类型检查零错误/警告，格式/F规则/差异与边界检查通过。完整回归首次缺少隔离原模块源码/准入资料，7失败/474通过；从根gitlink恢复原始资料及独立wheel环境后，原7项及全部481通过，未删改测试规避。

新客户端另在实际GCD物理run `run-138c85fddfa748e8b482ff7eb46e05aa`上接受一次辅助health故障注入，保持同一attempt观察34.513秒至成功；没有新EDA、模型、资源或profile变更。首次探针的目标已先完成，提前退出，未计资格。该验证不证明先前真实120秒读取问题的唯一根因，也不把机械盘长尾记为已消失。

修复尚未切到主版本；已加入post-r5的安全启用清单，待R10结束、EF空闲后合入并跑根回归。原三份来源/资源修复及随后真实物理资格均保留。ba4d51a的Code物理内存候选仍独立等待真实混合负载/PPA资格，没有提前启用。

## 正确交接Student03

Student03的对象事实已通过原EF导出→DF导入补齐，原result字节、测量run和PPA保持；冷建库耗时留在运行回执，不藏在Query成本之外。

当前Codex使用Query host完成8次有作用域读取、131,382bytes，交付4组事实/1组假设；公开SDK独立核对三个角色共8个快照作用域与全部共同指标。候选原参考与同模式控制各自角色固定，没有嵌套模型或新EDA。当前宿主推理与服务费用不记零，这不是A27效率成绩。

Student03最差已存路径是`ddin[6]/QN → dct_block_3.dct_unit_3.macu.mult_res[18]/D`，不是Student01的ddin[7]路径。46数据点的相邻增量含cell分类461.5ps、wire分类45.4ps；hold最小约9.33ps。15setup/5hold样本及23个未解决net关联的范围明确保留，不伪造全路径/全对象归因。

下一棒应让原生TimingECOAgent检查其现有reg2reg动作适用性，使用Student03自身产物和上下文；若其动作不能作用于真实瓶颈，再用原Goal时序机制。实际接力、全硬约束、27输出PDR、独立物理重放及最终采用仍待执行，不把推荐当收益。

## 新确认的专业初始化缺口

源码和原件共同证实：实际timing_only参考基线的artifact没有mode字段，初始parent被标为unknown，进入了原控制器为legacy unstaged p0保留的bootstrap。独立同模式无改源码控制已满足原两个功耗目标，但时序尚欠；现有控制器在正确mode匹配后本来会重算上下文并选择已有时序恢复阶段。

下一步仅补已实测基线的真实mode/recipe及未晋升baseline parent的事实身份，保留原目标、评分、阶段/晋升算法、旧结果和缺metadata历史行为。拟改Goal原生`evaluation/contest2026.py`、`cli.py`及对应测试，直接/平台共用；目前尚未实施，必须经新完整原生轮次验证，不假定能改善最终PPA。

正式冻结前仍需：健康JPEG完整Flow（94/100超时恢复不算完成）、资源及注册来源控制、上述初始化纠正、真实专业接力、完整证明/重放、全部成本校准，然后执行A26/A27并交付A28。

运行证据：`var/business/a25-dpl-operation-resources-20261018/`内`goal-complete-common-cohort-r1/acceptance.json`、`goal-control-common-and-recovery-r1/acceptance.json`、`goal-student03-query-host-r1/independent-acceptance.json`、`goal-measured-baseline-mode-audit-r1.json`；客户端门禁与实际观察位于`var/business/a25-diagnostic-observation-20261019/`。权威续接是R10及其single following pipeline，详见该目录的`CURRENT.json`。
