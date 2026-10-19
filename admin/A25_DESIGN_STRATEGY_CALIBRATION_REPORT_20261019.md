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

## 2026-10-19 23:22本机：真实原生结果、路径崩溃与隔离候选

本轮继续A25，前轮取得的新证据改变了策略与诊断行动，属于实际进展；正式A26/A27及A28尚未完成。主Flow、AES、原生完整参考和真实接力主管均以当前PID实际存在核查，未将旧回执或超时观察当成存活证明，未重开旧任务。

### 校准的资源替代及真实结果

原两个16GiB原生校准任务run-f370b6967824436894073d68f2f12a29、run-20557361627d4356896a653df5af52d5均在started_at为空、attempts=[]时经公开EF取消；旧主管自然退出，原目录保存替代说明。唯一替代主管1459962负责五份固定原策略，复用已完成首TNS结果与准备父ODB。原生任务根据约1.37GB实测峰值预约8GiB，CPU/命令线程、算法、原参数保持；共同最终物理仍24GiB、AES证明仍32GiB，没有扩服务池或修改活动Flow。

首次零派发预检发现缺少GOALEVOLVE_PLATFORM_PROFILE，生成器会输出新版默认negotiation；失败稿保留，新生成使用原冻结平台profile并恢复canonical Goal Diamond。原三配方与既有正确Tcl除输出目录相同；旧Query配对两个未执行脚本同时纠正此标记，新配对互相仍只差原生early power块。不据此全局切换Flow算法。

completed-native-independent-audit-r2.json已独立通过五组公共EF状态、四组注册zip全部捕获及当前文件SHA、失败原日志SHA和26用户文件。五组当前为：wns_path_deep、reroute_mid_power、measured_critical_path_deep和同低功耗父项timing_only原生成功；同父项power_then_timing失败。四个最终完整DRT/RCX均queued，公开说明为预约24GiB而池内只有8GiB空闲；无最终新PPA或采用结论。前两配方的原生绝对TNS约6.116/6.188ns，比匹配last_gasp控制5.329ns更差，不能与更早power_only父项比较后宣称新收益。

同次观察的主Flow首轮150阶段任务为101成功、13失败、2运行、34排队；这是布局/CTS/布线任务计数，不是150个最终设计或完整2轮已结束。AES129输出PDR run-ef79b04a799d4f30896f502e72deba99仍queued。r52闭合21个新终态EF任务（18成功/1失败/2零attempt取消），新增采样CPU63830.71秒，未知attempt usage0；不重复旧ID、pending不计已闭合成本，未知服务/主推理费用不填零。

### GCD机制与策略选择的适用边界

GCD成功Student02的保护条件为early_forced_reclaim且baseline TNS=0、WNS>=0。原GCD该阶段入口WNS约+0.0108900ns，当前JPEG约−0.00197642ns，因此当前JPEG不满足此条件。证据为GCD_guard_applicability_to_JPEG.json，这是源码条件及实际入口日志核对，不是将GCD候选二进制在JPEG上的实测移植。不能把GCD一次薄余量成功当作稳定泛化。

native-strategy-knob-contract-audit.json核对实际Teacher及参数语义：当前接入版本有17种可选时序配方；max_moves=0使用原C++按规模确定的有界预算，不是关闭/无限；power_stage_tns_ceiling_ns=0会被原构造器拒绝；当前JPEG已进入timing_recovery，调功耗保护轮数不直接改变此阶段；仅一轮也不能验证跨轮学习。保留算法不意味着不调专业策略；但不盲目使用零值、改变原评分或将fork每项能力未经来源核查都称为上游功能。

### 原生崩溃与隔离兼容候选

故障run-1bcbb23cb3ab41baa54867449c2f309f的注册extractor.log SHA为3f202d5a836f49685ba8be01eaa4e0302c835fa59123681d674e489fc4b70b4c，已实际核对。日志Signal11发生于sta::PathExpanded→SetupLegacyBase::makePinTargetOnPath→repairPins→SetupWnsPolicy。CPU495.86秒、峰值921567232字节，不能当成8GiB超限。当前证据定位原生崩溃，不足以最终证明具体内存错误根因。

源码发现repairPins在多个修复动作间重复使用同一个Path*；同版本Target注释已明确动作可使Path失效。隔离候选仅改SetupLegacyBase.cc：保留同一端点、在尝试动作后刷新其当前路径再展开下一个目标。原引脚顺序、预热、journal、动作序列、评分、预算和目标保持；刷新后的当前路径可能改变批次内目标成员，不能宣称物理行为逐字节不变。此为待真实验证的最小兼容假设，不降低修复动作预算，不改公共契约或任何活动源。

