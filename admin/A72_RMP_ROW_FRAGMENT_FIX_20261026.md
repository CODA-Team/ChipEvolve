# A72：修复 RMP 宏切割行选取，真实候选几何代价显著降低

工程验证及 code-check 通过，待老板业务验收。本轮解决一个具体几何缺陷，没有新增可采用 PPA，没有恢复正式长搜索。

## 业务效果

原 RMP 放置函数仅按纵向距离选择 row，宏单元将同一高度的行切成多个片段时，替换单元会被夹到远处。本轮改为按完整横纵投影距离选择能容纳单元的片段；保留原网格对齐、方向、同距离顺序及映射、STA、评分、回滚规则。

实际同条件重构中，四种内部映射的局部 HPWL 较修复前下降 **88.00%–91.88%**，setup 时序恶化显著减轻。但候选仍差于原设计，四种均被原规则拒绝，原采用结果保持。

这是修复错误物理代价的效果，**不是功耗优化百分比，也不是最终布线 PPA 收益**。本轮不再原样重复这个单区域策略来追求一个正结果。

## 源码范围与跨设计适用性

新私有原生源码相对 A68 只修改 `src/cut/src/blif.cpp::snapToPlacementRow`。判断依据是实际 row 区间和单元尺寸，没有设计名称、PDK 名称或目标数值特判。连续完整行保持原选择，宏切割片段改为最近可容纳片段，过窄片段被排除。

Goal 模块提供可重放补丁、原函数快照、C++夹具、测试和说明；没有修改平台公共接口、专业默认策略或其他模块。A71 的快速 SLVT 映射库只作为本轮显式短验证条件，不被设成所有功耗实验的默认策略。

## 三层验证

1. **原函数回归**：直接编译原函数和补丁后的函数，复现五类错误，验证14种修复后场景，2测试/19子项通过；连续行、负坐标、PAD跳过、空输入、网格与方向继承保持。
2. **真实输入的函数核对**：原 EF 记录的11738个 row 片段、36个原合法实例输入同一 C++函数夹具。旧函数移动29个、累计4342788 DBU，新函数移动0个。EF `run-4d911b5515444f3383950cdbc3247e88` 的10份捕获文件均核验。这里使用行API测试替身和真实几何输入，是原位置投影核对，不是新候选实例的位移统计或 PPA。
3. **完整新二进制实测**：通过 EF 完成七个原生编译/归档/链接任务；cut静态库的 `blif.cpp.o` 唯一且与本轮新对象字节一致，区别于旧对象。新二进制 SHA `275790d63baa00404494f8fd7b707e19d463d6ac7ae65edeef863aec1d0e3da6`，AST160文件/1989符号，源码清单与图哈希核对通过。旧A68源码、二进制保持原字节。

## 原生同条件候选

EF `run-9db98771e728467b9b859d60d06d4068`，工具175.68秒。与A71使用相同 ODB、全部STA库、快速映射库、FF/900ps/I/O180ps、placement estimate、8线程、一个逻辑区域和四种内部ABC映射；仅几何函数改变。起始八项标量完全相同，五份输入/输出 BLIF 的逻辑内容相同。

原区域36单元、HPWL808137 DBU；原设计setup WS−0.436833415ns、TNS−230.784699217ns。下表是未采用的临时候选，HPWL为局部估算，WS/TNS为该试评设计的全局setup值。

| mode | 候选单元 | 修复前HPWL | 修复后HPWL | 降幅 | 修复前WS ns | 修复后WS ns | 修复前TNS ns | 修复后TNS ns |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 95 | 16708410 | 2005290 | 88.00% | -3.455298 | -0.827260 | -423.719700 | -254.920960 |
| 1 | 77 | 16516143 | 1341144 | 91.88% | -4.274280 | -0.791266 | -471.473750 | -250.982450 |
| 2 | 79 | 16559748 | 1418148 | 91.44% | -3.547699 | -0.673210 | -436.534860 | -241.274850 |
| 3 | 95 | 17223408 | 1658475 | 90.37% | -3.844446 | -0.691444 | -447.982050 | -245.952630 |

