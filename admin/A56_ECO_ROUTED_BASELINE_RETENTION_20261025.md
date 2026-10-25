# A56：修复 ECO 首轮退化仍被当作最佳结果

基线根 `74c96bd`、ECO `6c46447`。本轮核查 A55 找回的 Ariane/ASAP7 来源之后的真实 ECO 分支，定位并修复最佳状态选择/交付问题。没有重跑模型或八轮专业搜索，没有改变原目标、WNS 排名、ECO 动作、评分、周期、路由迭代预算和最终采用约束。

ECO实现检查点 `f0f218e` 已发布到 ChipEvolve 的 `modules/timing-eco-agent`；根 gitlink/manifest 同步此源码，不向第三方 origin 推送，不热改旧会话副本。新专业轮次的业务验收仍待进行。

## 真正发现了什么

第一场每轮 DRT 会话 `run-b73f5c911f0b413bae04cbc1d5f3e138` 是有记录的主动取消，不是新的环境崩溃。随后周期 DRT 的八轮原生会话 `run-10dfb68566a24ed39bae121bd7e7d217` 实际成功结束；来源、对象/指标快照和原 ODB/SPEF 均继承正确。最终 PPA 不合格，不能把执行成功当业务通过。

原 EF 登记日志直接显示：

| 原生观察 | WNS（ps） | TNS（ps） | 原实际处理 |
|---|---:|---:|---|
| 输入，完整 SPEF 基线 | −288.838 | −127167.508 | 初始 best |
| 周期内 GRT 最佳，第 2 轮 | −292.973 | −91891.133 | 选择该 GRT 状态进入 DRT；不能与 SPEF 混作最终收益 |
| 第一轮完整 DRT 校准 | −366.345 | −493796.406 | **更差，却写成 best_drt 并导出** |

该次原生 DRT 还记录 12397 个 route violations；平台依据这份真实计数继续完整物理交付，并未将它误标为零。之后完整交付为 WNS −362.176 ps、setup TNS −462.748 ns、hold TNS −24.8699 ns、slew697、功耗644.54990625mW，最终 DRC0，仍拒绝。历史结果保持，不重新命名为成功。

源码原因不是专业评分不够强，而是周期 DRT 的首次晋升条件额外包含 `best_qor.get("cycle") is None`。初始基线没有 cycle 字段，因此第一次 DRT 无条件胜出，即使 WNS 更差。另一处相关缺口是匹配基线的 SPEF 只在 every-iter 模式初始化；单纯删掉首次例外，周期模式仍可能缺少被保留基线的最终 SPEF。

## 修改与业务效果

| 文件 | 本次职责 |
|---|---|
| `timing-eco-agent/src/main_orch.py` | 基线作为 cycle0/iteration0 的初始最佳；两种模式均保存基线 SPEF/视图；周期与逐轮 DRT 都使用原有严格 WNS 改善条件。EF 模式初始 ODB 保留登记输入原字节；等待初始快照完成后再继续。 |
| `src/platform_drc.py` | 把原生 WNS 比较抽成一个小内部函数，供两处晋升复用；原 DRC 计数/缺失判定保持。 |
| `src/platform_execution.py` | 原生 OpenROAD 导出 DEF/V/SDC 视图；直接复制所选 best_drt 的 ODB，不再次序列化它，保持 ODB 与原路由证据配对。内部导出函数仍在同一个 EF 会话进程树内执行。 |
| `src/test_platform_drc.py` | 覆盖真实 Ariane 退化、持平、真正改善、零 slack、缺失观测及无已知最佳值。 |
| `src/test_platform_execution.py` | 覆盖基线保留与已改善 checkpoint 的 ODB/SPEF/DRC 成套交付，导出失败不发布 ODB。 |

不再要求第一轮 DRT 必须成为输出；同时没有增加功耗、面积、TNS 或 DRC 的新专业晋升规则。WNS 更好的候选仍会入选，其他业务约束继续由既有最终交付/选择处理。这修复了“最佳状态”的实现，不保证每次搜索必有收益，也不把保留基线算作新增优化。

## 诊断、短验证和 code-check

1. 公共 EF 取回原八轮会话日志并核 SHA。直接执行旧源码的实际晋升表达式，真实 −366.345 相对 −288.838 返回 true，错误复现已留存。
2. 新源码的实际初始 best 表达式和周期晋升表达式重放同一记录，cycle0 基线保留、退化候选返回 false；真正改善仍由单元用例验证。这是决策重放，不是新实验。
3. ECO 全模块 **34 passed / 2 subtests passed**；根业务 **712 passed**。五个修改文件 Ruff 全通过，Pyright **0 errors / 0 warnings**。新增内部 helper/测试按整文件检查格式；大型上游脚本仅对改动片段做范围格式检查，不重排整份约三千行脚本。
4. 旧 main 本有115项 lint 及4项类型错误/18项警告。本轮在已修改文件内机械处理注解、转义、导入、等价解析表达式与已有类型不变量；原 Tcl 字符串常量逐项相同、异常类型/恢复处理不变。原生非致命 sidecar/恢复捕获及本地时间日志格式用局部说明保留，不增加新的 catch/fallback。范围格式整理前后完整 AST 相同，未改专业控制行为。
5. 通过 EF 在真实 GCD/Nangate45 500ps 已登记输入上执行新的原生导出函数：实际 OpenROAD2线程，ODB/SPEF 与输入逐字节一致，DEF/V/SDC 非空，DRC 证据正确继承已知输入0；公共 evidence bundle 的五份视图与两个实际 helper 文件 SHA 全部匹配。没有运行模型、ECO 动作、GRT/DRT、证明或共同 PPA 测量。

真实导出任务 `run-63be0848ce824682a09c349e82d507b4` 的原生命令成功，但私有核查程序填错 Tcl 采集路径，导致外层 extractor 收尾失败。原失败保留，检查后用 `run-9c310076f8d545c68444d9fd3ea908e5` **只登记已完成原件**；没有再次执行 OpenROAD。不是把原失败状态改成成功，也没有为核查程序的错误修改 EF。

私有核查脚本首次 lint 的导入/闭包绑定问题及首次类型诊断均保留修复记录。全部最终门禁分别核对退出码和日志，不以测试通过代替静态通过。

## 数据流、范围与接续

数据路径仍是 DF/DI 输入 scope → 原生 ECO → EF 内 OpenROAD → 选中 best ODB及匹配 SPEF/DRC → 原有共同交付/事实查询 → Codex 判断。没有新服务、公共 API、数据库或通用 harness。旧会话副本、原负结果、26 个用户保护文件及其他模块 WIP 保持。

证据位于 `var/business/a56-eco-routed-baseline-retention-20261025/`：原日志/句柄、before-failure-reproduction、actual-branch-replay、各静态/回归日志、原生导出与收尾失败、registered-export-execution、public-artifact-verification、静态整理的 Tcl/AST 对照。未来任务冻结正式 ECO 源码时消费该修复，旧实验不热切。

本轮解决了实际错误选择及其交付配对问题；尚未运行新八轮 ECO，也没有新的 Ariane 合格 PPA。Ariane 真实 setup/slew 债、GDS资料、Ibex/Nangate45 完整证明、另一个 PDK 的电气/最终资格、500ps协作和八组双次仍在总目标内。下一步核查专业探针返回空信息等具体分析能力问题，再做有界验证；长搜索继续暂停。
