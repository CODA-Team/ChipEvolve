# A25：专业策略反馈进入真实接力及参数选项核验

本轮补齐“已得到最终反馈，却尚未进入后续专业决策”的具体缺口。没有新增通用Agent框架或更改专业算法；A25未冻结，A26/A27正式试次及A28审计均未完成。

## 新交付的JPEG策略结果

既有reroute_mid_power控制的完整DRT/RCX与共同测量已成功。通过公开EF核验原生producer→物理→测量父子关系、注册归档及全部捕获SHA，从原native JSON/report_power恢复七PPA，再通过既有公共SDK读取同设计/run数值。结果为155.09437025mW、6378.88um²、setup TNS−0.575966ns、最差slack−30.3552ps、hold TNS0。原setup约束仍失败，不采用；这不是新模型或新的策略搜索。

独立证据：var/business/a25-relay-strategy-feedback-20261020/independent-new-controls-acceptance.json。关键路径配方物理run-146007b…随后已成功，但其共同测量run-7091ff…仍排队；不能提前引用最终结果。原timing_only控制仍等待同一EF任务。

此前同c2二进制/last_gasp配方的20%对80%控制已证实：仅改变原功耗回收比例，最终WNS改善17.6174ps，绝对TNS减小约65.80%，功耗增加0.0473174%；两者仍setup失败。它只能为下一步选策略提供依据，不能直接证明新Flow父状态或路径兼容二进制会有同样收益。

## 两个原生参数选项，独立环境绑定

保留原80%部署与模板不动；另建local-reclaim20.json和goal-campaign-reclaim20.json。独立逐字段比较：部署只改变campaign_template路径，模板只改变power_reclaim_proportion_percent的80→20。目标、权重、Teacher/四Student、AST/EPD、源码修改要求、评分、晋升及配方均保持。

原Goal自身工作目录/解释器的配置加载器真实读取20%，四Student、ast_graph及repository_graph仍启用。当前根09f95a5、Goal控制器d5a3a95、C++seed8010354保持；新增选项通过实际公开EF探针run-f6660cebe805429ca29c1a72198e6468，四专业环境检查均通过。20%环境ID4903714c…、SHA dcaf24a8…，80%仍用既有精确环境。必须在实际新父状态上重新实测baseline、生成实际AST/EPD，不借用旧结果。

## 只替换尚未派发的等待器

原1332988/861077478经PID/start ticks、命令、无子进程、waiting状态及episode/dispatch均不存在共同核验，确认还未派发。只结束该等待器，保留原receipt和759份原固定输入；主Flow、原生完整参考、全部EF计算及服务均未重启或取消。

新的唯一等待器1719378/861343738位于var/business/a25-relay-strategy-feedback-20261020，固定775输入及26份用户保护文件。先等待原完整Flow和原生完整参考；派发前沿既有公开EF/SDK审计各项届时已完成的控制，生成dynamic-final-control-feedback.json，并把实际反馈/结果哈希加入原生episode输入。仍未交付的结果明确记录缺失，不补造或推断。

后续控制Codex先检查完整Flow并选择真实适用父项，调用新Query并将已验证控制、阶段差异、重复物理状态与限制交入professional context，再从80%/20%两个已核验选项中选择一个；保持原Teacher自主选择配方。实际只运行一份原完整1轮四Student，逐候选审查最终PPA；仅对可行子项进行全27输出PDR和独立物理重放。八个原有收尾scope按唯一新key绑定，两配置使用相同state_root/EF入口。

新等待器和双参数选择已独立核验，静态/类型/零派发预检通过。**目前尚未启动实际新专业搜索，不能宣称Teacher已消费20%反馈或协同PPA已改善。** 正式单项必须获得相同参数选项；不把开发校准当正式试次，也不因团队投入较多而省略成本。

## 修复预算限制的实际来源

进一步按SOURCE_MANIFEST的原Goal上游1cc20aa核查：当前d5控制器的整个planning/timing_recovery.py文件与该上游逐字节相同。多个配方1–2次的pass/iteration参数及AES背景注释已存在于原项目，并非平台接入时新增。共同C++的reachedIterationLimit确实用正max_iterations判断停止；原Tcl缺省为max_passes10000、max_iterations−1，配方会显式覆盖。

这说明需要检查原生策略是否对JPEG充分收敛，但尚无本轮cap-saturation实测，不能断言它是失败的唯一原因，也不能静默删除原专业边界。当前接力保留配方和算法，仅开放已有功耗比例参数。证据为original-recipe-limit-provenance.json；后续如研究修复余量或预算，应另建匹配控制，区分策略收益和C++增量收益。

## 当前真实计算与成本

AES既有整体证明run-d223b728…已实际running，EQY完成combine/partition并开始pdr。读取当前partition.list和partition JSON核对：确实只有一个分区，outbits精确覆盖done及text_out全部129位。仍无PASS，不把覆盖检查当功能证明；旧已取消策略不重开。当前证据为current-aes-whole-proof-running.json及current-aes-whole-partition-coverage.json。

r65从r64已计费ID去重，新增4个成功终态，采样CPU7232.81秒、未知attempt usage0；包括两份原生策略物理、reroute测量及新20%环境探针，另有5项本次观察未终态。无新增模型调用，已知token及episode次数沿用；主Codex、服务、准备/测试及未终态费用不填零，不将重叠CPU范围相加。

仍需完成AES全输出证明及环境资格、剩余策略最终读数、正确SDC下GCD/JPEG选中源码复测、原完整JPEG2×50、原生完整参考与本轮真实接力；之后收口合格版本，冻结精确来源/模型/策略/停止及冷暖状态，再执行A26/A27和A28。团队PPA可累计各专业充分预算，保留原硬约束并披露成本。

本轮根文件仅本报告和TASKS.md；私有脚本、配置与证据留var。没有修改、执行、stage或部署受保护admin/evaluation代码、DF/DI工作修改，没有产品公共接口、数据库、全局资源池或服务变更。
