# U4 施工前审计：GoalEvolve

日期：2026-10-13。范围：已授权推进 GoalEvolve 后，对具体接点与承重墙做只读审计，形成可确认的 U4 施工契约。业务代码未修改，未启动新模型或 EDA，未重置旧 L3 预算。

具体施工计划见 `U4_GOALEVOLVE_COMMON_TOOLCHAIN_PLAN_20261013.md`；证据根 `var/audit/u4-goalevolve-plan-20261013/`。

## 老板视角结论

GoalEvolve 已能在原环境重放发布结果，但还不能直接用本机 Codex 登录发动新的完整源码优化；共同环境和执行底座接入也尚未完成。本轮推荐保留研究框架，仅适配模型入口、专业共同源码起点/AST、确定性执行入口和必要测试资料。

源码审计证明存在集中接点，可以减少改动范围；实际编译和新优化收益仍须实施后验证，不能由静态阅读宣布可运行。

| 问题 | 源码证据 | 本轮具体处理 |
|---|---|---|
| 本机登录无法进入原 runner | `agents/codex_runtime.py:_ensure_home/_environment` 强制项目 dotenv，并生成每个 worker 的 API 配置 | 显式新增 existing-Codex 模式，复用当前登录；原 API 模式保留，不自动互相回退 |
| 实验由项目自行启动 | `evaluation/contest2026.py:_build/_build_relocated_cow` 和 baseline/evaluate 使用 `ResilientCommandRunner.run` 发动编译、OpenROAD、parser/checker | 在原确定性 runner 尝试边界使用公共 EF client；原日志和返回结构继续供 evaluator 使用 |
| 旧源码图不能代表新版源码 | `p0_campaign.py` 固定旧 p0/cache；`RepositoryGraphIndex` 已有新根路径注入能力，按实际源码 hash 验证 cache | 为共同专业源码重新生成 AST，保留原 AST/EPD 方法和四 Student |
| 只改 binary 路径无法获得研究功能 | 共同原厂源码没有 `repair_power`；其原调用链为 Tcl/SWIG→Resizer→Optimizer→RepairPowerPolicy，另有 timing 和 RMP recipe 依赖 | 提取专业增量和必要接口适配，真实构建验证，保留原 recipe 菜单 |
| 默认算法变化影响比较意义 | 旧 p0 detailed_placement 的 negotiation flag 缺省 false；新版默认 negotiation | 共同模式显式 Diamond，旧模式调用保持，其他评价阶段与指标不变 |
| 全套门禁未通过 | 官方未改源码实测九项失败，依赖未发布历史 local 配置、R54 父代源码和跨设计经验库 | 将单元测试改为可重建 fixtures 验证同一行为；真实研究运行仍记录历史资料缺失，不能编造知识 |

## 已核实边界

根基线 `b629e3f047d323b22315f639799efdf98d4530f0`，GoalEvolve 固定官方 `1cc20aa611e687c2745ff7da6a006a5d25f49f85`，正式源码干净。八模块 HEAD、工作树和相关控制文件 hash 在 `audit.json`；已有评测代码和 DF/DI 修改不纳入本轮施工。

专业源比较不包含测试目录，仅比较 C++/头文件/Tcl/SWIG/CMake：rsz 共有文件 81 项不同、p0 专业文件 12 项在共同版本不存在，rmp 3 项不同。具体文件列表在 `audit.json:source_differences`。差异包含上游演进，不能当作可整目录复制的补丁。

共同版本已有 Optimizer/OptimizationPolicy 架构，原抽象 policy 接口基本对应；共同版本仍有自身新的策略/接口，需要保留。RMP 的研究增量较大，包含守护、快照/回滚、路径云与 telemetry，不应因默认基线暂不使用 RMP 就删掉它。

原 evaluator 完整执行 repair_design、选择的 power/timing/RMP recipe、Diamond 详细布局、improve/mirror、合法性检查、global_route、寄生重新估算与真实报告。功耗 cache 刷新和单位设置有明确语义，接入不重写这些定义。

AST 主控必须继续运行在 Python >=3.11 的独立 GoalEvolve 环境。本机既有 L3 Python 3.12 / tree-sitter 环境可以作为核查依据；镜像 Python 3.10 不能替代此主控。模型在宿主，EDA 在共同镜像，parser/checker 由 EF 在兼容的独立 Python 运行。

旧 p0、发布候选、论文容差和 L3 的真实重放保持历史证据。共同版本建立新实验、新基线，不将旧数值直接用于新环境改善判断，也不把 ASAP7 与 Flow 的 Nangate45 混比。

## 原生门禁重新核查

使用正式未修改 GoalEvolve，现有独立 Python、localhost 代理绕过；缓存和测试临时目录均在本轮 audit var。运行 `pytest ... tests`，覆盖原生 unit/artifact。完整原日志、JUnit 和回执：

- `native-tests.log`
- `native-tests.xml`
- `native-tests-receipt.json`

JUnit 共 399 个 case（包含子测试），9 个 failure、0 error、0 skip，其他 390 个 case 成功；运行 450.177 秒。退出码 1，不能记全套通过；正式源码测试后仍干净。与旧报告的通过数因覆盖范围/子测试计数不同而不可直接混用，本次以完整 JUnit 为准。

九项失败分类：六项历史 AES local profile、一个公开 AES evolve profile 引用未发布 R54 父代、两项未提供的跨设计经验库。当前没有新增的业务代码回归，也没有重新出现 localhost 502。缺失资料的旧审计保留在 L3 `missing-assets-audit.json`。

## 需确认的新增契约

GoalEvolve 推进目标已授权，待确认的是 U4 计划中的实际技术范围：explicit existing-Codex、内部 runner→EF 委派、新共同 source/AST、Diamond 兼容、测试资料依赖修复、承重墙与 fork 发布。根 `AGENTS.md` 和老板协作协议要求具体文件/数据流/影响面先确认后实现。

确认前只做审计和项目文档，确认后进入 U4 实现；不自动将当前授权扩展到 DF/DI/Query 数据入口或完整三项目协同。
