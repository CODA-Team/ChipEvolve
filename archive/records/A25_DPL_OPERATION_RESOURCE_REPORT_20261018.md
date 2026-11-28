# A25：私有构建的资源预约与并发资格

新发现的效率瓶颈来自平台配置：三次成功的DPL私有候选构建，进程树内存峰值分别为4,896,727,040、4,921,700,352、4,897,959,936 bytes，却各自预约32GiB，恰好占满当前执行池。第二个Student的构建、先完成Student的布局评价因此等待。执行底座是在按约定调度，没有卡死；预约粒度需要区分完整工具构建与私有重链接。

## 改动和边界

隔离DPL候选97466b0在原线程预约候选8940667上增加一个私有配置接点：已有profile.resources先查操作同名项，没有则仍按build/physical回退。可以只为variant_build设置资源，而不改变完整构建和其他操作。显式原生线程数仍参与CPU预约的较大值计算，原CLI、算法、线程选择、时限和公共EF接口不变。

文件清单：scripts/platform/execution.py选择已有资源映射；validation/test_platform_execution.py新增四种操作的覆盖与回退检查。新增场景修复前仅variant_build失败，修复后validation全部47项通过，Ruff F/格式/差异及生产文件Pyright basic零错误/警告。候选已发布到ChipEvolve的modules/dplevolve-a25-operation-resources，主DPL和当前r7均未切换。

没有建立新资源管理器或新Agent harness。数据流仍是原Code helper→私有profile→公开EF TaskSpec→原产物→DF/SDK。配置由平台准备，专业Agent继续使用原构建与评价命令。

## 已验证与尚未验证

用真实89份框架源码构造实际request、TaskSpec和容器命令，确认10线程请求预约10核/16GiB，完整构建的默认32GiB保持，原5400秒叶任务期限、单次attempt和只读共同源码绑定保持。只做公开SDK读取及命令组装，没有启动构建或模型。

16GiB约为上述单任务采样峰值的3.49倍，只是待资格验证的私有重链接配置；不能据此保证所有新源码的峰值，更不能套用于完整/冷构建。当前r7仍使用原32GiB预约，历史费用和排队不回写。

## 真实资格验证已排队等待

PID4045467当前只等待既有r7及JPEG超时证据交付成功；随后还须确认前序监督已退出、公开EF空闲及全部输入哈希不变，才执行：

1. 将同一89文件框架各冻结一份到私有目录，用原delegate入口提交两份10线程/16GiB构建。要求两份实际成功、各只执行一次，公开EF的开始/结束区间真实重叠，CPU预约均为10核；同时保留整个构建/排队观察轨迹。
2. 将这两份构建产物分别交给已有DPL业务replay入口；保留原8线程物理评价、共同工具链、三条原基线、完整CTS/DRT/RCX及公共数据交付。没有Teacher/Student新搜索或模型调用。
3. 核验私有框架的原生HPWL与原框架控制相同，两份最终七PPA和DRC一致、布局合法、源码身份/EF产物及DF/SDK事实对应，按run/attempt去重记录已知费用。它验证资源接点和真实业务可用性，不宣称新PPA收益、功能证明或采用。

前序失败时本探针停止在诊断，不插入EDA、不重复搜索。构建沿用原单任务5400秒；两份构建监督和后续两份业务重放分别显式设4小时窗口，等待前序的窗口96小时。不会延长原JPEG/r7的预算。暂时观察读取失败只记录后继续观察同一进程，不把一次读超时判作实验终止。

当前状态是waiting_existing_delivery，尚未发起上述EDA。准备时先采用业务入口直接8线程重建的草案已归档，最终方案改用原native10线程构建，再交付预构建产物给业务replay，避免重复编译并贴合Student实际线程数。

## 后续决定

本候选不在先前已固定的自动启用清单内；原衔接程序仍只启用8940667，没有热改其方案。实际并发资格通过后，才将97466b0合入主DPL、更新根来源清单，并为未来实验选择和冻结资源策略。失败则基于原回执修正这一接点，不能用测试通过或理论并发数代替实测。

验收和续接：var/business/a25-dpl-operation-resources-20261018/acceptance.json、resource-calibration.json、request-preview-acceptance.json、qualification-specification.json、qualification-receipt.json。当前26份用户文件、r7的68份输入及前序衔接器输入全部保持。原DPL轮次继续：截至19:41，12项EF任务中11成功/1候选源码编译失败，第二次修正构建和两份后续布局评价已成功；Teacher计划完成，两个Student仍在原生收尾，第三Student/review和整轮交付未完成。

## 19:52：第一份稳定源码已实际核验

Student01已正常结束，Student03已启动。对Student01的实际Git候选ref bbc7f5c、已注册构建及评价逐项复核：84份源码哈希完全相同，评价使用的binary SHA与构建产物一致，注册原生指标HPWL为127898.1µm。它比框架127973.5µm少75.4µm（约0.0589%），是可交接的局部结果，尚无最终PPA/功能证明/采用结论。

