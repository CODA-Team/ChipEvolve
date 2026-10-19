2026-10-19实际收尾补核：JPEG首轮50place全部终态，38成功/12失败，六份密度超1、六份negotiation未收敛/DPL-0033，全部注册日志已逐SHA核对；完整2×50仍运行，已有50份CTS交接。配对同输入默认negotiation失败、显式Diamond合法，成功归档五份捕获与失败单独原件均已核对，单一flag差异成立；Diamond日志HPWL却增加约205%，不能据此全局切换或宣称最终PPA改善。第一组TNS配方native已成功，正在共同DRT/RCX和数据交付；AES原ORFS及测量完成，原重复mkdir错误后3434644已沿同来源/同控制键实际进入复制验证。r49独立闭合51个新终态EF任务、采样CPU31549.38秒，无旧ID重复，不是完整搜索费用；详见文末补核。A25未冻结/A26–A28未完成。

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

## 两种合法化算法的实际配对结果

paired-independent-acceptance.json核查了同一个注册pre-DPL ODB/SDC/candidate.mk、同一二进制/镜像/线程/15份库/RC和padding。Diamond成功归档中的五份捕获逐SHA对应；默认negotiation失败时保存的是独立query-data原件，manifest、输入、失败ODB及stdout也逐项对应，未用失败归档布局假设替代取证。归一化输出目录后，两份Tcl只差-use_diamond_legalizer。默认分支复现未收敛及DPL-0033，Diamond通过placement检查。

这支持该预先选定JPEG配置的默认算法差异解释，不推断其他五个DPL失败全部可被同样修复。Diamond在镜像优化前的日志HPWL由127999.3升至390028.0（原日志尺度，约+205%），之后镜像为385866.4；合法布局并不保证最终线长、功耗或时序更好。两份probe的EF采样CPU分别72.39/692.69秒，不作正式运行时间优势，也不重复归入原失败任务。没有变更活动搜索、扩大资源池或放宽原约束。

完整首轮布局12份失败已在initial50-final-failure-audit.json中核对：6份FLW-0024密度超1、6份negotiation未收敛后DPL-0033，其余38份成功；没有把明确算法/配置失败写成资源不足或失联。后续CTS/布线、第二轮及最终共同PPA仍需真实完成，不能由首阶段结束推定全搜索健康通过。

## 费用闭合与交接边界复核

preparation-costs-r49.json扫描47份既有快照的全部run引用后，独立新增这50个place和AES原ORFS共51个唯一终态任务，39成功/12失败，采样CPU31549.38秒、未知attempt usage0、最大已完成任务峰值约2.694GiB。其余CTS/布线/模型、AES复制/PDR、四策略与其他后继没有冒充已完整入账；host Query、服务及主Codex未知费用不填零，且不与重叠的原生命令CPU相加。

源码复查同时确认DPL入口原生默认和平台实际传参都为3_4_place_resized，平台从真实源archive提取前置状态，再承接CTS/路由；没有发现把Goal的post_route命名输出直接当作DPL pre-DP输入的情况。Goal结果目前没有DPL所需的原ORFS archive，不能把当前已验证的Flow→DPL→Goal→ECO及Flow→Goal路径扩写成任意反向边都支持；本轮没有为未验证路径增加变通。

后续冻结应明确每种专业策略实际选择的合法化器/修复recipe及其来源，而不是只写“最新版OpenROAD”。原生专业算法可以选择不同策略，统一的是工具身份、物理输入与最终验收条件。改变策略使用新实验及对应控制，不能热改旧结果或用一个阶段的成功承诺最终PPA。

## 当前CTS真实消费与跨阶段合法化核查（2026-10-19 21:28本机）

