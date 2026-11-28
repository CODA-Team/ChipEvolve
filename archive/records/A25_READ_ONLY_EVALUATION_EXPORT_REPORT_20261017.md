# A25：减少只读评价的重复物理归档

JPEG 首轮原生 CP0 评价暴露了一项实际管理开销：成功的只读评价会把继承的全部物理文件再次压缩和登记，Flow 后续只消费该评价的日志和结构化事实。以首个实际任务为例，声明产物合计约 1.46GB；这是逻辑引用体量，不能直接算成新增磁盘占用。原生收据生成后至 EF 终态仍有 43.26 秒，包含归档及后续托管成本。

## 改动和业务边界

- Toolkits `src/eda_toolkits/openroad/a2_stage.py`：成功只读评价返回原日志、执行收据和 `a2-evaluation.json`，原物理状态继续由 EF 输入和父 run 追溯；物理阶段和已识别的原生/解析失败仍保留完整归档。生产改动只增加一个产物收集条件。
- Toolkits `tests/test_a2_stage.py`：成功评价不得再生成物理整包；既有真实 make 继承、失败归档、原时钟和单位检查保持。混合类型 profile fixture 补显式类型，静态检查不再误推成纯字符串字典。
- 根 `SOURCE_MANIFEST.json` / Toolkits gitlink：固定已发布源码 `a7fec1b`；本报告、任务、架构和协议记录源码资格与待启用状态。

数据流仍为原物理父产物 → EF 只读评价 → 原 CP0 日志/结构化结果 → 原反馈接口 → DF/SDK。Flow 的评价分支本来只读取 `extractor_log`，反馈读取 `a2-evaluation.json`；物理检查点的生产者选择只查 place/CTS/route。插件清单要求日志和收据，`flow_archive` 为可选。因此没有新公共函数签名、API、数据库或研究算法，不用削减原能力换取开销下降。要调整成功评价的产物策略，修改 `a2_stage.run_stage` 的收集条件；评价算法和数据语义仍在原 evaluator / feedback 代码中。

## 检查与实际资格

新增断言修复前 1 失败/14 通过，修复后 15 项针对、66 项 Toolkits 回归、23 项 Flow 执行/反馈/恢复消费检查、470 项根回归通过。Ruff、Pyright 和差异空白/格式检查通过。Flow 消费测试第一次从错误工作目录收集失败，改用本项目 `flow/` 工作目录后通过，没有增加跨项目源码路径或修改其代码。

新 wheel 独立安装在资格环境，未覆盖生产。通过现有 EF 提交原 JPEG 槽位 1 的同一份评价输入：原 staged input 哈希和 artifact ID、库、CP0、SPEF、镜像/工具身份及评价上下文全部一致，三项数值和单位逐值相同。新适配器只导出日志、收据、评价 JSON。

| 同输入工程资格项 | 原已完成任务 | 新 wheel 的 EF 任务 |
|---|---:|---:|
| EF 计算墙钟 | 68.40 秒 | 29.31 秒 |
| 已知托管 CPU | 65.12 秒 | 32.83 秒 |
| 声明产物逻辑体量 | 1,459,428,456 bytes | 81,944 bytes |

新适配器收据到结果生成约 0.00052 秒，至 EF 终态约 0.276 秒。两次处于共享主机的不同时间，新任务含隔离 CLI 包装；这些是一次同输入工程检查，不能作为 A27 正式平台/原生 Codex 效率比，也不代表整个优化流程加速。逻辑体量不是实际磁盘增长。

原生评价仍为原 TT/CP0 条件，三项一致不等于最终 FF/545ps 七项 PPA 验收。没有新增模型试次、优化搜索、C++ 构建、布线、功能证明或采用；构建了一个 Python wheel。当前控制资格使用同一 EF run `run-ddd5c06f19cb48568a64df25dc2eeaf4`、一次 attempt；最初检查脚本误读 `wait_run` 返回结构，独立核验只读取同一个已成功任务，未再次发起 EDA。失败回执保留，主 Codex/前端及独立服务成本另计或未知。

主要证据在 `var/business/a25-formal-preparation-20261017/a2-evaluation-retention-r1/`：`independent-acceptance.json`、`live/` 原始前后事实、`pre-fix-pytest.txt`、`engineering-gates.json`、`root-regression.txt` 和 `wheel-preparation.json`。新 wheel SHA 为 `7bc1e95525bf450d37c347fe1c7203914487ded6fba65758f5149fc650e4cecb`，与已提交生产源码逐字节一致；26 份用户文件哈希不变。

## 当前状态与后续启用

源码和隔离真实资格通过，**生产尚未启用**。原 JPEG 完整两轮仍使用原已安装版本，未编辑活动副本。生产插件以独立 a4 Python 子进程运行，a7 客户端是另一环境；两个环境及其旧文件哈希已明确记录，不能只更新 a7 就冒充插件更新。

启用接点现已准备：`activate_qualified_toolkits_when_idle.py` 校验已完成的原 JPEG 交付、原前端退出、公共 EF 空闲、两个环境的旧文件及新 wheel 指纹，随后只更新自有环境；插件为新起的独立子进程，Toolkit 更新无需重启 Gateway。当前直接执行的门禁反例已在安装前拒绝，两个环境哈希保持。`verify_activated_toolkit_native_feedback.py` 会通过实际插件运行原输入、导出原评价事实并从公开 DF/SDK 核对三指标、条件、主体与证据；这两项实际启用和生产核验尚未发生。

新 r4 串行队列 PID 4165026、句柄 87174，目录 `serial-calibration-continuation-r4-idle-toolkits/`，54 份输入指纹及 dry-run 通过。在原 Gateway 更新/实际接单验证之后加入上述两个步骤，再继续健康 DPL、Goal 和恢复完整范围的 GCD 搜索；原五条命令、模型、预算和相对顺序保持。r3 在零派发且无子任务时以 143 退出，原记录保留，没有取消 EDA、改动活动 JPEG 或提前安装。当前 r4 仍零派发等待原完整两轮，不能把门禁准备或隔离资格写成生产更新已完成。

A24 完整专业接力和预算校准尚未结束，A25 未冻结，A26–A28 未启动；公平团队 PPA 优势与原生 Codex 端到端效率收益仍待正式实验。
