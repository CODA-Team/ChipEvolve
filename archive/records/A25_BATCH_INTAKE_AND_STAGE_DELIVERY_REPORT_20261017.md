# A25：批量输入缺口与阶段数据验收

发现并修复了一项会吞掉搜索候选的入口容量问题。真实 GCD 首轮的 9 个 CTS 候选在上传输入时连接重置，尚未创建 EF run；原生 DRP 后续复制已有结果补足了 50 个布线输入。不能将 41 个 CTS 成功解释为整批正常执行。

EF 修复源码 `f54e9d6` 已发布，wheel 已独立安装验证；**生产服务仍使用原部署检查点 `942e0ef`，监听队列仍为 5，尚待计算安全收尾后原位启用**。当前搜索、原目标、参数域、评分及已记录失败保持。完整 JPEG/Code 接力和正式双核心对照仍未完成。

## 入口问题与最小修复

原生 50 个客户端会集中上传 profile、候选配置及 SDC。Python 3.12 的普通 `ThreadingHTTPServer` 默认只容纳 5 个等待连接；生产端 `ss` 确认了这一实际容量。原 CTS 日志中的九个失败均停在 `upload_input`，错误为 `Connection reset by peer`，没有对应 CTS EF 任务。

在同一 `/home` 文件系统的独立真实 Gateway/API/store 中复现：50 个并发客户端，旧服务 11 个客户端失败，117 次上传成功；失败同为连接重置。共享 `LocalHTTPServer` 采用 `socket.SOMAXCONN`（本机 128），两个原有启动入口都使用该类；源代码环境和独立 wheel 环境均完成 50/50 客户端、150/150 次精确 hash 上传。

没有增加重试、改任务格式、改工作线程/调度策略或研究算法。既有 HTTP 路由和错误语义保持。所改两个 Gateway 文件同时通过格式检查；尺寸登记只增加本次实际 8 行，总额 9090，不给未来增长豁免。

证据目录：`var/business/a25-gcd-canonical-source-20261017/ef-http-burst/`。

| 证据 | 实际结果 |
|---|---|
| `original-r1/summary.json` | 旧容量 5，50 个客户端中 11 个失败，均连接重置 |
| `fixed-r1/summary.json` | 源码环境 50/50、150/150，通过 hash 核对 |
| `wheel-fixed-r1/summary.json` | 独立安装 wheel 后 50/50、150/150，通过 hash 核对 |
| `pending-capacity-negative.log` | 仅恢复旧容量时，等待派发的完整连接批次测试超时失败 |
| 新容量回归 | 同一连接批次及实际 SDK 上传两项均通过 |
| `wheel-preparation.json` | wheel 与提交源码一致，六项依赖复用原生产 wheel 的精确 hash |

Gateway wheel SHA256：`6b5438ce230ef06bd3771bf43a23abaf5b85dd1ef5772113d6c3b625a4cf1bdf`。这些是入口正确性证据，不是正式时间或 token 收益。

## 单一状态入口显示缺失回执

原 `status --design` 的 `native_progress.closed_batches` 现在显示所有已记录 iteration 的已闭合批次：原生退出码、计划数量、已有 run 回执数量及缺失 slot。当前真实 GCD CTS 为计划 50、回执 41，缺失 `33,36,37,38,39,40,47,48,50`，即使原生退出码为 0 也明确显示。

“缺失回执”不擅自等同于“服务未接受任务”：一般情形仍需按原身份对账。本次九个槽位另有原上传堆栈，确认发生在提交前。入口只提供事实，不补算、改评分或写回原实验；旧迭代缺口在新一轮开始后继续可见。 两设计实际 status 读取均通过；GCD 已进入 iteration 2、phase 0 时，首轮九个缺口仍准确显示，见 `closed-batch-status-acceptance/acceptance.json`。

## 实际阶段继承与数据链路

GCD 首轮全部 50 个布线任务已经成功。按 DRP 复制完成后的 phase 4 检查点，逐一核对 50 份实际 EF 输入回执：继承的是原可信 donor 的 archive、ODB 和 SDC，均一致。41 个实际 CTS 生产者对应 50 个后续逻辑槽位。三处检查点目录采用了另一个相同字节的生产者引用，实际布线仍按声明的 donor 取件，ODB/SDC 字节一致；没有因此改动算法或错误拒绝继承。