另核查了“检查报告JSON缺失”：原检查器零失败时不创建DPL marker category，JSON仅在category存在时写出；注册的3_5_place_dp.json已经明确记录详细布局违例0，检查器源码与该Student源基线相同。因此无需制造一个空报告，也不将可选marker报告缺失误报为兼容性故障。最后的共同约束检查仍按原流程独立完成。

费用方面，当前完成的Teacher和Student01已记录至少31,113,396输入加输出token，cached input是其中的子集。Student01正常退出，但原生事件包含重连异常，按既有记录器规则用量完整性仍为未知；未结束Student的费用也保持未知，不能补零或直接做公平效率比。源代码/binary/指标身份及费用原件哈希分别记录在student01-source-binary-metric-acceptance.json和partial-native-model-costs.json。

## 20:34：第二份源码与实际交付入口核验

Student02已正常结束。独立读取其稳定ref 8eb7067和公开EF实际构建/评价：90份源码逐SHA相同，binary与评价实际输入一致，原生HPWL为127077.1µm，比框架低约0.70046%，注册详细布局违例0。它发现了强化版本的镜像朝向回滚问题，保留75d808d为拒绝版本，修正后的注册日志中两条通路的replay rejects、exact/reorder audit gap均为0。上述是原生方法和源码身份验收，尚无最终PPA、功能证明或采用结论。

实际调用既有Code候选导出入口，在本轮单独观察目录取得两份已完成候选；分别引用正确的bbc7f5c/8eb7067稳定版本，导出的两份ODB哈希与实际EF生产者注册产物完全相同。被拒绝的75d808d未进入输出。没有冻结正式交付清单、启动新EDA或写入DF，第三Student仍按原流程执行。原生收尾后仍须走完整共同测量和数据交付。

前两个Student及Teacher的已知模型用量下界现为72,477,808输入加输出token，完整性与未知费用分列，原较早快照保留在原文件。另对Student01两次评价的实际提交/开始时间核查，提交至执行合计2436.96秒，包含接单/准备等待；同时的资源快照显示私有构建占用全部32GiB预约。它说明需要核验新的资源策略，不能直接写成理论提速或正式前后效率比。

新证据为student02-source-binary-metric-acceptance.json、partial-native-export-observation-r1/acceptance.json及producer-acceptance.json、注册日志registered-source02-exact-audit.log、partial-native-model-costs-r2.json和student01-evaluation-dispatch-delay.json。前序源码及资源资格仍在既定等待队列，当前没有热切换。

## 21:02：三份稳定源码均核验，原生评审进行中

Student03正常结束，稳定ref为230a8d97e5e53461d7fd4c8048535a509e168a19。89份Git源码与实际构建/评价请求逐SHA一致，二进制e6f78282…与评价实际输入及构建回执一致；公开EF注册的原生指标为127573.8µm，布局违例0。相对框架线长减少399.7µm（0.31233%），原生运行32.319秒；最大位移22.5729µm的回退也保留，不能只报道正面线长。构建和评价各一次attempt成功，构建峰值4,921,757,696 bytes、采样CPU1546.78秒。

| 稳定候选 | 源码简称 | 原生HPWLµm | 比同一框架降低 | 注册布局违例 |
|---|---|---:|---:|---:|
| Student01 | bbc7f5c | 127898.1 | 0.05892% | 0 |
| Student02 | 8eb7067 | 127077.1 | 0.70046% | 0 |
| Student03 | 230a8d9 | 127573.8 | 0.31233% | 0 |

三份Student均正常返回，原Teacher review已启动。再次调用既有只读候选导出入口，三份输出都指向对应稳定ref；第三份ODB哈希0d72d1e7…与公开EF原生产者run-dcad4de7995247bea209b652d49d587f的注册产物一致。没有冻结正式交付清单、改变原生筛选或发起额外EDA/DF写入。当前仍待原生评审结束及完整共同PPA交付，不能将表中线长当作最终PPA或采用依据。

Teacher计划和三份Student的已知输入加输出token下界为85,417,787；review与整个交付的费用尚未完整。缓存输入是输入子集，Student01原事件完整性未知的限制继续保留。原32GiB预约未现场修改，两个既定衔接器继续等待r7及原JPEG事实交付，不将准备或排队写成真实并发资格通过。

新增原件位于同一证据目录：student03-source-binary-metric-acceptance.json、partial-native-export-observation-r2/acceptance.json和partial-native-model-costs-r3.json。根文档检查点e68f6f4另记录JPEG全部100槽位/376份关键小产物核验，66份成功输出超共同面积上限及44种原生时钟的对照限制。原68份活动输入和26份用户文件已逐SHA复核保持，产品/研究源码和服务未改。
