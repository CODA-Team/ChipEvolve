# A29：邀请论文案例施工

老板已批准五切片计划：固定 GCD 成果、补齐四专业实际参与、按需扩展 ibex/jpeg/ariane、展示平台操作、汇总论文素材。GCD 优先，10/22 晚目标收口，10/23 前交老师审阅；不以全平台审查清零、完整统计配对或独立 AES 证明为前置。

## 切片一：已完成工程修改，实际业务验证进行中

- Goal 构建归档器修复 `d5a3a95` 已快进合入模块主版本并推送；新实验绑定该正式来源。原有 GCD 结果与验证不重跑、不改写。
- `chip_evolve/native.py`：Goal 原生 TNS 目标读取业务限制（本轮为零），功耗仍沿用原 10% 搜索目标；读取已存在的物理内存配置；ECO 显式八线程，并在新交付记录中声明已完成详细布线。
- `chip_evolve/delivery.py`：只有明确声明已详细布线的新记录走保留布线路径，原检查点保持原语义。
- `chip_evolve/physical.py`：对已布线状态运行 DRC 检查/RCX/共同测量，不清线或重新布线；GRT 检查点仍完成原详细布线。物理任务读取既有设计内存声明。
- Flow `162b80a`：保留 CLI 结构化失败或显式 Error 行，脱敏凭据，不再把所有错误统一写成检查登录。无原生算法/采样/模型重试逻辑改变。

没有新增 EF/DF API、SDK schema、服务或数据库，没有改专业评分/晋升。根新增 `admin/test_invited_paper_relay.py` 覆盖目标与布线交付；`admin/test_eco_pdk_binding.py` 实际执行生成的 launcher，核对显式线程参数。

## 工程验证

- 根当前已跟踪测试及本轮新增测试：549 通过；30 项针对检查通过。
- Flow：从原 flow 工作目录运行完整 test，97 通过。
- Goal：tests/unit XML 450 项，失败/错误 0，原跳过 3；完整 tests 扫描在第三方发布大目录 I/O 上过慢后中断，保留原日志，没有冒称发布产物全审查通过。
- 根产品/新增测试 Ruff、格式与实际安装环境 Pyright 通过。Flow Ruff F 通过；新增函数单独格式化，未批量重排旧代码。整文件 Pyright 仍报告原有四处类型诊断（transport 可空、schema 推断、isfinite 类型、动态 worker 属性），不把它们变成本轮无关重构门禁。
- 首次根/Flow 检查分别遇到旧 Toolkit wheel、缺 Runtime 测试依赖和工作目录错误；已在本轮独立环境安装本机已有 wheel、使用正确模块目录后通过。生产服务和用户 DF/DI 工作树未更新。
- 26 项用户保护文件 SHA 一致；跨模块依赖保持安装 wheel/公开 API。

证据目录：`var/business/a29-paper-delivery-20261020/`。新增本轮独立配置、输入引用和测试环境，不修改历史 runtime。模块提交不等于真实新接力已通过；后续记录实际 EF、PPA、DF/Query 和采用状态。

## 下一步业务验证

1. 已有 GCD routed 产物通过 EF 做一次保留布线的 DRC/提取/测量，确认交付不改变线路。
2. GCD Flow2-37 的原布局检查点启动 DPL 一轮三 Student，复用实际 Query 证据；再对其产物诊断并交给 Goal 一轮四 Student、ECO 最多八轮。
3. 同步准备 ibex/ariane 的实际 RTL/SDC/ORFS 配置，JPEG先复用已有可用候选。平台记录统一，不要求无收益候选成为最终祖先。

本报告后续只补业务结果；不把“已接受排队”写成优化成功。

## 审查反馈后的实际收口

