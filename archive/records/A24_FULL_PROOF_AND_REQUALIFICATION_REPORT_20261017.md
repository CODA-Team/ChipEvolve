# A24：完整来源证明、两设计功能复核与真实搜索启动

这是正式实验前的工程检查点。JPEG完整Flow已启动，两个Code的JPEG健康原生轮次及完整接力、预算校准、A25冻结和A26–A28仍未完成。本文没有新增PPA采用或协同优越性声明。

## 实际交付

| 检查 | 结果与证据 |
|---|---|
| JPEG原参考与完整旋钮来源 | 全27输出、7082分区PDR通过，EF `run-d74de735331e4b6c9ddb64a79d392bc2`成功；控制器5767.19秒，原生工具5699秒，全部输入hash保持 |
| 单次JPEG完整Flow | 同一个`a24-jpeg-flow-r4`实际启动，原2轮×50候选、完整域/原评分/72000秒保持；首批50任务被EF接收并实际消费，非只写计划 |
| AES现采用结果功能复核 | 新固定Liberty PDR证明全129输出/695分区，EF `run-e6c149ab8a154fe9a8318273a1d1042a`；原结果、旧验证、网表及独立物理重放保持，七PPA和SDK身份核对通过 |
| GCD现采用结果功能复核 | 原18个独立输出分区失败保留；同模型整体证明全18输出通过。通用入口新增显式整体模式后，新标准回执 `run-957bdb20bc4f4604a841a89a91ed41b4`全18输出/1完整分区通过，SDK/旧字节核对通过 |
| JPEG参考STA上下文 | 新补充snapshot提供post_route/FF/秒，15条原采样路径的实际事实完全相同，原快照和结果不改；EF `run-90a6ccfb85df4c2291b25529041d4b7f`成功 |

JPEG权威接受记录：`var/business/a24-jpeg-pilot-20261016/full-source-proof-acceptance.json`，完整证书SHA为`d7ffe895795dfc40bc9f928517a59e060f4e342c76834f2c49d18287efae15e0`。它证明固定模型下数字等价，不能代替物理签核、调参收益或公平成本实验。

两设计新复核位置：

- AES：`runtime/experiments/aes/a24-aes-functional-requalification-pdr-r1/requalification.json`。
- GCD：`runtime/experiments/gcd/a24-gcd-functional-requalification-pdr-whole-r2/requalification.json`。
- 参考STA：`runtime/experiments/jpeg/a25-canonical-timing-context/live-acceptance.json`。

以上相对路径均位于`var/business/a24-jpeg-pilot-20261016/`。补充参考snapshot为`local-run-e1851061d4094a9189502aa21c245818-sta-context-a25-r1`，可通过既有SDK显式读取；旧snapshot缺失的上下文字段不回填。

## GCD失败为什么不能直接当成设计不等价

原ORFS网表有34个FF，所选结果有35个，寄存器实例命名及状态编码不同，没有同名FF匹配点。原18个输出分区的反例已经被SMT复核，但分区输入含其他输出，例如`req_rdy`分区把若干`resp_msg`位和`resp_val`当自由输入。这是抽象分区反例，不足以证明整个实际电路能到达同一反例。

保留该次失败`run-e8bf38ca43cd4caf9e97b9776b46d553`后，只增加原生`[partition *] / merge *`，库、两份网表、全部端口、PDR/xprop及固定Z3不变。真实整体诊断`run-953931bad3c641e6a4d9d406a293b613`在约6秒原生求解后通过全部18输出；其唯一分区的输入只有真实顶层输入，输出之间不再互作自由切点。

因此，这次GCD分区反例不是全设计不等价证据。它也不证明所有旧Yosys证明都正确，或推翻之前旧EQY/SAT误通过负例的发现；这些是不同验证路线和不同命题。

## 通用入口与资格

`chip_evolve/eqy.py`新增私有`validation.equivalence_merge_partitions`，缺省false；显式启用时在现有配置中加入原生整体合并规则，并在新回执披露`partition_mode=whole_design`。没有GCD网名条件，不改变设计、库逻辑、端口、策略或验收义务；全输出及每个实际分区PASS仍必需。旧默认配置的其余字节保持，JPEG/AES现有证明与活跃Flow配置没有更换。

新模式由同一生成器的真实固定ASAP7双反馈FF正反例核验：正确电路PASS，故意改错电路FAIL，负例状态确认为FAIL且有SMT反例，而非工具启动错误。EF `run-462738d64f434b75ae4e0e01aeb4edfb`，记录`runtime/experiments/gcd/a24-eqy-whole-model-controls/independent-acceptance.json`。随后标准`verify_outputs`入口重新证明GCD，得到完整新证书及旧物理/SDK证据组合；没有重复物理优化或改写旧验证。

采用显式配置而不全局强制整体证明，是因为大型JPEG保留已证明的状态切点有重要分解价值；状态编码不同的小设计则可能需要整体义务。正式每设计的验证配置仍须在A25冻结，对同设计所有方法一致，不依据优化输赢改变证明模型。

规则依据：[YosysHQ EQY配置参考](https://yosyshq.readthedocs.io/projects/eqy/en/latest/config.html)中的原生分区合并与状态重编码说明。此次只使用其合并功能，没有加入重编码假设或删去输出。

## 文件与门禁

- `chip_evolve/eqy.py`：原验证入口的显式整体配置与模式披露。
- `admin/test_eqy_whole_design.py`：三项修复前失败、修复后通过的检查，覆盖原模型/端口/策略保留、原缺省及配置传递/回执。
- 本报告、`TASKS.md`、`ARCHITECTURE.md`及`SOURCE_MANIFEST.json`：更新源码和实际工程状态；九专业/底座模块gitlink不再改动。

31项相关检查、根416项回归及产品/新增文件Ruff、格式、Pyright通过；原历史扩展测试的风格问题不另作已通过声明。原参考、所选PPA、旧失败/证明、用户26份未提交文件保持。数据补充只增加新快照，没有建立新服务或评测底座。

当前解除的是完整来源证明与当前GCD/AES功能复核缺口。A24仍需完成JPEG完整调参、适用专业健康轮次、实际接力、最终合法性/独立物理重放及预算校准；不得把本检查点改写成这些已完成。
