# 四项目工程验收与 Codex 对照（2026-10-08）

本轮完成独立开发项目、边界重整、单机执行精简、真实数据接入、独立检查与迭代验证。当前可用链路是：提交 EDA 实验 → 注册产物 → 不可变数据快照 → 公共 SDK → 主 Query Agent 查证与比较。下方列明可用功能和缺口；不能把四项目分开等同于全部智能能力成熟。

## 功能与职责

| 项目 | 当前交付 | 相对 Codex 直接终端的复用价值 |
|---|---|---|
| Execution Foundation | 幂等提交、生命周期、日志、失败、运行中取消、资源、产物哈希、重启追溯；一个本机 API+worker 进程 | Agent 不必每次重新写任务锁、进程树治理、状态库和证据归档；直接脚本同样能实现 |
| Data Foundation | 设计目录、精确作用域、不可变快照、实验/producer 关联、对象索引、canonical 指标与来源 | 不同进程共享数据归属与证据；直接 Python 内存字典在小数据下更快、更省空间 |
| Data Interface | 15 个工具定义、无运行依赖的标准库 SDK、URL 编码、透明错误/信封、py.typed | Agent 复用同一调用和缺数据语义；curl/urllib 可以等价调用，SDK 不保证更快 |
| Query Agent | 主独立实现接入对象、WNS/TNS、时序路径、指定实验比较、引用与可回答性判断 | 复用证据组织和拒绝过度推断的规则；当前是确定性 Python 策略，未证明优于 Codex 推理 |

Query Agent 通过已安装 Data Interface wheel 访问 DF；生命周期通过 EF 公共 HTTP。DF 从 EF 注册产物 HTTP 导入，禁止跨服务读私有数据库。数据阶段 timing/routing 与执行控制阶段 extract/package 分开；SDK 不再做目录聚合、名称猜测、指标所有权判断或 N+1 阶段过滤。

## 工程与环境

- 四个独立 Git、.venv、environment.lock.txt；只允许自身 editable，跨项目通过 wheel/HTTP。
- dev.py 清除继承的 Python 路径与用户 site-packages，本机访问绕过代理。服务只写新 var；启动入口为 18700/18924。
- 执行底座移除身份库、账号/会话、控制台、应用代理、plan executor。G1–G17 与负例保留；源码总批准上限从 9660 下调到 8970 行，没有扩大门禁。
- Query Agent 严格 Pyright 零错误；原未执行的 import-linter 已改为真正执行 3 条依赖契约。
- bootstrap 已实际运行成功，四环境 pip check 与 editable 归属检查通过。12 个废弃 wheel 保存在 var/archive，当前发布包有 sha256 清单。
- 旧生产目录、运行服务、工作树、大数据库未切换或删除。原用户修改有备份，纳入本地工程提交，不 reset。

## 独立验证

| 项目 | 当前测试 | 其他门禁 |
|---|---|---|
| Execution Foundation | 384 passed, 1 skipped | G1–G17/负例、41 个源码文件 mypy、变更 Ruff/Black |
| Data Foundation | 342 passed | 独立 HTTP smoke、作用域/归属/哈希冲突/单位转换负例 |
| Data Interface | 10 passed | 真实 HTTP 编码、单次传输、过滤与证据 detail 契约 |
| Query Agent | 87 passed | Ruff、format、严格 Pyright、3 import contracts |

总计 823 项通过，1 项宿主条件跳过。对应最终日志和环境清单在 admin/final-verification.json 与 admin/final-environments.json。机制 fixture、真实 EDA 和真实 Codex 试验分别记录。

## 真实 OpenROAD 闭环

纯 wheel 环境安装四项目，从非源码工作目录启动服务。Nangate45 三缓冲链在真实 OpenROAD 执行 STA；网络理想化，没有寄生或完整 PnR。

- 周期 1ns 与 0.2ns，WNS 从 0 变为 -0.0745538513ns；SDK 与主 Query Agent 查指标、查路径和比较均通过。
- 缺技术 LEF 的真实工具调用正确 failed。此 OpenROAD 构建部分 Tcl 错误会 exit 0，验收提取器同时检查 ERROR 与必需数值，避免假成功。
- 注册报告 artifact_id/sha256 对应实际 report.rpt，并通过 DF 来源接口取回原文。
- 明确为 ns 的时序路径保持正确换算；缺单位不生成确定的 ns 数字。
- STA 完成后人工等待的任务被运行中取消，用时 0.407s；保存资源与取消状态。该人工等待只检验取消机制，不是 EDA 性能负载。
- 重启 API/worker 和 DF 后，成功/取消记录、原产物哈希和数据快照仍可查询。

最终记录：var/benchmarks/real-acceptance-v5/results.json。两次成功短实验直接运行约 0.95/1.10s，infra 约 1.53/1.27s；入库约 0.026/0.021s。单次顺序测量受宿主和缓存影响，不能推断稳定性能优势。