50 份候选输入与继承 CTS SDC 的物理、虚拟时钟周期，在实际 ASAP7 首库 `1ps` 上下文中逐份一致。本核查只覆盖当前明确模板的时钟绑定，不是任意 Tcl/SDC 的等价证明。

全部 50 份原生评价已经经过 EF 导出、DF 导入，并从当前安装的公共 SDK 读回：150 个数值、原始 metadata、单位、评价上下文和生产者证据一致。核对的原始 JSON 通过公开 EF artifact 读取并验证 SHA；没有读内部数据库或部署用户未提交的 DF/DI。

这些是原生 CP0 评价事实，不能直接作为固定 FF/310ps 的最终 PPA。最终共同复测、完整功能证明和独立重放仍按原流程验收。

主要回执：

- `gcd-cts-pre-submit-failure-audit.json` 与 `native-pre-submit-failures/`：九个原始提交前失败。
- `iteration1-audits/1792202575645480283/summary.json`：三物理阶段完整已执行总体及 50/50 实际交接核验，明确包含九个提交前失败。
- `iteration1-clock-input-acceptance.json`：全部 50 份时钟绑定。
- `native-feedback-sdk-acceptance/acceptance.json`：50 快照、150 数值及完整上下文。

## 校准与边界

| 首轮实际 EF 任务总体 | 数量 | 已知 CPU 秒 | 最高进程树内存 |
|---|---:|---:|---:|
| place | 50 | 2892.99 | 642,478,080 bytes |
| CTS | 41 | 325.63 | 473,702,400 bytes |
| route/finish | 50 | 3403.81 | 2,156,990,464 bytes |

以上覆盖完整已执行总体，包含管理适配的 CPU，不是近期成功快样本。九个上传失败没有 EF 执行用量，其前端及未确认响应成本另记，不能统填零。JPEG 同池争用影响排队和墙钟；各任务排队时间重叠，其和不等于实验总历时。完整轮次、模型、准备、评价和其他成本仍须继续归集。

另对失败 JPEG slot 5 做了一次有界检查：同一归档 pre-DP ODB、15 份库、SDC、RC 和 padding=1/DPO=0，显式 Diamond 仍以 DPL-0036 失败；原默认 negotiation 为 DPL-0033。这个孤立检查不能证明改变默认算法会修复该点，活动搜索保持原样，也没有据此放宽参数或约束。日志及资源在 `diamond-native-result/`，结论为 `jpeg-diamond-diagnostic-conclusion.json`。

审计脚本的两处错误单列保留：先误用 DRP 复制前的 phase 3 检查点，后误把 SDK 摘要当作完整 snapshot。修正后分别按 phase 4、公开 evidence/完整详情指针核验；没有为审计脚本错误修改 DF/DI 或改写原结果。

## 工程检查与下一步

- EF 改动的三份代码/测试文件 Ruff、格式及完整 42 源文件类型检查通过；完整回归 395 项通过、1 项平台条件跳过，唯一尺寸门禁在精确登记后连同全部 guardrails/HTTP 48 项复验通过。
- 根进度入口 16 项针对检查、441 项完整根回归（17.31 秒）及产品/新增测试静态检查通过；26 份用户文件 hash 保持，未纳入本次提交。
- EF 五份改动为两个 Gateway 文件、对应 HTTP 测试、尺寸额度及原因登记；根实现只改进度聚合和对应测试。公开 EF 契约、专业源码、数据接口和原生算法保持。

下一步：保留当前完整搜索和 A7 验证的原句柄；确认消费者收尾及执行队列/attempt 空闲后，备份并只原位替换 Gateway wheel，沿原端口和状态目录验证实际批量入口及历史事实。随后完成 JPEG 两个 Code 健康轮次、实际接力和最终验证，校准后冻结 A25，再运行 A26–A28。正式试次必须记录提交前失败，不能将没有物理评价的候选当作参数性能差，也不能用本轮带输送故障的预演冒充公平协同收益。