私有目录var/business/a25-goal-path-lifetime-diagnosis-20261019/中，candidate-preparation.json核对701份声明源码仅上述一文件不同、原父项及编译donor一致；原Goal COW构建器已成功创建私有构建图。主管2221907/start_ticks859268729经原EF委派提交run-0b5b5d32c5784ecd826aa40e37fb881e，当前queued16GiB，未开始attempt。回放主管2246640/start_ticks859279784实际存活，核对同一构建进程及成功回执后，才用同一新二进制执行原故障和原正常配对脚本；Tcl只重定位输出目录，原上下文/输入/目标和原8线程/动作预算保持，随后仍完整24GiB DRT/RCX。两份实际回归尚未派发，不记崩溃已修复或PPA改善。

镜像内无gdb，经单独公开EF小探针确认，未sudo/安装系统软件或因此反复重跑失败EDA。私有生成、构建、回放和审计脚本最终Ruff/格式及各自实际模块/SDK解释器Pyright零错警告；准备脚本初始lint失败后已修正，不当成全部工程门禁通过。C++构建、真实回归、独立最终物理及未来精确环境/AST重建仍待完成，因此候选未发布或启用。

### Query候选与剩余顺序

隔离Query4ee0af0仅修正跨run/revision指标比较的使用指导：使用已有mode=experiment和raw_key，不改DF/DI或数据语义。40针对、164全回归、3项依赖约束、静态/类型和真实原生Codex查询均通过；实际12次操作、111059字节，正确读取TNS及原单位功耗变化。wheel SHA138048010d11544f37a3fc4e827ab229753596c7aa6c5fe4968ca94e6e264fe6仅装隔离env，主Query48b105b和活动wheel未切换。这个小查询与此前完整诊断工作量不同，不能计算正式token/时间节省率；unit=null及派生/实际加载SDC差异仍保留限制。

下一步为原五组最终结果→真实路径故障回归及必要最小修复→将最终Query证据交专业策略决策→健康完整Flow/真实接力与AES资格→安全模块收口、精确环境及正式入口审计→A25冻结→A26/A27正式双核心实验→A28。当前主要等待是真实资源排队，同时可推进源码诊断；不因等待伪造完成，也不另造通用harness或评测底座。

本轮根文件仅PROJECT.md、TASKS.md及本报告；所有诊断/候选源码/配置/运行证据在忽略的var目录。用户评测脚本、DF/DI工作树及全部26受保护文件保留；没有stage、执行或部署其未提交修改。

## 2026-10-20：有效策略消费核验与老板问题答复依据

GCD已有真实Flow→Query→Goal闭环和合法候选；JPEG完整新Flow接力仍待完成，不能把两者描述成同一完成程度的团队比较。当前JPEG负结果支持专业策略覆盖、局部至最终物理反馈、默认算法兼容三方面需要改进，尚不足以认定某个Agent或底座是唯一原因。此前对接通和运行的验证多于专业策略实际消费与适配性的验证，这是工程推进需要纠正的缺口。

`var/business/a25-jpeg-reclaim-proportion-20261020/native-stage-and-recipe-provenance.json`核对上游1cc20aa及当前timing_recovery.py同blob，配方两轮界限来自原项目；原/新C++默认阶段均为LEGACY LAST_GASP，不能从配方名字推断实际POWER_RECOVERY_PLUS调度。四种已完成原生策略中，部分修复后TNS为零、重新布局和全局布线后转负；这些阶段数值不是共同最终DRT/RCX，不能混算改善率或认定线延迟是唯一原因。

原80%和新增40%功耗回收对照实际日志均为max_moves12500、max_targets14000、trial_limit36000，参数变化被原上限截住。原源码中proportion只用于阶段预算计算，因此这次40没有形成有效的早期动作预算对照，已显式停止唯一新增诊断run-9eeec2ad94f744dbb4a4aa6d4f8e97c1；公开终态cancelled，采样CPU966.31秒仍计成本，不记PPA失败或卡死。未停止原完整搜索、其他专业或构建。

替代的20%既有参数实验位于`var/business/a25-jpeg-effective-reclaim20-20261020/`。生成器证明控制与原80脚本除输出目录相同，候选仅80→20；源码/二进制、输入、原目标、配方和最终验收条件均保持。两个脚本分别通过实际原生Goal/客户端环境Pyright零错误警告，219固定输入及26用户文件逐SHA通过。主管3133532/start_ticks859661306已提交公开EF run-ee17837aad8545cebbbc57379abdfb0d，实际running；首份公开日志已确认max_moves10655、max_targets11216、trial_limit31965。由此只能证明策略力度实际改变，最终PPA、功能证明和独立重放未完成，不采用。

本次公开观察同时确认四组24GiB最终物理、16GiB隔离路径修复构建及32GiB AES证明仍在等待资源，不能把排队写成任务丢失或专业负结果；原监督PID仍存在，未重启。完整接力、原生专业参考、源码故障回归和A25冻结继续待完成。20%实验尚未闭合费用；40%取消费用需在下一去重台账中追加，未宣称旧r54已包含它。

本次仅补充本报告，产品源码、公共接口、原算法与晋升规则不改；未运行用户评测代码或部署DF/DI工作修改。不为纯文档重复全平台测试，也不把已启动的对照记为整个A25完成。
