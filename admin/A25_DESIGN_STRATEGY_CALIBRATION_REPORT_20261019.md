# A25：按设计校准专业策略及合法化默认行为核查

本轮响应老板关于“GCD有效、JPEG效果差、专业策略能否调整”的质疑，继续已批准的正式实验前资格。工程接通和业务采用门禁已经存在，但策略覆盖与最终物理反馈尚不充分；本报告不把新配置、排队或接口检查记作PPA改善。A25未冻结，A26–A28未完成。

## 实际策略差异

只读核对两场原始Teacher计划、解析后的分配、验证后的hypotheses、阶段诊断和实际配置，保存路径与SHA于`var/business/a25-jpeg-strategy-calibration-20261019/actual_GCD_JPEG_strategy_comparison.json`。

- GCD四个Student分别使用legacy_deep、wns_path_deep、measured_vt_deep及last_gasp_deep。最终平台保留的是Student02，其配方为wns_path_deep，不能将Student01的legacy_deep误写成该候选配方。主要源码机制保护repair_power阶段的时序前沿。
- JPEG原Teacher原文已经把四个slot分配给SetupLastGaspPolicy.cc，验证后的四份假设均采用last_gasp_deep。不是本轮导出器将四个不同配方压成一个；这项核对不证明所有上游提示/调度限制都已排除。
- 两场均只有一轮四Student，功耗回收比例80%、阶段TNS上限60ns、三项权重1.0等配置相同。保留原生算法不意味着这些策略参数永远不可调整；现有接入版本提供多种模式/配方，但不能把fork中的每项能力未经来源核查都归为官方上游功能。
- 原诊断：GCD的repair_power增加绝对TNS约2.269794ns，布线再增0.478183ns；JPEG功耗阶段仅增0.0117245ns，布局增0.417766ns，全局布线增6.186492ns。这是各场内部阶段变化，不是跨设计规模归一化比较，也不证明唯一因果。

此前JPEG全候选审计证明四个源码候选只有两个最终native物理状态：01/02/04与无源码增量的配方父项ODB同字节；03局部TNS改善，却在完整DRT/RCX后使最终TNS、WNS和功耗较匹配物理父状态变差，四个候选均不满足原setup约束。详细证据见原生机制审计及完整候选报告。不能据此宣称所有专业Agent不行，也不能由GCD一次成功推出跨设计稳定收益。

## 已派发的原生配方对照

独立目录`var/business/a25-jpeg-strategy-calibration-20261019/`，主管PID2829023。四种既有配方为tns_global、wns_path_deep、reroute_mid_power和measured_critical_path_deep。它们不是只改变一个参数的四组单变量实验；每个完整配方及其内置动作都在native-generation.json中记录，特别是reroute_mid_power还包含中途功耗回收。该校准用于筛查策略适用性，不将配方差异算成新C++贡献。

所有组复用同一注册无源码增量父项二进制c2ff1adc…，核对原producer run-035a965018534c439053aebc8e56d90e、构建收据和701份声明源码一致；沿相同原输入/功耗配置、共同FF545ps、原目标执行。生成器调用原冻结Goal Controller自身的Tcl构造器，重建last_gasp_deep控制后除输出目录逐字相同。没有修改Controller、OpenROAD源码或现有搜索。

- generate_native_controls.py：在原Goal自身工作目录和解释器中生成现有策略Tcl，不执行EDA。
- run_controls.py：通过现有Jobs/公开EF执行native→共同完整DRT/RCX→ORFS/OpenSTA事实→SDK与原约束比较；对象索引显式按需，不伪称已建齐。原生模型调用0，构建/搜索旧成本不重复累计。
- local.json/specification.json：独立状态根、180份固定文件及26份受保护用户文件的身份；没有新增后台或公共契约。

第一组已实际交EF，run-cd7d070387024d81918c00ba3454d6bf；最新公开状态queued，等待同一32核/32GiB池资源。其余三组由同一主管顺序执行，尚未派发；不能说四组已运行完成。即便某组最终可行，也须再完成全27输出PDR、独立物理重放和SDK核验后才能考虑采用；本轮主管不会自动采用。

