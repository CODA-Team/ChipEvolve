# A25：共同工具链归档器导致源码增量未可靠进入链接

本轮发现并复现了一项实质构建缺陷，改变了后续动作：必须先核验源码增量确实进入实际二进制，再做策略或源码贡献归因。A25未冻结，A26/A27正式试次及A28未完成。

## 已证实的问题

原隔离路径生命周期修复的最终链接run-6d4e57d0d0384c19bb0b2e0ec5d9450c成功，CPU1313.12秒、峰值4821544960字节；但实际可执行文件SHA仍为原父项c2ff1adc…，独立分块哈希相同，不能认为修复生效。

实际CMake静态库链接命令为`"/usr/bin/gcc-ar-11" qc librsz_lib.a …`。Goal的COW增量构建只在归档器basename等于ar时删除复制来的旧库；gcc-ar-11未被识别。qc随后追加对象，132成员中只有66个不同名称，SetupLegacyBase.cc.o同时保留旧、新两份。实际编译规则已指向新源，编译对象也改变，但最终链接仍得到原可执行文件。这是本次构建中已证实的源码/二进制交接缺陷，不能当成EDA运行失败或专业策略无效。

原回放run-b91f0f4d16884c169956b29c9880e9c9已经使用该旧二进制开始，发现后通过公开EF取消并确认cancelled；仅收尾匹配PID/start ticks的私有回放主管2691230，保存原回执及取消前后证据。原主Flow1557962、五策略、20%对照与AES证明保持。

## 最小修复与工程验证

独立Goal分支a25-gcc-ar-cow-archive-20261020，提交d5a3a9550d0bafe9371f9630e972c89c11706a1f，已发布到ChipEvolve的modules/goalevolve-a25-gcc-ar-cow。主模块仍为7b03c33，活动源码/配置和公共契约未切换。

仅两文件：

- goalevolve/evaluation/contest2026.py：原私有静态库清理函数识别ar、gcc-ar、llvm-ar及其数字版本后缀；原qc、相对本地静态库和目录约束保持。没有改变专业算法、Teacher/Student、AST/EPD、配方、评分或晋升。
- tests/unit/test_static_archive_toolchain.py：真实GNU ar先生成含旧对象的库，再以相同成员名添加新对象，验证成员唯一且读取到新内容。五种工具名覆盖；此单元检查不冒称实际执行了每种编译器归档器。

旧版四种名称失败，修复后五种全部通过。完整tests的XML共473条（含子检查），错误/失败均0，原跳过3。Ruff F、新测试F/I、改动区域格式、实际Goal解释器Pyright、逐文件差异与内部模块边界检查通过。源工作树只有这两份提交；没有使用受保护评测脚本或DF/DI工作修改。

## 实际重建与后继门禁

新主管188118/start_ticks860357065，仍用原单文件SetupLegacyBase.cc兼容候选和原701份声明源码；控制器只增加上述归档器修复。read/write挂载保持此前已通过的安排，输入/目标/8编译线程/单LTO worker保持。依据上一完整链接实测4.82GB峰值，本轮variant_build预约8GiB；不扩全局32GiB池。

公开r3写探针dc18ea…、对象编译2abd80…、静态库链接c43c0d…成功。独立读取新库为66成员/66个名称，SetupLegacyBase.cc.o唯一且与新编译对象SHA一致，证据corrected-static-component-acceptance-r3.json。最终OpenROAD链接run-ef488f773d074ce09137ee4ba6f7429a仍running，尚无新可执行文件或崩溃修复通过结论。

新回放主管213905/start_ticks860372578等待同一r3构建。它须先独立核对公开注册归档、源/实际编译与链接规则、新二进制SHA、唯一静态库对象及原固定输入，再执行原崩溃/原正常两个模式；新Tcl仅重定位输出路径、参数不变，之后仍共同完整DRT/RCX。门禁未过不得进入回放或宣称修复生效。

## 历史影响与继续路线

只读核查留存JPEG四个Student库，分别有198/198/132/132成员，均只有66个不同名称；其匹配无源码父项为66/66。GCD成功Student02也为132/66。当前库观察与既有注册二进制哈希可关联，但旧静态库不是当时已登记的历史产物；重复成员本身不足以单独证明每个旧二进制选择了哪一份实现。

