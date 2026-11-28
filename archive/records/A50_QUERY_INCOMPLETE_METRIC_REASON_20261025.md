# A50：保留指标真正的不足原因

接续根 `a4e6e23`、Query `01abe98`。A48/A49实际出现缺corner却提示原件缺失，导致诊断方向错误；本切片修复该具体错误，不放宽证据完整性规则。

## 文件与数据流

- Query内部 `domain/experiment.py` 的MetricObservation增加可选incomplete_reason，旧调用默认None；它不是新增CLI、SDK或服务端点。
- `adapters/data_foundation/experiments.py` 按原complete条件记录缺注册原件、单位、corner或源状态；原complete表达式不改。
- `application/collection.py` 将原因传到已有Evidence.reason；freshness/comparison保留该原因，不再误换成原件缺失。旧provider没提供原因时保留原回退。
- 对应contract和unit测试覆盖缺项、当前状态及比较拒绝原因。没有新调度器、数据库或补数据的模型循环。

## 验证

修复前3项针对用例复现错误；修复后 **186 Query全回归、712根回归** 通过；全项目lint/format/Pyright与3项import-linter约束通过，pip check通过。最初类型检查报新增list/测试回调缺类型，已只补类型，原日志保留。

独立wheel SHA `942293c7916b75ff3b1921bba82b2fd5733d05f76cc55399db10f4105f25cd4f`；5份产品源文件/wheel/安装字节一致。五项真实只读验证：两份缺corner历史摘要、current缺corner均明确指出corner且保持NEEDS_MORE_DATA；完整摘要仍ANSWERED；错revision仍无证据。26保护文件保持；EDA0/模型0，旧环境和历史记录不动。

原最早摘要后来可继承同run的1ns声明。初次检查仍以为它缺单位而断言失败；源码与实际snapshot/run查询均确认这是既有的run级单位继承规则，并非本次产品回归。最终真实检查按当前声明核对缺corner；缺单位的独立输入由contract用例验证，不假称当前历史快照还缺单位。不重跑或改写EDA。

模块已提交 `5adc9e5` 并发布原隔离模块分支，根固定gitlink/manifest。八份未来配置在本目录configs显式绑定新wheel环境；原专业模板与服务保持。证据：`var/business/a50-query-incomplete-metric-reason-20261025/` 的前后测试/静态日志、installed-verification、原失败检查与r2核验、future-bindings。

## 下一具体阻断

对A45与A47两个同条件、指标齐全的GCD run实际运行 `Compare WNS --compare-runs ...`，未指定stage时返回NEEDS_MORE_DATA且证据0。源码ComparisonPolicy将未指定stage的None当作必须匹配的阶段，排除了两份真实finish指标。下一切片只修阶段选择/可比语义与对应短查询，不运行新EDA或更改指标/专业评分。完整正式实验尚未完成，长搜索保持暂停。