原生脚本首次直接按文件启动解析到了环境安装的Goal包，导致official utils路径与原冻结控制不同；零EDA预检即拒绝，五份生成稿和错误保留。改为在原项目工作目录用普通python -c/runpy启动，未改sys.path/PYTHONPATH，新生成控制逐字相同。Native类型检查也按该原项目自身模块根解析，根客户端脚本按实际client wheel环境检查，均零错误/警告；初始错误上下文不当作源码通过。

## 新发现：Flow新版默认合法化未收敛

本轮公开读取完整Flow首轮50个唯一place run，观察快照为14成功、6失败、4运行、26排队。六份失败中四份注册日志明确FLW-0024密度超过1.0；另两份为DPL-0033。具体run、日志原件和时间见flow-observation-r1/r2及newly_failed_place_classification-r2.json，计数仅代表该观察时刻，非整轮结束。

run-aeadbc746ab048fe9d3f277361be19ae来自首轮slot46。注册日志明确新版默认NegotiationLegalizer未收敛，之后发现3项重叠及345项padding检查失败；峰值约498MB，不能解释成8GiB预约不足。后续另一份DPL-0033也已经取回注册日志。原Flow脚本调用裸detailed_placement，而已迁移Goal脚本显式使用Diamond，因此“二进制版本相同”仍不足以保证算法默认行为一致。

独立目录`var/business/a25-jpeg-legalizer-compatibility-20261019/`，主管PID2907010，已通过原EF注册归档取回该候选pre-DPL ODB及floorplan SDC；候选mk/SDC/profile与原slot输入SHA逐项一致。两个隔离探针共享该ODB/SDC、15份实际库及RC、padding=1、DPO关闭和8线程，仅Diamond标志不同。第一项Diamond已交EF run-b1ab332004364c9caf913d725885c909，最新queued；默认negotiation对照由同一主管随后执行。

探针采用明确加载的DPL阶段，省略原ORFS指标包装，**不是完整原ORFS重放**。必须先确认paired negotiation复现非法布局，且Diamond合法，再判断默认合法化选择是否解释这一失败。即使成立，也只证明该候选阶段的兼容问题，不能单独解释全部JPEG PPA差异或直接证明整场收益。没有给正在运行的搜索换脚本、重试失败候选或删失败成本。

## 验证、边界和下一步

三个私有驱动/生成脚本通过Ruff F/I、格式及各自正确模块环境的Pyright；原控制重建相同、成对探针仅一个合法化flag差异、二进制/源码/输入SHA和零派发预检通过。它们的真实业务验收仍在等待计算；未声称完成一个产品代码切片的全部门禁。本轮没有产品源码或公共签名改动，不因文档/实验准备重复全平台回归。

原主Flow主管1557962/2256439、AES来源主管2282819、原生完整专业参考等待者1705515及真正Flow→Query→Goal等待者1479386仍存活。最长原place任务run-dc8c0d39fa5b46cdaceebe670b02f40b公开状态running，日志已推进至合法化迭代1220，仍有真实进展，未因慢而取消。AES run-35011a297b2847e0a3537d6f91eecddd仍queued；排队不是失败，也没有重开来源key。现有活动输入和26份用户文件保持。

后续实际顺序：取得策略/合法化对照并独立核验→将最终阶段证据沿现有Query上下文反馈给后续专业决策→继续完整健康Flow与真实接力/AES资格→空闲窗口收口DPL/ECO主版本→冻结来源、各方法充分投入与停止规则→执行正式PPA和同Codex同业务平台效率对照→最终审计。任何负结果继续保留，校准样本不改称未见设计，团队不要求与单项同总预算。

本轮根提交仅包括本报告、TASKS.md和ARCHITECTURE.md；所有实验脚本/配置/运行数据留在忽略的var目录。没有stage或运行受保护的用户评测代码，也没有部署用户DF/DI修改。