## 真实 Codex 对照

共运行 24 次真实 codex exec。固定 gpt-6.1-sol、medium reasoning、180s 硬时限；每项每组两次，第二轮反转组次序。直接组可写脚本、锁和索引；同一设计/输入，两组均保留完整 prompt、schema、事件、答案、工具调用和 token 使用。方法参考官方文档：[noninteractive](https://developers.openai.com/codex/noninteractive)、[eval-skills](https://developers.openai.com/blog/eval-skills)，使用 OpenAI Docs。

下面是审查后的配对观察：execution/interface 取第一轮，data/query 取修复后的复测。每项两组均 2/2 正确；不把不同迭代混成总体胜率。

| 任务 | 直接终端平均 | 使用 infra 平均 | 工具调用平均：直接 / infra |
|---|---:|---:|---:|
| execution | 104.4s | 86.6s | 5 / 5 |
| data | 46.4s | 41.0s | 3 / 2.5 |
| interface | 24.9s | 31.2s | 1 / 2 |
| query | 43.0s | 48.8s | 3 / 5 |

模型 token 也有成本；累计输入含缓存，不能直接当账单价格。以下报告未缓存输入与输出的均值，保留各次完整 usage，不换算未经核实的金额。

| 任务 | 未缓存输入：直接 / infra | 输出：直接 / infra |
|---|---:|---:|
| execution | 29,292 / 35,008 | 3,302 / 2,812 |
| data | 22,402 / 22,740 | 1,044 / 912 |
| interface | 16,412 / 18,125 | 550 / 774 |
| query | 16,781 / 24,423 | 1,082 / 1,391 |

执行和数据组本次较快，接口和 Query Agent 组较慢。双方均能正确处理歧义、对象不存在和不支持根因。样本很小，CLI/模型与宿主波动明显；未证明模型推理质量提升、长期稳定加速或 token 普遍减少。资源测量范围也不同，不能用本轮 CPU/RSS 宣称更省资源。

第一轮原评分不能删掉：interface 四次因正确实例写在 evidence 而被只读 notes 的评分器误判；审查采用同一规则检查 notes+evidence。query infra 第一次只调用 SDK，不算 Query Agent 测量。data infra 有一次引用 ZIP 哈希作为包内报告来源，揭露产品问题。原结果、审查结果与完整轨迹分别保存。

## 基准驱动的修复

1. 实验比较曾被执行控制阶段否决：引入 DF 已索引数据阶段，补独立回归，比较通过。
2. 不同 producer role 使精确 report.rpt 未绑定，引用误落到 ZIP：按精确路径/哈希解析，容器与 member_sha256 分开，冲突不绑定权威来源。
3. 时序换算曾假定所有值为秒：按声明单位转换，缺单位不生成规范数值。
4. SDK 默认摘要省略每条路径来源，Query Agent 路径因此 PARTIAL：新增有界 detail=full 传输，QA 显式取每条证据；真实路径查询复测通过。
5. 评分器与实际组件调用检查已修正，data/query 的 8 次复测全部通过。第 3/4 项通过针对性回归和真实闭环验证；它们不改变复测的 WNS/实验比较任务，未额外重复模型试验。

失败记录在 real-acceptance-v1/v4 和 codex-pilot-v1；成功轮次不会覆盖它们。正式可复现入口为 admin/benchmarks/run_acceptance.py、run_codex.py、review_pilot.py。

## 合成数据机制测试

50k 对象、100 次精确查询：已加载 JSON 扫描中位 0.555ms；直接 RAM 字典 0.000902ms；DF 本地持久上下文查询 0.271ms。JSON 解析 0.0315s、建字典 0.00614s；DF 导入 1.13s。JSON 4.88MB，SQLite 40.99MB。

这是单进程热缓存机制微基准，没有 HTTP、模型或真实大设计；DF 返回上下文、RAM 字典只返回身份，两者工作量不同。结论是持久化/上下文有代价，不能宣称 DF 快于优秀的直接 Python。记录在 var/benchmarks/data-mechanisms-v1.json。

## 明确未完成

Typed 关系/fanout/location/region 的真实 provider、申请并自动提交补充分析、自主 LLM 根因诊断/优化尚未完成。大设计、多工艺、多 corner、完整 PnR、商业工具和服务崩溃中断恢复没有本轮验收。下一步应围绕这些实际任务增加对照样本，并先证明数据覆盖与证据可靠性。

本轮未接管旧生产环境。完整迁移核查在 SERVER_AUDIT.md；后续清理根据消费者和在途任务归档，不能直接删除大型历史数据。

发布溯源：admin/final-release.json 保存本地提交和当前 wheel 哈希；v2 的试验包清单在 codex-pilot-v2/wheel-provenance.json，v1 未单独冻结 wheel 清单，这是早期可复现记录的限制。模型临时工作目录已逐文件哈希核对后归档，原路径保留在轨迹中。
