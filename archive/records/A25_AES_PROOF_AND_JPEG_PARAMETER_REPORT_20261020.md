# A25：AES全输出证明分区调整与JPEG参数实测

上轮为已核实的同任务计算等待，本轮补齐实际模型/分区诊断，使用现有证明选项进行一次明确策略切换，并收取JPEG20%最终控制。没有新增平台框架或修改产品源码；A25仍未冻结，A26–A28未完成。

## JPEG：调参数有实际效果，仍未通过时序

20%控制已完成原生、完整DRT/RCX、ORFS/OpenSTA交付。独立从公开EF注册测量归档核对九捕获，按原native JSON与唯一report_power总值恢复七PPA，再与宿主及公共SDK逐项同值。结果如下：

| 相同last_gasp配方、无新C++ | 80%匹配物理控制 | 20%新控制 |
|---|---:|---:|
| 功耗mW | 155.25515378 | 155.32861650 |
| 单元面积um² | 6378.88 | 6382.38 |
| setup TNS ns | −0.573876 | −0.196260 |
| 最差slack ps | −30.8414 | −13.2240 |
| hold TNS ns | 0 | 0 |
| 原setup约束 | 不通过 | 不通过 |

相对80%控制，20%最终最差slack改善17.6174ps、绝对TNS减小约65.80%，功耗增加0.0473174%、单元面积增加3.50um²，core/die不变。这支持该输入上的策略校准价值，但还差13.224ps才能闭合时序，不采用，不作团队优势或正式收益结论。

原生成Tcl只变80→20和输出目录，二进制c2ff1adc…及源/库/RC/SDC/目标保持；80%的最终物理控制与原无源码父状态的注册native字节对应证据保留。该比较没有混入27f81fd6路径兼容二进制。此前实际接受动作仅9774→9730，减少约0.45%；这次最终结果说明动作数量不能单独代替动作内容及后续物理影响的判断，也不证明哪个具体单元是唯一原因。

新测量为run-c11ea0e502ef4b1689fd4f824d129ffb，物理为run-0c48727de91241a6b46fd3ed7bfcf498；独立依据为`var/business/a25-jpeg-effective-reclaim20-20261020/independent-reclaim20-final-acceptance.json`。复用已通过静态/真实读取的私有公共原件审计器，无新模型、优化或EDA重跑。

下一次专业决策应能消费这些已完成控制，在真实Flow父状态的新Query诊断后选择专业配置；不把80%视为必须锁死，也不由旧输入的一次改善直接规定所有新设计都用20%。当前未派发接力的固定输入仅含此前三控制，20%反馈及可选策略配置仍需在安全重绑窗口明确交付，不能声称已经进入其Teacher。

## AES：零状态匹配的实际原因

原EF证明run-ef79b04a799d4f30896f502e72deba99此前确实运行，四个原ABC-PDR PID/start ticks与持续CPU增长均已核验。完成的是done分区，其余数据输出没有得到证明；活跃计算不等于全129输出通过。

实际原配置equivalence_match_flops=true，但proof-state-matches计数0。读取既有解析模型确认：参考含530个L/R型触发器，当前独立综合来源含562个SL型触发器；实例名称也由u0等变为RTL派生名。现有匹配策略要求相同实例名和master模型，因此没有可用状态对应点。这不是参数漏传，也不能据此认定设计不等价。

进一步读取四个正在求解的数据输出分区样本：每份都含65056个参考原语单元与71448个候选原语单元，单份IL约23.76MB；样本之间内部别名映射值超过99.9%相同，仍存在14/18项等局部差异，未宣称图或文件完全相同。该证据支持尝试减少重复全局求解，不保证合并后更快。

原模型与诊断证据在`var/business/a25-actual-flow-query-goal-correct-archive-20261020/`的AES-proof-zero-matches-model-diagnosis及AES-proof-running-partition-overlap；本轮精确样本比例另在新证明specification的shared_primitive_cones中。初始准备错误要求全部别名映射完全一致，被预检拒绝；随后按实际超过99.9%记录，原失败稿和diff保留，没有修改运行中的证明。

## 一次既有整体证明策略切换

使用已有私有配置validation.equivalence_merge_partitions=true。该原生EQY选项已在A24完成GCD全部18输出/一个完整分区的真实验证，产品三项相关检查本轮再次通过。新旧AES生成的proof配置独立对照：移除唯一新增的`[partition *] / merge *`块后逐字相同；库、两份网表、全部端口、PDR、xprop、固定Z3、14400秒预算及32GiB声明保持，没有新增状态假设或删输出。

这是一项明确的分区策略替换，不因观察超时将旧任务当作停止。通过公共EF取消原任务，原状态保留cancelled及实际费用；原owner3434644正常收到失败后结束，没有重跑源综合或物理复制。18个登记的原EQY/ABC及子进程逐PID/start ticks核验均已退出，原服务和无关进程不动。

新主管1575738/start_ticks861233872，在独立key a25-aes-full-native-domain-all129-merged-r1下，调用现有verify_outputs。除原验收外，返回后还需从实际partition JSON的outbits逐位确认done及text_out全部129位覆盖、全部分区PASS、无未证明点；然后核对原来源/复制七PPA及SDK，并完成该来源的环境资格。当前仅处于新证明准备/排队阶段，尚未获得PASS。

新增私有worker通过Ruff F/I、格式、实际client解释器Pyright和真实无派发预检；最初测试调用使用了未装pytest的client解释器，未安装包，改用既有检查环境后3项通过。该策略切换只做一次，不设置失败后自动换第三种证明或修改平台的循环。若失败，保留同一案例和原始结果进行具体诊断。

证据位于`var/business/a25-aes-whole-output-proof-20261020/`：specification、proposed-proof、old-proof-cancellation、launch/receipt及independent-strategy-switch-acceptance。原所有证据和实际失败保留。释放原任务后，公开EF已观察JPEG最终测量及原Flow评价恢复运行，主搜索未重开、deadline及候选数未改变；这不是正式效率成绩。

## 成本、边界及剩余任务

r64从r63已计费ID去重，新增7终态（6成功/1明确取消）、采样CPU5853.56秒、未知attempt用量0，另观察7项未终态。包含原AES实际计算，不能因策略替换丢掉费用；新验证解析/证明任务也按实际EF终态继续计费。没有新模型、原来源综合或专业优化搜索；服务/准备/测试/读回/主Codex费用仍未完整观测，不填零。

仍需完成：新AES全129证明及环境资格；JPEG其余策略最终交付和20%反馈进入实际专业决策；GCD精确SDC与JPEG选中源码的最终复测；原完整健康JPEG2×50；完整原生参考及真实Flow→新Query→Goal；合格来源/实际AST/EPD/模型/停止与冷暖状态冻结。之后执行A26 PPA、A27同Codex同完整业务及A28审计。团队PPA无需与单项同总预算，保留原硬约束和全部成本。

根仅修改本报告及TASKS.md。34项当前证明固定输入和26份用户保护文件已核验；没有修改、执行、stage或部署受保护用户评测代码、DF/DI工作修改，没有产品签名、数据库、服务或全局资源池变更。
