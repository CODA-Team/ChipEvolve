# A53：跨运行比较不能把一份实验算两份

接续根A52、Query `23508a2`。当前实际安装包对两个相同run ID返回ANSWERED，回答同一run与自身差值0、附两条重复证据；已在真实GCD测量run复现。

## 修改与数据流

- `query-agent/src/query_agent/adapters/run_evidence/experiment_context.py`：显式运行ID按顺序去重后读取，减少同一handle重复GET。
- `application/answerability.py`：仅跨run比较按不同run计数；同一run两个snapshot或原件不能满足两run要求。普通单run多证据查询保持。
- `application/service.py`：数值比较选取不同run的观察，全部原件证据保留，避免前两条恰好来自同一run。
- `tests/integration/test_distinct_run_comparison.py`：四项应用/公开适配器回归覆盖重复ID、同run多snapshot、第二run缺失、重复来源与有效第二run同时存在。

无新公共字段、CLI/SDK/API、数据库或服务；不改指标、单位、corner、stage、研究算法、评分或采用政策。修复的是运行身份，不是新造统计评测底座。

## 门禁与实际验证

修复前四项新增用例均失败。修复后 **196 Query全回归、712根回归** 通过；lint全部通过、181文件格式通过、Pyright0错/警告，3项依赖约束保持，pip check通过。门禁使用失败即停止并逐项查看输出。

独立wheel SHA `302f19a7d2e318d9a6a66d574acde93ca7a45abe22411abcca33b7730f5f55cc`，三份产品源文件/wheel/安装文件字节相同。真实只读复测：

1. 同一GCD run重复两次：旧包ANSWERED、差值0；新包NEEDS_MORE_DATA，仅一个实际run，不再返回比较差值。
2. 两个不同、同条件的GCD WNS run仍ANSWERED。
3. 既有GCD/ASAP7功耗比较仍为0.00071564863902W对0.001373553765W，原值保持。

26用户保护文件保持；新增EDA/模型0，旧运行环境不动。这里的不同measurement run仍不自动证明“独立优化两次”；既有重复实验ledger还要求不同原生optimization run及相同方法身份，未放宽这些规则。

## 发布与接续

Query提交 `54a08be` 已发布原隔离模块分支，根更新该gitlink/manifest及文档。八份未来配置显式绑定本次已验证包，原专业templates保持，不自动放行长搜索。证据在 `var/business/a53-query-distinct-run-comparison-20261025/`：actual-before、before-command、前后测试、完整门禁日志、installed-verification、future-bindings。

实际路径仍是公共EF/DF/DI→Query事实与运行身份→Codex判断。若要改变跨run比较如何计算证据数，改answerability的比较分支；要改变数值差计算选用哪个run，改service，不能让引用条数替代实验次数。

A52已证“旧已布线产物事后重建PDN”不可当有效Ariane/ASAP7修复；必须在正确前置配置下完成物理资格。Ibex/Nangate45完整证明、新500ps完整Flow搜索、八组双次合格结果仍未完成。后续回到逐功能当前阻断总表与这些实际业务缺口，不用长搜索调试环境。