- 老板已明确批准停止旧 JPEG 剩余搜索。核验原 supervisor PID/start ticks 后，仅停止该树 14 个进程；公开 EF 对其 3 个活动任务请求取消，全部完成结果保留。没有停止 EF/DF 服务或其他人的计算。
- GCD 新 DPL 已通过原三条基线并进入一轮三 Student；G03 的 Query 已完成4事实/4假设，实际定位 reg2reg 关键路径及驱动12负载的小 SLVT 反相器。G03→ECO最多8轮已提交；保留合法G02，独立新runtime的select已复用其原18输出PDR/重放验证完成，不重复证明。
- 修正本报告上节的初版功耗目标口径：平台不再生成通用×0.9目标，直接保留各实验专业模板声明的功耗目标，只映射业务TNS限制。本轮新GCD模板显式声明原目标函数的功耗最小化方向（零理想点），这是优化方向，不是声称零功耗可达或最终约束。
- 新保留布线分支增加“输入存在信号线”检查。第一次实际EF验证发现最新版工具把check_drc放在drt命名空间；修正为drt::check_drc后真实提取/测量/DF交付完成，组件、线路、引脚DEF段完全一致，七PPA精确同值。
- 该独立checker对同一G02返回5377个marker，而原详细布线流程报告0；不能把两者当同种指标。ECO模块090f866在原生best选择时记录当次DRT计数，导出与最终ODB SHA绑定的原件；平台保留原计数，独立checker值作为补充诊断。它的物理含义尚待专项核实，不宣称独立DRC检查为零。ECO原评分、best选择和回滚未改。
- 补充NOTICE明确ASU-VDA-Lab来源和原提交；没有虚构或替第三方授予许可证。
- 新根回归551通过；ECO15项通过；根/相关ECO产品与测试静态、格式、类型检查通过。
- ibex实际Slang综合完成，因绑定全VT库但原配置只加载RVT LEF而失败；新配置显式加载RVT/LVT/SLVT。为落实GCD优先，已收尾本轮自己的ibex并保留证据，相同配置在ECO前端结束后自动继续，不称原样默认ORFS。
- Ariane原研究ASAP7 placed基准和SRAM模型已找到并准备：210295组件、136 SRAM实例、21 Liberty和11 LEF。它不是原样ORFS RTL基准；尚未派发导入/布线，不把“缺ASAP7原生ORFS配置”误写为“所有PDK资料都缺失”。
- 四设计论文素材开始持续导出：[当前指标与接力图](INVITED_PAPER_RESULTS_20261020.md)、[11节点完整指标CSV](INVITED_PAPER_METRICS_20261020.csv)。新增DPL/ECO计算未终态前不填新PPA。

运行与取消回执、原失败和全部成本记录仍在本轮var目录。用户新提供的DeepSeek独立审查文档保持原样，不提交它或其他用户修改。

## 小设计资源接续与同一 Codex 的 Query 展示

- 本轮根 `native.py` 只向 ECO 私有运行 profile 传递 `session_memory_gib`，模块 `platform_execution.py` 将其映射为既有 EF 内存申请；默认仍24GiB，本轮GCD显式16GiB。八线程、八轮及原生算法不变，JPEG不套用GCD设置。当前两项DPL各8GiB占用16/32GiB，旧ECO24GiB排队属于正确资源等待；配置准备期间DPL一项构建完成，原ECO已按24GiB实际开始；保留这份正在运行的原case，不取消、不重跑，新选项仅供后续实验。未修改冻结现场或杀掉DPL构建。
- 根552项回归、ECO15项回归通过，两个接入文件和相关测试Ruff/格式/Pyright通过。首次误用旧模块venv缺Toolkit/pytest，改用本轮已安装公共wheel的独立测试环境；没有改生产环境或将测试依赖故障写成业务故障。
- `same-codex-query-demo-r2` 已由当前Codex用现有`--model host`完成两次实际DF事实读取及证据回答：保留G02，G03作为ECO探索分支；额外Query内部模型调用0，父Codex推理token未单独计量，不声称总token为零或节约百分比。两读取及初始化墙钟约1.346秒，回答另有原回执。
- 论文CSV把正时序余量列更正为WS，并另列规范WNS=min(0, WS)；没有修改原PPA数据。