因此保留已测得的实际PPA、功能证明和独立重放，重新核验源码收益归因。不能由此宣布所有专业改动失效，也不能继续仅凭“源SHA不同、链接成功、二进制SHA不同”认定某段新实现已执行。之前GCD的合法0.715648639mW产物仍是实际结果；其C++增量收益以及JPEG非激活/增量机制判断，需要纠正归档后的匹配重建与实际运行补证。

原1705515完整原生参考和1479386真实接力主管均在waiting状态、尚无模型/EDA派发时，经PID/start ticks核验后收尾，保存superseded-before-dispatch-archiver-fix.json。它们原固定来源仍含此缺陷，不能让其继续自动发起新的源码实验。实际Flow继续；修复完成二进制与故障资格后，须重新绑定合格控制器，恢复完整原生参考和真实Flow→Query→Goal后继，不能把已收尾守候者写成仍在线。

下一步：收取r3真实新二进制及原故障回归；重建并核验受影响源码候选的实际增量；收完已有五组最终物理及20%对照、完整Flow和AES证明；用合格来源恢复专业参考与真实接力，再冻结A25及正式实验配置。原策略覆盖不足、局部至最终物理退化、合法化默认改变仍是独立问题，本缺陷不替代其最终结果检查。

## 证据与费用

主要证据目录：var/business/a25-gcc-ar-cow-archive-20261020（旧/新单元结果、完整XML、类型/工程验收、JPEG/GCD旧库观察、未派发后继收尾）；var/business/a25-goal-path-lifetime-diagnosis-20261019（旧二进制拒绝/取消、保留坏库、r3构建/回放及独立门禁）。未采用候选、旧失败和实际费用均保留。

r59沿r58已计费ID去重，新增10终态（9成功/1取消）、采样CPU26693.32秒，未知attempt用量0；18项本次观察未终态任务待闭合。另记真实Codex/GCD中断资格一次模型/一次EDA、19.6452秒墙钟；中断模型usage未知，已知token总数不增加，调用数增加1，不把未知当零。服务、准备、测试、主Codex及未回收计算范围仍未知，不与EF费用盲加。

主根文件：本报告说明缺陷、范围、门禁和继续路线；TASKS.md更新实际任务状态；此前真实Codex收尾报告追加本轮构建结论。所有运行产物留var，模块主版本与活动服务不变。

## 同日续验：新二进制、原条件回归与GCD归因恢复

最终r3链接ef488f成功，采样CPU1334.78秒、峰值4819644416字节。新二进制SHA为27f81fd6f64ca9d0500c7abfdc38eacb4d6f54063e73f17f18218987bbd5a0db，已与旧父项c2ff…区分。独立核对四个公开构建任务、67份注册捕获、701份声明源码/原父树、实际编译/链接规则及唯一当前策略对象通过；这证明本次最小路径修复确实进入新可执行文件，不等于全部物理与业务验收完成。

第一次读回审计错误地用receipt字典顺序推算ZIP编号，在此前分析探针的捕获集合上失败。保留原脚本/日志后，以成员basename和内容SHA的精确多重集合核对相同原件，通过后才签发independent-build-acceptance-r3.json。没有因此重编译或重跑EDA。相关未派发守候者按实际终止状态更换，新source规格/旧失败保留。

回放也暴露两项管理脚本错误，不能归咎于专业策略：一次遗漏原命令的-threads 8，实际进程为129线程，已取消并保留成本；随后r4严格从原失败/正常请求复制命令，只替换二进制与输出Tcl。两个8线程原生样本均到达post_route及正常结束标记、未出现原Signal11，但清单误写evaluate.tcl而实际为flow.tcl，导致后置归档失败。原EF任务ee2d954…、1f125994…继续保留failed；不能把它们写成完整EF成功。

恢复阶段没有再次调用OpenROAD。通过公开EF分析任务159757d8…、898ccd14…登记实际flow.tcl、ODB/网表、公开原日志、源补丁及构建证据，每份14项捕获独立核对通过；labels中的analysis_of_run_id准确指回原失败任务。原生零退出由冻结leaf控制流推得：非零工具退出会跳过不存在的捕获文件，本次copyfile异常发生于code==0；没有把此推断冒充原来已落盘的进程回执。两份注册产物及真实8线程日志已核验，随后共同DRT/RCX仍在进行。恢复初版误用Jobs结果形状而在读日志前失败，改用现有公开client.materialize_artifact后通过，同样没有重跑物理计算。

