# A63：修复 Query 的 hold 错答，核清专业估算与物理收尾边界

基线根 `025ebd2`、Query `54a08be`。本轮接续 A62，先做固定物理状态的 RC 对照，再修复由真实查询暴露的 hold 指标错答。Query 新提交 `f31773d` 已发布到原隔离模块分支，未切换集成候选分支。没有专业搜索、模型调用、重新布线、DRT/RCX、最终资格或采用。

## 老板可以据此判断什么

本轮确实修好了一处会误导决策的产品问题：问 hold，原 Query 却拿 setup 数据回答。RC 对照还确认，专业项目与 ORFS 使用不同的估算参数；这不等于底座坏了，也不能靠换表把设计“修好”。更实际的任务边界缺口是：setup 专业优化后，仍须明确处理 hold 和物理约束，不能把“执行成功”当作全部时序已经兑现。

## 已修复：hold 查询被当成 setup

原运行 `run-693be0f9f8c64e41bf55b84828e48625` 的同一个 DF 快照同时具有：

| 数据底座已有事实 | 数值 / ns |
|---|---:|
| TNS（setup） | −509.0591487986443 |
| HOLD_TNS | −98.49779581865572 |

旧安装包对 `Hold TNS?` 返回 `ANSWERED`，数值却是 −509.0591487986443，并引用 `metric=TNS`。这是真实错答，不是数据缺失或展示格式问题。原因有两处：通用指标识别先匹配 `TNS/WNS` 子串；带 timing/analysis 措辞的请求还会进入只支持 setup 的窄分析端口。

修复将明确的 hold 标量名称映射到 DF 已有的 `HOLD_TNS/HOLD_WNS/HOLD_WS`，并让这些请求走现有指标数据端口。支持 canonical 名称、自然空格形式、`TNS (hold)` 和原始 `globalroute__timing__hold__tns` 字段。普通、分析措辞和两运行比较使用同一识别结果；不扩展窄分析端口的域契约。

修复后独立安装包正确返回 −98.49779581865572ns；无修饰的 `TNS?` 仍返回 setup 值。真实正裕量场景 `Hold WS?` 返回 +0.019383717402046963ns，而 `Hold WNS?` 返回按定义截断的 0；缺少 hold 事实时返回 `NEEDS_MORE_DATA`，不会取 setup 代答。本轮只修标量查询，不宣称所有 hold 路径调查和专业修复能力已完成。

| 修改文件 | 职责 |
|---|---|
| `query-agent/src/query_agent/application/analysis_queries.py` | 识别明确 hold 标量，并避免交给 setup-only 的窄分析入口。 |
| `query-agent/src/query_agent/application/planning.py` | 普通查询、比较和证据要求保留正确 hold 指标名；其他意图规则保持。 |
| `query-agent/tests/integration/test_hold_metric_queries.py` | 用同时存在且数值不同的 setup/hold/analysis 事实验证选择、缺失、正裕量和比较。 |

原有函数签名、数据结构、DI SDK、DF 服务和专业算法保持。新 wheel 与源码、安装环境的 97 个 Python 文件逐字节一致；相对 A53 wheel，仅上述两个产品文件变化，其他 95 个 Python 文件相同。

## RC 对照：相同物理状态、相同 guides，只替换参数表

从实际固定镜像经 EF 取回 ASAP7 的 `setRC.tcl`、平台配置及 `rcx_patterns.rules`：

- Goal 校准表与 ORFS 表不同。例如 M2 电阻分别为 0.0462311、0.0297127；clock wire 电阻分别为 0.0513971、0.0214161，分别相差约55.6%和140%。读入时单位为 kΩ、fF、µm，源表在设置显示单位前应用，未发现本次单位错配。
- 两份 RCX 规则 SHA 完全相同：`32a117e5e866d3de1406e8f18d65b6f1857781f156638941a4769e25ef5252cc`。不同的是早期估算表，而非两套不同的最终提取规则。
- 每个物理状态内，两次分析读取同一 ODB/SDC/库、相同 saved guides 和同一 A38 二进制，不运行优化或 global_route。原状态2004630条 guides，新专业后继1604090条；各 RC 对内计数一致。

| 物理状态 / RC | setup WS / ps | setup TNS / ns | hold WS / ps | hold TNS / ns | slew / cap / fanout |
|---|---:|---:|---:|---:|---|
| 原布线状态 / GoalRC | −294.2331 | −91.995811 | +6.9796 | 0 | 113 / 0 / 0 |
| 原布线状态 / ORFSRC | −301.8374 | −109.663357 | +3.8541 | 0 | 0 / 0 / 0 |
| A62专业后继 / GoalRC | −433.7904 | −451.768939 | −116.4069 | −94.280476 | 164 / 0 / 0 |
| A62专业后继 / ORFSRC | −360.9309 | −172.776969 | −63.5938 | −27.370714 | 0 / 0 / 0 |

