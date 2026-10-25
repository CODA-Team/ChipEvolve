# A65：修复 hold 路径被 setup 路径代答

基线根 `7dfe907`、Query `f31773d`；Query 新检查点 `5291730` 已推送原隔离模块分支。本轮修复一个真实查询错误，没有新 EDA 实验、模型调用、专业搜索或服务变更。A64 的物理修复仍为独立接点验证，尚未自动接回公共业务入口。

## 实际问题与修复效果

同一 Ariane/ASAP7 原最终 SPEF 快照中，setup 与 hold 原报告均已在 DF 登记。旧独立安装包收到 `Show the worst hold timing path`，仍返回 `ANSWERED`，第一条却是 setup `path:5`、slack −288.8ps、终点 `axi_req_o[158]`；引用也是 setup 原报告。正确 hold 首项为另一条 `path:10`。这是 Query 类型传递错误，不是底座缺少 hold 数据。

| 同一既有物理状态的查询 | 旧包回答 | 新包回答 |
|---|---|---|
| 最差 hold 路径 | 错用 setup，−288.8ps | hold，+9.735ps |
| 最差 setup 路径 | setup，−288.8ps | setup，−288.8ps |
| 无修饰的 critical path | 未明确区分类型 | 默认 setup，并在证据中标记 |
| A64 的 setup / hold TNS | A63 已修正标量语义 | 保持 −92.960533493ns / 0ns |

这些数字是**纠正查询对象**，不是把同一路径时序改善了298ps。Ariane 原物理产物与 PPA 没有改变；A64 是另一 GRT 状态，也不能与本次原 SPEF 路径混作同条件时序对照。

原因为：简单路径解析没有保留 setup/hold；Query 的内部 analysis 端口也没有该参数；DF adapter 未向已安装 DI SDK 传 `check`，拿到混合路径后直接按 slack 排序取页。较差的 setup 路径因而挤占 hold 请求的返回页，内部 DTO 与证据还丢掉了实际路径类型。

修复使用现有 DI `get_timing_paths(..., check="setup"|"hold")`，在服务端按类型筛选后分页。内部 analysis 端口增加可选 `check`，默认 setup；路径观察和证据携带原记录的类型。中文“保持时序路径”与明确 hold 问句得到 hold；A63 的 HOLD_TNS/WNS/WS 标量规则保持。没有 hold 数据时不拿 setup 代答；原记录缺类型时保留未知、不标成完整事实；返回明确矛盾类型时保留边界错误。

这只调整 Query 内部端口及类型，不增加 HTTP/CLI 参数，不修改 DF/DI 服务、SDK、专业算法或 Codex harness。批量和复杂调查继续通过既有 Codex-hosted 工具完成，不将此窄修复称为全部时序归因能力完成。

## 修改文件与数据流

| Query 文件 | 职责 |
|---|---|
| `application/analysis_queries.py` | 明确路径问句的 setup/hold 类型。 |
| `application/collection.py` | 向端口传类型，在返回证据和文字中标记实际类型。 |
| `ports/analysis.py` | 内部路径端口增加默认 setup 的可选参数。 |
| `domain/analysis.py` | 路径观察保留可选原始 check，未知仍为未知。 |
| `adapters/data_foundation/models.py` | 接收 DF 已有的路径类型字段。 |
| `adapters/data_foundation/provider.py` | 通过现有 SDK 请求相应类型，保留来源、单位、范围与分页语义。 |
| `adapters/analysis/fixture.py` | 既有测试夹具显式为 setup，不伪造 hold。 |
| `adapters/analysis/unavailable.py` | 与内部端口签名一致，缺失能力仍如实返回。 |
| `tests/contract/test_data_foundation_adapter.py` | HTTP 类型筛选、分页、证据及缺失/矛盾类型回归。 |
| `tests/unit/test_analysis_provider.py` | 同步测试子类签名，验证仅有 setup 时不能回答 hold。 |

上表产品文件均在 `query-agent/src/query_agent/` 下；两份测试在 `query-agent/` 下。数据流为问句→Query 内部类型→既有 DI SDK→DF 按类型筛选的页→携带类型/单位/来源的证据→Codex。要修改类型选择，改解析器；修改传输或证据，改 adapter/collector，不能通过改事实数值实现。

## 验证和 code-check

- 新增8项回归，完整 Query **219 passed**，根业务 **712 passed**；Query 全量 lint、格式、Pyright 和三项依赖约束通过，三份私有验证脚本同样通过静态检查。
- 独立 wheel SHA256 为 `18610a3ad54f30dcc5e8aeb494c5e75b3e0e88c246a4a241a58c1d7568047712`。源码、wheel 与新安装环境97个 Python 文件逐字节一致；相对A63仅上表8个产品文件不同。
- 新安装包8项真实只读查询通过：三种hold问法、两种setup问法、默认critical path及A64两种TNS。每条路径的ID/check/slack/unit/scope与独立SDK请求逐项核对，未只看 `ANSWERED`。
- setup/hold 两份原报告均从公开EF材料化，完整文件SHA与DF证据一致；各65536字节DF原件引用与EF原字节匹配。报告生产者为 `run-4846723e5c124f6bb4be0eb546db25b7`，不是新测量。
- 八份待用配置仅更新新Query解释器与独立state_root，原PDN/FakeRAM、GCD500ps和专业策略全部保留。旧环境和历史配置不热切换；实际新配置在 `var/business/a65-query-path-check-20261026/configs/`。
- root业务Python与26个用户保护文件保持；没有新增服务、数据库、专业动作或采用结果。收口时EF五种活动状态均零。
- 初次回归中的3个语言变体复现错答；另4个初始夹具漏写managed-run模式、初次Pyright的Literal推断问题已纠正并留存过程日志，不将这些夹具/静态失败说成额外产品故障。

运行证据在 `var/business/a65-query-path-check-20261026/`：`reproduction.log`、`before-*-Query.stdout`、`installed-verification.json`、`code-check.json`、完整门禁日志、两份原EF报告及新wheel。运行数据不发布。根仓库仅更新Query gitlink/来源manifest、本报告、A54、TASKS、ARCHITECTURE和STATUS。

## 物理接点的后续边界

审查现有入口确认，`run --capability orfs` 分支只调用 baseline，没有消费 `--source` 的物理接力行为，不能借用这一组合后声称已具备自动接力。`qualify` 是补路由/提取/测量，不能暗中增加修复。原候选证据也绑定专业选中检查点的生产者；新的物理修复必须另记后继生产者，保留原专业证据及可恢复身份。

下一步应在既有业务结构中明确这项显式请求、独立接力节点与恢复记录，再复用A64已通过的原生机制。不能为接通一条调用而破坏候选溯源或把全部Goal交付默认改为另一优化策略。本轮未完成该接入，也没有借新建框架/服务绕过它。Ariane最终资格、Ibex/Nangate45完整证明、GCD500ps协作及八组双次仍未完成，正式长实验保持暂停。