### GCD：干净重建重现原成功候选

另设var/business/a25-selected-source-requalification-20261020，借用原候选源码只读构建，不加入路径生命周期C++补丁、不改原配方或目标。GCD和JPEG各701份声明源码、46项原输入、原Tcl仅输出路径变更和真实交接父run均在派发前独立核对。原生测量复用Goal自己的ResilientCommandRunner/EF适配器、原执行策略/容器环境/Query上下文；平台只接共同物理复测和DF/SDK交付。准备中的类型和取证器失败保留，原生测量派发前已修正静态检查；原生EDA及模型没有为此重做。

GCD选择的Student02已以唯一当前归档对象正确重建，仍得到原1cee1d7f…二进制。新的原生EF任务5d6d6036…成功；12份前后网表/ODB与原运行逐字节相同。该控制支持原GCD候选可由所记录源码正确重建，原PPA/证明/重放及相应源码收益结论得以保留；不能仅由旧库存在重复成员就推断其优化失效。没有新增GCD改善率或跨设计泛化结论，新的共同交付仍待收尾。此时JPEG Student03尚在重建；其后续终态及差异见下节最新续验。

该观察时点有效主管为selected-source构建483449、原生Goal测量671155、共同交付671173及r4旧产物恢复866630；其中构建与原生测量均随后结束，最新身份以下节为准。原CPP回放643524、旧参考1705515及旧接力1479386已结束，不重启其固定旧来源。

### 整体进度与费用

JPEG健康Flow第一轮50份route均已公开成功；这不是完整2×50结束或50份业务可行。主主管1557962、既有五策略1459962、20%对照3133532和AES证明3434644仍实际存活。源/环境/AST/EPD及正式配置冻结、完整专业参考/真正Flow接力、A26/A27与A28均未完成。

r60从r59去重，11新增终态（10成功/1取消）、采样CPU35176.73秒；r61再补12终态（10成功/2归档失败）、采样CPU20808.83秒，未知attempt用量均0，r61观察8项未终态。注册分析不重复计算原生EDA成本；本续验没有新增模型调用。已中断模型、服务/主Codex/准备/读回等未知范围仍不填零，账本不是全场完整费用。

新增独立依据：independent-build-acceptance-r3.json、independent-recovered-native-acceptance-r4.json（在路径诊断目录），以及independent-preparation-acceptance.json、independent-gcd-rebuild-equality.json（在selected-source目录）。私有脚本、失败记录及运行数据均在var；本次主根仅更新本报告和TASKS.md，未修改受保护评测代码、DF/DI工作树或活动服务。


## 最新续验：两源码构建成立、JPEG原生复现与完整参考恢复

selected-source构建483449及原生671155均已终态结束。独立读取六个公开构建任务、18份注册捕获，核对每个候选701份原只读源码、真实CMake编译/链接图、66个唯一库成员及当前策略对象：GCD仍为1cee1d7f…，JPEG Student03仍为a8e42d81…，均与各自旧选中可执行文件相同。因此本次选中JPEG的差结果不能归因于归档器丢失该源码改动，也不能由此替其他三个旧候选作源码执行保证。

原生EF run-3407bfa095444fad9a4d4ebb7f121ad3成功。公开原/新注册归档及其全部捕获独立核验：GCD12份阶段网表/ODB逐字节相同；JPEG六份网表相同，六检查点12个TNS/WNS打印值逐值同原运行，但post_repair_timing、post_placement及post_route三份ODB字节不同，合计9/12文件同值。未将该差异推断成唯一的序列化或行为原因，也未宣称最终物理已同值。原执行policy保持；请求环境仅本机代理绕行名单增加::1，实际容器OMP/OpenBLAS/MKL仍为8/1/1。不是请求环境全部字节不变。

首次构建审计错误假设新workspace还复制了source，实际构建图使用已固定的原候选只读源码；失败脚本/日志保留，r2沿真实request.source、编译命令和注册捕获核验通过，没有重编译。原生度量JSON由完整Evaluator后处理生成，纯ResilientCommandRunner回放只产生原生文件/日志；阶段复核从注册日志和原文件查证，没有编造缺失JSON或补跑EDA。

