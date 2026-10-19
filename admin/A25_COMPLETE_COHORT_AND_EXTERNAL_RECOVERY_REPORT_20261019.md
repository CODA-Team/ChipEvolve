# A25：JPEG全候选收尾、完整Flow启动和外部中断恢复

本轮JPEG原Goal全部四候选已完成共同交付和独立SDK审计，均违反原setup约束，不采用。后继健康完整Flow2×50已实际启动。直接侧新增完整业务恢复资格已通过独立取证；AES完整参数来源已通过统一EF提交，仍在排队/运行资格阶段。A25未冻结，A26–A28未完成。

## JPEG：完整原生运行不等于PPA成功

| 候选 | 共同功耗mW | 单元面积µm² | setup最差slack ps | 原约束 |
|---|---:|---:|---:|---|
| Student01 | 155.25515378 | 6378.88 | −30.8414 | setup失败 |
| Student02 | 155.25515378 | 6378.88 | −30.8414 | setup失败 |
| 原Teacher选择Student03 | 155.27968109 | 6378.88 | −33.0878 | setup失败 |
| Student04 | 155.25515378 | 6378.88 | −30.8414 | setup失败 |

原生完整四Student、原判定、注册producer/ODB哈希、共同DRT/RCX和所有七PPA、SDK范围/数值均已核对。最终inventory为3份completed、1份already_delivered，父业务状态succeeded表示运行和数据交付结束；没有可行候选，没有新增采用或强行给失败候选签发功能/物理通过回执。

来源归因已进一步明确：原Goal命名为post_route.odb的检查点实际是global_route及estimate_parasitics -global_routing，没有detailed_route或RCX。平台随后完成真正DRT和寄生提取。01/02/04与原匹配无源码父项的注册ODB同字节；03的局部估算TNS改善，经共同最终流程后相对该父项物理状态，功耗增加0.02452731mW、TNS恶化0.192613ns、最差slack恶化2.2464ps。两者仍不满足setup。这个排名反转不能推断为版本错误或源码被忽略；原本就是不同物理阶段的指标，最终业务必须依据共同事实判定。

证据：`var/business/a25-complete-cohort-audit-20261019/jpeg-readonly-r1.json`、`var/business/a25-jpeg-native-mechanism-audit-20261019/actual-native-versus-common-physical-stages.json`及`actual-common-ranking-reversal.json`。原算法、源码范围、原生评分和目标没有改写。

## 健康完整Flow已开始

真实业务为`a25-jpeg-full-native-stage-resources-r1`，原2轮、每轮50候选、72000秒，source模式；起点是注册完整旋钮来源`run-e1851061d4094a9189502aa21c245818`，不是把不具备RTL来源的Goal结果伪装成Flow接力。

实际原生drp_config.json与正式Flow模块逐字节一致，SHA443542fd51785b7187a42b7473413b11a6cb4b2a3e8bca392ffd34f2401a1282。线程8，place/CTS各8GiB、route_finish12GiB，与原批准资源资格一致。首轮50槽位均取得唯一公开EF run，归属和资源逐项核对；第一次采样为1成功、4运行、45排队，没有提交前缺回执。未把初次提交成功当作两轮健康搜索完成。

原调参器仍可探索自身时钟参数；实际首批SDC哈希不同，已读取的真实staged候选为514.78ps。原始来源545ps、原生探索时钟和最终共同545ps业务判定要分开记录，不能把原生内部分数当成不同频率下的公平最终比较，也不通过固定原参数来缩减专业能力。

启动及初50回执证据位于`var/business/a25-post-export-continuation-r2-20261019/04-healthy-full-flow/`。完整阶段继承、原轮次、所有失败/候选及最终数据仍由该原主管和后续独立审计完成。

后续采样已见7个布局成功、3个原生FLW-0024密度超限。三个注册日志及最高约1.02GiB的实测峰值已核对，属于原参数组合的物理不可行，不是8GiB资源终止或提交丢失；保留失败与原域，不另行重试。最早长任务仍在详细布局迭代，当前没有将安静/较慢输出当作失联。实际回执为`actual-initial-density-failures-and-progress.json`。

