# A51：恢复未指定阶段的两次运行比较

接续根 `8ce4d2b`、Query `5adc9e5`。本切片修现有比较功能，未新增EDA、模型、公共接口、服务或数据库。

## 具体阻断

对A45与A47两个同条件GCD完整结果执行原CLI `Compare WNS --compare-runs ...`，返回NEEDS_MORE_DATA、证据0。两项指标实际均存在；ComparisonPolicy把未指定stage的None当成必须匹配的阶段，过滤了真实finish指标。另有同路径错误：首条指标若缺单位/corner，仍被用作比较条件，导致后面的完整指标被排除。

唯一产品改动是 `query-agent/src/query_agent/application/context/comparison.py`：先限定设计/指标，未指定阶段且存在单一实际阶段时按该阶段比较；多个完整阶段时使用原MissingDataError要求指定stage，不选任意阶段；使用完整指标作为单位/corner参照，缺项先按真实不足原因排除。明确stage的筛选、原单位/corner一致要求、数值及专业算法保持。

`tests/unit/test_comparison_scope.py`覆盖上述六种边界：单阶段及别名、多阶段歧义、缺项首条在显式/隐式阶段、其他设计不干扰、普通两run真实应用管线。修复前6例失败，修复后 **192 Query全回归、712根回归** 通过；全项目Ruff/format/Pyright、3项依赖约束、pip check及差异审查通过。

## 真实安装包复测

独立wheel SHA：`7cf9d33eb51610242289dbf89d85f7d567c14df091e7c19bc5e8da5bfee494ba`。产品源码、wheel和安装文件字节一致，原环境未热切。

1. A45→A47同条件GCD WNS比较现在ANSWERED，返回两条原run证据及同值0；原先零证据。
2. 错误显式placement阶段仍不足且无证据，不把finish当placement。
3. GCD/ASAP7原基准与G02的POWER_TOTAL比较，旧A50包仍零证据，新包ANSWERED；实际值分别0.001373553765W与0.00071564863902W，与原result逐值一致。两份result同objective/condition，两个DF原件链接均实际取回并核SHA。

这是恢复既有事实比较，不是新PPA优化收益、重复实验均值或Control Agent优于固定调度的证据。全部读取及验证新增EDA0/模型0，26个用户保护文件保持。实际scope保留原run、snapshot/revision、finish及单位W；未放宽A33身份检查或A50完整性要求。

## 文件、发布及接续

Query产品修复 `fa9a2cc`、测试lint收尾 `23508a2` 已发布原隔离模块分支，根只固定该gitlink/manifest及文档。八份未来配置在本目录configs绑定新解释器，原专业模板/服务/历史环境保持；不等同于放行长搜索。

数据流仍为EF执行归属+DF登记事实→DI→Query原比较策略→Codex判断。若要改阶段如何对齐，改ComparisonPolicy；不改DF存储或专业评分。完整证据在 `var/business/a51-query-comparison-stage-20261025/` 的actual-before、input-identity、前后测试、静态日志、installed-verification、两个power-source与future-bindings。

新500ps完整Flow搜索、Ibex/Nangate45完整证明、Ariane剩余电气违反与最终物理，以及八组双次合格结果仍未完成。当前继续具体阻断审计，长搜索保持暂停。

收尾更正：初次lint因新测试正则未写raw触发RUF043，之前对静态全通过的汇报过早。改为等价raw正则后，最终Ruff全部通过、180文件格式通过、6针对回归通过；原192全回归/712根回归保持有效，产品字节与已验证wheel不变。失败ruff.log保留，最终结果见ruff-final.log/format-final.log/targeted-final.log。后续门禁命令使用失败即停止，不能仅凭测试成功汇报静态通过。