新搜索首轮50份CTS均已启动过真实EF attempt；公开运行与实际输入核查为49成功、1运行，0项检查失败。50个槽位来自35个成功布局父项，15个槽位使用原生选择的非自身donor；每份checkpoint的注册artifact_id/SHA、实际消费字节、配置/SDC/profile/业务目标/Query上下文字节，以及候选和最终条件身份均匹配。该核查只覆盖CTS输入交接，不代表全2轮或最终PPA通过，也不将50槽位解释成50份不同物理父状态。证据为`var/business/a25-jpeg-stage-consumption-20261019/cts-consumption-132834.json`；只读脚本经Ruff F/I、格式及实际client解释器Pyright零错警告，26份用户文件SHA保持。

最后一个CTS为slot28/run-deffacf9daf9495ca1f1377e2151d80c。公开实时日志已观察到第一次negotiation在1399迭代后仍有231项内部违例，随后原脚本继续repair_timing、第二次detailed_placement；后者仍有迭代进展。该内部计数不等于最终check_placement判定，不能预先将活动任务写成失败或卡死。原件观察及SHA保存在`var/business/a25-jpeg-legalizer-compatibility-20261019/active-cts-slot28-log-observation-r1.*`。

源脚本核查发现兼容选择已存在统一配置入口：cts.tcl两次调用detailed_placement_helper，util.tcl的该helper读取DETAIL_PLACEMENT_ARGS再调用detailed_placement。后续匹配完整物理对照可在独立配置中显式声明算法，而无需修改活动OpenROAD源码或逐阶段插入特殊补丁；本轮未改变此变量、活动配置或搜索预算。既有slot46探针的Diamond线长代价仍需完整验证，不能由这项配置入口检查直接决定全局切换。

同时公开确认AES原同键复制place/CTS已成功，route_finish运行且详细布线持续推进。第一组TNS配方的native已成功，但共同完整物理任务run-7246e783917d4794bdee12832fc05dba等待24GiB预约；观察时只有16GiB池内可用，属于明确资源等待，非丢任务或缺回执。本轮未增资源池、改调度顺序或重开实验。A25未冻结，A26–A28仍未完成。

本次续查检查点只提交PROJECT.md（当前业务状态）、TASKS.md（未完成项及真实进度）和本报告（配对、费用与消费证据）；没有产品源码或公共接口改动。私有只读核查脚本与运行回执留在var，初始格式检查未通过后已保留原脚本、修正格式并重新执行，最终静态及真实核查通过。


## 首个完整策略结果、AES复制验收与Teacher决策补核（2026-10-19 21:40本机）

首个tns_global对照完成原生→完整DRT/RCX→ORFS/OpenSTA两类事实交付及原约束判断，测量run-df048fa6b0764c079d5f210f0b351ca5。最终功耗155.20265698mW、单元面积6378.88µm²、setup TNS−0.57416ns、WS−30.8414ps。相对原来源功耗−12.972382%、单元面积−5.276069%，轮廓不变；但setup失败，不采用。相同来源last_gasp无CPP控制为155.25515378mW，TNS−0.573876ns、相同WS/面积；新配方功耗仅再低0.033813%，TNS略差，尚不能证明解决了JPEG的最终时序问题。

独立核查已通过公开EF locator读取注册测量归档、验证其SHA，由原native-metrics和stdout功耗总值恢复七PPA，再核对结果及当前DF/SDK；当时ORFS/OpenSTA两个snapshot主体身份一致，OpenDB对象索引显式延后。证据`var/business/a25-jpeg-strategy-calibration-20261019/tns-global-independent-delivery-audit.json`。对该不可行控制不宣称已完成全输出PDR或独立重放。原主管已自动进入第二组wns_path_deep，不因首组负结果重开旧搜索或修改原约束。

AES同一来源的复制place、CTS、route_finish均成功；原注册归档全部九个capture字节、七native值、当前DF/SDK和三scope、source/copy条件及目标均独立匹配，七PPA精确相等。证据`var/business/a25-aes-native-domain-source-20261019/copy-delivery-independent-audit.json`。功耗71.545690298mW、单元面积1498.78µm²，原功耗/单元面积/core/die四项上限失败；复制可复现不等于来源可采用。129输出ABC-PDR及环境freeze仍由原3434644继续，未冒充已通过。