### 第一份路径兼容最终交付

原8线程power_then_timing兼容回放的保留产物经共同完整DRT/RCX及ORFS/OpenSTA交付，测量run-ba5a34d02f8c487280bc57029841cdef、物理run-5531332090e942ffb0696d293152ebed。最终功耗154.87778187mW、单元面积6345.92um²、setup TNS−0.299236ns、WS−20.2225ps、hold TNS0，原setup约束仍失败，不采用。独立核对注册测量归档的九捕获、原native-metrics及唯一report_power总值，重建七PPA后与宿主和公共SDK逐项同值；注册分析父run仍准确指向原归档失败任务，没有把原failed改成成功。另一timing_only共同物理继续，配对结果未齐。

该只读审计先有一项Zip流类型注解诊断，实际查证已通过；改用分块SHA消除类型问题，静态/格式再通过，没有重复EDA或模型。这不是新PPA优化成绩、功能证明或独立物理重放。

### 原完整专业参考已重新接续

新增var/business/a25-native-professional-control-correct-archive-20261020，以已通过473检查及真实构建的d5a3a95为Goal控制器；C++仍为原701文件seed，原baseline/专业参数/Teacher与四Student/AST图/EPD、模型、目标和晋升保持。原生CLI保留--repository-graph on，使用新campaign；实际能力完成情况仍须搜索后审计。此为同源warm开发资格，不是cold正式效率样本。

新主管1091379/start_ticks860931853已实际运行，等待原主Flow1557962/856018740完成后才派发原完整1×4、43200秒搜索，整体由EF32GiB任务管理。旧1705515固定规格及证据保留，不重启。传输/链接预检仅按实际代码字节相同复用原证据，没有新增预检模型或将准备记作完整运行通过。三个准备/运行脚本的Ruff F/I、格式、Pyright及真实无派发预检通过；初始JSON递归返回类型诊断和退休回执字段探针失败均保留。主模块、活动专业副本、服务及公共契约不变。

### GCD共同复测的私有SDC配置错误

本轮selected-source的私有local.json继承旧ns SDC（SHA92e75554…），原目标要求已固定ps SDC（SHA990385fb…）。原route run-7d4ba7c8cc4c49dca6e3666aa1dbf85f完成后，现有测量门禁拒绝“Measurement SDC differs from the shared objective”，尚未派发错误测量。不能把该次路由记为满足原目标的共同复测，也不能放宽哈希要求。

保留旧配置/路由及失败，以local-gcd-canonical-sdc-r2.json仅绑定原目标要求的SDC，其他设置保持；新key a25-gcd-selected-source-correct-archive-canonical-sdc-r2由1181038/860984753完成共同物理与数据交付，直接复用已成功的同一原生5d6d6036产物。没有重做原生优化、模型或源码构建，没有修改原目标或运行中的JPEG配置。新正确绑定的最终结果/独立验收尚待收取；此前GCD已验证的原PPA与源码重建结论不受本私有配置错误替代。

### 检查点与剩余工作

原主Flow仍在首轮评价屏障：38/50布局、49/50 CTS、50/50 route成功，失败保留；完整2×50尚未结束。五策略最终控制、20%控制、第二份兼容最终、selected-source共同交付、AES129输出证明继续。JPEG真实Flow→新Query→Goal接力仍须用合格seed/精确环境重新绑定；如换C++seed，须重新生成实际AST/EPD并实测baseline，不能沿用旧基线身份。A25未冻结，A26/A27正式实验及A28审计未完成。

r62从r61已计费ID去重，新增8成功终态、采样CPU10132.85秒、未知attempt用量0，另观察8项未终态；没有新模型调用。费用仍不覆盖全部主推理/服务/测试/准备/读回，未知不填零，新排队和后续任务继续待闭合。保护的26份用户文件SHA保持，用户评测代码及DF/DI修改没有执行、stage或部署。

新增依据：selected-source目录的independent-selected-builds-acceptance.json、independent-native-replay-acceptance.json；路径诊断目录的independent-first-compatibility-final-acceptance.json；新原生参考preparation-acceptance.json及launch/full-native-receipt；GCD纠正的gcd-canonical-sdc-r2-preparation.json及launch/receipt。根仅修改本报告和TASKS.md；所有新脚本/数据留var，不为纯文档重复全平台回归。