四种候选仍增加单元/面积，setup较起点更差；原生全部拒绝。拒绝后210746实例/191607网络的型号、位置、方向、放置状态、引脚/网络连接含供电同值；setup/hold WS/TNS、面积、电气计数恢复原值。该语义核对不扩展为逐形状布线几何证明。没有进行最终DRT/RCX或新网表采用。

## 数据、环境和代码检查

两个前后阶段通过现有 EF→DF→DI→安装 Query 登记，setup/hold四次精确查询及原件字节/SHA一致。原生日志和映射原件保留每次试评及拒绝原因。没有新服务、公共API、评测库或通用harness。

模块回归476项/71子项通过，唯一的本机HTTP测试因本次命令未绕过代理返回502；显式本地NO_PROXY后原失败项单独复验1通过，合计477项已核对。新格式后的原函数19子项再次通过；未为代理问题修改产品。根业务Python与733项已有验证同源，直接复用，不重复整场。

产品测试Python及九份私有脚本的lint/format/type、C++夹具格式、逐文件差异和边界检查通过。原函数快照仅清理末尾分隔空行，补丁的空白context行采用Git支持的无空格形式。已执行补丁按原SHA另存；发布补丁在原完整C++文件上应用后与已构建源逐字节一致，19子项再次通过，没有重复EDA。26份用户在途文件、DF/DI WIP和历史来源保持；结束时EF五种活动状态均零。早期测试命令的目录错误、未存在的integration路径和上述代理失败日志保留，不计为产品修复或新EDA试次。

八份新待用绑定位于 `var/business/a72-rmp-row-fragment-fix-20261026/configs/`，只换已验证的source_seed和私有state路径，保留campaign、目标、PDK/时钟/PDN/FakeRAM、资源和Query。使用新源码开展搜索时须测真实新baseline；历史固化重放保持原源码。当前 `long_search_ready=false`，没有启动Teacher/Student搜索。

## 改动文件职责与恢复入口

| 文件 | 职责 |
|---|---|
| goalevolve/toolchain/patches/fix-rmp-row-fragment-projection.patch | 原生选行函数修复，可应用于新私有源码 |
| goalevolve/tests/fixtures/rmp_original_row_projection.cc | 原函数精确快照 |
| goalevolve/tests/fixtures/rmp_row_projection_harness.cc | 最小行API夹具，编译真实函数 |
| goalevolve/tests/unit/test_rmp_row_fragment_patch.py | 原错误与修复场景回归 |
| goalevolve/toolchain/patches/README.md | 补丁基线、应用与验证范围 |
| SOURCE_MANIFEST.json、goalevolve gitlink | 固定已发布模块版本，其他模块记录保持 |
| 本报告、admin/A54_CURRENT_BLOCKER_MAP_20261025.md、admin/STATUS.md、TASKS.md、ARCHITECTURE.md | 结论、当前阻断、恢复点、任务与现有边界记录 |

恢复资料 `var/business/a72-rmp-row-fragment-fix-20261026/`：`source-repair.json`、`built-binary.json`、`cut-archive-verification.json`、`AST-repair-receipt.json`、`real-projection-verification.json`、`geometry-before-after.json`、`analysis.json`、`prepared-bindings.json`、`code-check.json`。原生输入→EF新二进制→原候选/回滚→DF/DI/Query→Codex判断的链路保持；调整行为应改该cut补丁或显式专业策略，不改EF/DF来绕过坏候选。

## 下一步与未完成范围

转查其余接点和交付准备，优先核查Ariane/Nangate45保存GRT后继经公共入口交接的条件、来源和产物。Ariane/ASAP7仍缺足够的专业收益及最终资格；当前单区域映射的负结果保留，不把调大时钟、换RC或重复同策略当修复。

Ibex/Nangate45完整证明、Ariane最终DRT/RCX/PPA/证明、GCD/Nangate45批准500ps协作及八组双次合格结果仍未完成。正式长搜索保持暂停，总目标仍进行中。