JPEG首轮CTS现全部终态49成功/1失败，50份真实消费核查仍零差异，终态快照`cts-consumption-133115.json`。slot28注册extractor.log逐SHA核验，第一次negotiation剩231内部违例、第二次剩665，最终DPL-0033；没有OOM或未消费证据。首轮50个route_finish槽位已入队，完整2×50及最终交付仍待完成。

实际Teacher可见18项配方目录，冻结Controller的power_then_timing模式允许17项（排除area-only配方），并非只允许last_gasp；原Teacher仍将四候选集中在last_gasp。原一轮确已结束，原生评审依据GRT局部结果晋升Student03，而完整DRT/RCX后平台拒绝采用。原生search_policy在连续两轮未晋升后才提示多样化，本场只有一轮且发生原生晋升，该自适应条件没有触发。不能把延长到三轮等同于保证触发多样化，也不能声称最终负反馈已进入下一轮。证据`actual-teacher-menu-and-native-feedback-audit.json`；后续需将最终物理负结果实际交付决策，依据四配方结果选择新的专业轮次和参数。

费用r50新闭合66个唯一终态EF任务（64成功/2失败）、采样CPU12720.14秒，未知attempt用量0；包含本轮CTS、配对探针、AES复制/交付及首策略原生等明确子集，不包含尚未结束的完整搜索或全部策略。r50记录的当时pending任务run-7246e783917d4794bdee12832fc05dba现已完成但尚未在r50计费：后续必须按已计费终态行去重，不能把pending引用误当已计费而漏掉。模型费用仍只继承已闭合收据，活动Flow等未知范围不填零。A25未冻结、A26–A28未完成。


## 实际专业Prompt交接与新最终反馈诊断（2026-10-19续查）

沿原运行的六个明确模型产物路径，核对Teacher plan/review和四个主Student编辑调用的invocation及最终生效prompt（非追加平台上下文前的teacher.md草稿）。六份均包含原context_id和setup_tns_ns_min=0约束，逐文件SHA已记录于`var/business/a25-jpeg-strategy-calibration-20261019/effective-professional-context-delivery-audit.json`。这证明六个主调用收到原目标/原Query上下文，不证明模型正确使用，也不覆盖全部修复/草稿调用。原上下文属于原来源，不能冒充当前最终负反馈。最初只读递归查找会遍历Student源码/构建目录，已核实后仅终止该自有扫描进程，改为六条明确路径完成核查，没有中断EDA或专业Agent。

已通过现有业务CLI启动当前tns_global最终结果的真实diagnose，PID882097/start_ticks858702436，规格/问题/启动记录在`var/business/a25-tns-final-query-feedback-20261019/`。比较原FF545ps来源，要求查明实际违例组/分布、单元与线延迟证据、可用策略及进一步降功耗是否合适，区分事实/假设/对照建议，不允许优化动作或凭空因果结论。调查允许读取已有事实，max-analyses=0；现有业务入口先通过EF导出此前延后的OpenDB对象，再由DF导入。当前数据准备/诊断未完成，不宣称已生成上下文或被专业Agent消费；原两快照结果文件保持不变，补充发布使用独立materialized-result.json。

AES原129输出证明的前置步骤已成功，正式ABC-PDR任务run-ef79b04a799d4f30896f502e72deba99仍因32GiB预约等待池内资源，不将Supervisor的proving状态当作证明已运行或通过。四配方第二组/完整Flow和既有后继继续，A25未冻结、A26–A28未完成。本次只更新本报告，用户评测代码与DF/DI修改不动。

## 新最终诊断完成、已驱动原生模式配对（2026-10-19）

本轮真实Query inv-3f974849a7454426805279a155537d56已形成有引用的回答并导出绑定当前tns_global源的上下文2e0c76bd…。公共load_context、source/reference身份及固定输入SHA核查通过：4事实、4假设、48证据、5限制。原问题/调用/身份验收位于`var/business/a25-tns-final-query-feedback-20261019/`，完整包在原TNS实验query/professional-context.json。Query的paused是“包已准备、等待消费者”的领域状态，不表示长期线程目标暂停。