## 直接侧：真实命令收尾和完整观察中断恢复

实际原生Codex CLI0.159.3、gpt-6.1-sol/medium执行；直接侧保留原源码/工具/普通脚本能力，不调用EF/DF/DI/Query。它是授权的无平台控制路径，产品实验仍由统一EF负责。

1. 真实90秒deadline停止原生Codex及其附着长命令，工作进程PID/start ticks在实际收尾名单，独立哨兵保持存活。未完成usage footer的模型成本保留未知，不填零。
2. 首次完整直接业务完成两次真实RTL ORFS、全部18输出ABC-PDR和七PPA同值；但Agent自选故障时记录了run_command.py包装器，未证明实际OpenROAD身份，保留completed=false。647份原产物哈希已独立检查；不删除失败或冒称恢复通过。
3. 第二次由独立外部fixture在真正OpenROAD执行时只对已登记观察端SIGTERM，实际不可用10.010144秒。注入前的完整父链与恢复后的原始顶层Make PID/start ticks一致；递归综合Make正常结束不等于整场EDA重启。随后两次完整ORFS、全部18输出PDR、七PPA精确同值和所有自有进程收尾经独立核验通过，检查341份原产物哈希。

两个业务的最终功耗均1.373553765mW、面积42.6757µm²、原约束全部通过，未进行新优化。源与独立重放均从新RTL工作目录开始，没有复用第一次旧实验的物理产物。恢复试验针对观察端不可用，Codex普通工具仍可使用；不把整个Agent必须失明作为额外限制。原生宿主、外部故障程序和独立判定各有边界，没有新增模型API循环或通用harness。

证据在`var/business/a25-direct-retained-session-recovery-20261019/`与`var/business/a25-external-observer-recovery-r2-20261019/`，分别有原事件、收据、超时/失败和独立审计。这些是共享开发主机上的资格案例，与旧平台恢复案例工作量不同，不能直接计算正式效率比。

## AES共享完整来源

源码/登记核查确认AES旧a9-reference只有VT兼容配置，没有像GCD/JPEG一样显式设置完整原生旋钮来源。本轮新建独立配置，复用已验证的通用ASAP7参数和两个原hook脚本，保留AES自己的RTL、FF/810ps及全部129输出、旧原约束；对所有专业方法共同开放，来源差异单列，不能计作Agent/协同增益。

实际EF源任务为`run-35011a297b2847e0a3537d6f91eecddd`，配置8线程/8GiB；已有同设计完整ORFS峰值2,631,053,312字节作为资源依据，EF池仍32CPU/32GiB。它会在现有原生Flow负载下排队，后续依次验证不变配方复制七PPA、SDK、全部129输出PDR及精确环境。尚未获得这些实际结果，不能提前写成AES完整来源通过。

初次新准备驱动在派发前因Deployment.experiment创建了空目录，后续“不存在”断言误判而退出；提交EDA为0。原脚本/日志保留，仅删除该已确认的自有空目录，r2使用纯路径预检后提交同一未派发key，没有重复EDA、没有产品代码改动。实际资格与该修正均在`var/business/a25-aes-native-domain-source-20261019/`。

## 成本与剩余验收

费用r48核对前47份费用快照及其哈希：闭合JPEG原生之外的18个共同交付EF任务，新增采样CPU14746秒，未重复r47的48个原生任务/13专业调用。本轮3份新原生episode中，两份完整业务已知输入+输出3890900token；超时探针实际用量缺失，保留未知。直接命令CPU与原生记录器CPU有重叠，不与EF采样CPU盲加；活跃Flow、AES来源、服务和主Codex费用继续单列。

本轮新增私有准备、取证和有限故障脚本通过静态/类型检查，实际资格和产物核对如上；没有修改公共API、生产服务或专业算法。26份受保护用户文件保持，原冻结副本不热切。剩余核心仍是健康完整Flow及真实Flow→Query→Goal接力、AES来源资格、原生完整专业参考/冷准备边界、可执行且匹配的正式各侧清单和独立验收、A25冻结，随后才执行A26/A27并收口A28。