原状态实际 SPEF 测量可复用 A62：setup WS约−288.8381ps、TNS−127.167514ns，hold WS约+9.7354ps、TNS0。估算表切换并不保证每项单调变好，也不能把估算下 slew=0 当成修好了原 SPEF 中的444条违反。因此本轮**没有替换专业 PDK 表或降低最终约束**。

A62未优化起点在新原生 GRT 协议下就已有 hold TNS约−98.50ns，故不能把新后继的所有 hold 欠账都归罪于3388次VT动作。当前证据把问题定位在专业重建/布线估算及后续修复分工边界，尚未将输入准备、路由拓扑和模型影响完全拆开。

本次从保存 ODB 恢复的后继 GoalRC TNS为−451.768939ns，与A62现场−451.843205ns相差约0.074266ns；WS保持。本轮另存新测量节点，不覆盖A62，也不声称GRT估算可仅靠ODB逐值精确重放。

原生任务 `run-172ee7ff1b52405593ea98558cb752bf` 成功，整体约148.36秒、CPU219.75秒、峰值约3.13GiB/5进程，四个场景均原生退出0。四份事实经既有 EF→DF→DI/Query 登记，正确 hold 数值、范围及引用 metadata 原字节全部核验；CSV 为 `RC-model-stage-table.csv`。

## 下一处具体任务边界

Goal本次原生策略是 `repair_timing -setup`；TimingECOAgent原提示和评分目标以setup为主。当前共同 `qualify` 负责GRT/DRT/RCX及测量，不自动承担修复。这些职责不能合起来就假定已覆盖hold。

实际镜像的 `flow/scripts/global_route.tcl` 已有完整收尾：`repair_design_helper`、增量合法化/路由、`repair_timing_helper`、再合法化/增量路由；源码明确写明修 setup 和 hold，`util.tcl` 绑定已有 setup/hold margin 与原参数。本轮仅通过EF提取并核对其源码，未执行这一修复。

下一项应核查如何把专业后继明确交给**现有原生物理收尾**，并使用已修的hold事实验证每段结果；保持专业算法与纯测量职责，不在qualify中偷偷加优化，也不新建Agent框架。长搜索仍暂停。Ariane最终setup/hold/电气资格、Ibex/Nangate45完整证明、GCD500ps协作和八组双次仍未完成。

## 门禁、发布和保留范围

- 先有真实旧包错答和13项失败回归，再实现；补入原始字段形式后新增共15项测试。最终Query **211 passed**，根业务 **712 passed**；Query全量lint/format/Pyright及3项import契约通过，六份私有host驱动也通过静态检查。
- 最终独立包14项真实只读查询通过，包括4个新RC快照、原错答样本、缺hold事实和正裕量。未新增EDA或模型调用来验证查询。最终 wheel SHA：`f0bf114cefb2fe5f4b8f5deb43dd545a0096595ccbcc3a830ce0eb91d10438bc`。
- 新八份待用配置位于 `var/business/a63-rc-model-correlation-20261025/configs/`，仅更新独立state_root及新Query解释器。Ariane/ASAP7继承A60修正PDN/FakeRAM声明，GCD/Nangate45保留A54联合策略；不改历史配置或服务。
- 原父项、输入、SDC、库、SPEF、专业RC表及26个用户保护文件保持；root业务Python及generic_agent/DF/DI既有修改保持。EF收口时五种活动状态均零，没有新采用、模型搜索或独立优化重复。
- 私有采集器初次误把两个不存在的可选源码路径列为必需捕获，已明确缩到实际存在的三份输入，用新任务保留失败后完成；不是产品leaf的故障。初次测试夹具语法/类型错误、最终包收紧非hold意图范围前的临时wheel均留证，最终门禁与SHA独立核对，不把过程失败记作通过。

证据目录：`var/business/a63-rc-model-correlation-20261025/`；关键为 `hold-query-before.stdout`、`RC-control-results.json`、`facts-receipt.json`、`installed-verification.json`、`native-hold-protocol.json`、`code-check.json`及门禁日志。

除三份Query文件，根仓库只更新Query gitlink/来源manifest、本报告、A54当前表、TASKS、ARCHITECTURE、STATUS。运行数据和wheel保留在var，不新增服务、公共API或数据库。总目标保持进行。