观测到的五条负setup样本都从sample_cnt[0]控制信号进入不同DCT系数寄存器；其数据段单元增量约0.499–0.504ns，线增量约0.009–0.012ns。对应最差样本中一个NAND的原/当前master由NAND2x2…SL变为NAND2xp33…R，支持检验驱动/Vt/负载交互。样本不是完整失败端点统计，没有匹配端点前后时序和完整拥塞证据；“恶化在布线后显现”不能直接等同于“线延迟独占主因”，也不能据此认定某一个单元是唯一原因。

根Codex读取该诊断后已实际选择现有wns_path_deep，在相同已降功耗父状态上比较timing_only与power_then_timing。独立目录`var/business/a25-query-guided-reclaim-pair-20261019/`只含私有实验脚本、声明配置与运行数据：generate_pair.py调用原冻结Goal构造器；run_pair.py通过既有EF准备父状态、原生运行、共同DRT/RCX和DF/SDK交付；decision.json记录诊断到策略选择的依据。192固定文件/26用户文件保持，Ruff/格式与各自实际解释器Pyright零错警告。去掉构造器原有early power block后两份Tcl逐字相同，时序命令、父ODB、二进制、库/SDC/RC、原内部目标均一致；不改C++、原评分或晋升，不手工删Tcl指令。

主管PID1101590/start_ticks858800175已运行。共享父状态准备run-78c877c8fc294ab58b4a66a766a2d938成功；注册归档中的Query包、真实决策JSON和准备ODB均经公开locator逐SHA对应，见query-consumer-registered-evidence.json。第一项timing_only原生优化run-20557361627d4356896a653df5af52d5已被EF接受，仍等待16GiB资源；不能写成优化已完成或PPA改善。这证明根Codex已将最终诊断用于下一项实验选择，不宣称原Teacher/四Student已消费新反馈或一轮新源码演化已完成。即使最终可行，仍需全输出证明和独立重放后才能考虑采用。

Query首次只交付ORFS/OpenSTA两类事实，本轮业务diagnose按现有显式延后标记补齐OpenDB；源result.json保持SHA不变，新增materialized-result.json。当前调查60次工具操作/411571读取字节、0内部分析，原生host可见1071461输入token（含932736缓存子集）、9264输出token；这是一个已完成CLI turn的可见用量，不推断内部API请求数。CLI发起到输出回执约555.32秒，调查active_seconds约240.15秒，两者范围不同，不能只用后者充当完整延迟，也不形成正式效率优势。

Query使用默认stage比较模式时因revision不同拒绝；独立核实现有公开mode=experiment后，七个精确raw_key均返回可用COMPARABLE及正确原/当前值，没有更改DF/DI或构建新比较框架。记录explicit-experiment-comparison.json。原比较unit仍为null、输入库引用仍有unknown，必须结合原单位/冻结测量条件，不能把COMPARABLE当作物理等价或因果证明；后续使用指导应明确跨实验模式。最初私有检查器误把COMPARABLE当作HTTP外层状态，修正为读取data.status后通过，不是服务故障，旧Query回答不回写。

r51增加6个唯一成功EF任务/采样CPU3205.29秒、未知attempt用量0，并闭合上述一个实际Query host用量。r50中当时pending、实际未计费的qualification现已计入；后续用accounted_EF_run_ids去重，不把观察到pending引用视为已计费。费用仍非全场，服务/未知模型与重叠RUSAGE不填零或盲加。最新公开首轮route为4成功/2运行/44排队；AES129输出PDR、四配方剩余三组、配对优化、完整2×50及原生参考/实际接力均未完成，A25未冻结、A26–A28未完成。

本次检查点提交PROJECT.md（当前业务交付）、TASKS.md（剩余任务状态）和本报告（实际证据、费用及限制）；私有配对脚本/配置/运行产物留在var。没有修改产品源码或公共接口，没有把当前实验检查点写成整个A25切片完成。
