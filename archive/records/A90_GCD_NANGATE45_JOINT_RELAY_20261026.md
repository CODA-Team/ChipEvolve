# A90：GCD／Nangate45 原生联合策略与物理接续

根基线 `980efef`，Goal `0ca32cc`，ECO `de19cc4`。**已有500 ps基线 → Goal原联合配方 → Query发现GRT时序债 → 显式ORFS物理修复 → 最终验证与本轮采用，实际通过。** 没有恢复Teacher/Student长搜索，也没有新增产品代码、接口、服务或数据库。老板业务验收独立。

## 老板能看到的结果

| 同条件最终指标 | A45基线 | A90最终采用 | 变化 |
|---|---:|---:|---:|
| 功耗（mW） | 2.2321124561 | 1.9228593446 | −13.8547% |
| 单元面积（µm²） | 675.64 | 594.51 | −12.0079% |
| core／die面积（µm²） | 1076.77／1278.42 | 1076.77／1278.42 | 保持 |
| setup WS（ps） | +40.0912 | +11.0525 | 余量减少29.0387 ps，仍闭合 |
| hold WS（ps） | +110.517 | +110.445 | 仍闭合 |
| setup／hold TNS（ns） | 0／0 | 0／0 | 保持闭合 |
| slew／cap／fanout违反 | 0／0／0 | 0／0／0 | 通过 |
| 布局违反／DRC | 0／0 | 0／0 | 通过 |

最终18个顶层输出的完整PDR证明通过；独立DRT／RCX后七项PPA及19个原始字段完全相同，网表与已证明候选同SHA。最终三个DF视图及Query的setup WS、hold WS、setup TNS、功耗均核对原值和原件SHA。本轮通过原有selection入口登记采用，目标、时钟、面积/功耗上限及电气/DRC要求均未放宽。

这是一条**原生固定策略的有界验证分支**，不是新Student源码演化或完整Flow搜索；独立重放也不是第二次独立优化。它证明该条件下专业能力与物理接续可以交付真实功耗/面积收益，不能写成四专业连续接力或自主调度优于固定顺序。

## 具体诊断与接力过程

原输入复用A45已经完成的500 ps ORFS来源，不重做综合、布局或原基线验证。EF登记的六份源产物、19项DF指标、原目标与条件先核对。原Goal控制器从当前正式模块冻结，A72已验证的701份C++源码与二进制逐SHA保持，不重复编译。

使用原 `Contest2026OpenROADEvaluator._write_tcl` 生成的未修改Tcl：`power_then_timing / legacy_setup`，原 `early_forced_reclaim` 阶段、80% proportion、`max_moves=0` 原生默认动作容量，TNS目标0。专业中间态允许原有60 ns时序债，**最终采用约束仍是原来的零TNS与零电气/DRC**。没有自造0.9倍功耗目标。

| 原生阶段 | 功耗（mW） | 单元面积（µm²） | setup WS（ps） | setup TNS（ns） |
|---|---:|---:|---:|---:|
| pre_repair | 2.2347383201 | 675.6399884 | +38.540922 | 0 |
| post_repair_design | 2.2347383201 | 675.6399884 | +38.540922 | 0 |
| post_repair_power | 1.8982125912 | 582.0079974 | −195.025723 | −4.621239078 |
| post_repair_timing | 1.9268227043 | 593.9779779 | +7.875867 | 0 |
| post_placement | 1.9190119347 | 593.9779779 | +9.333923 | 0 |
| post_route（实际GRT估计） | 1.9825901836 | 593.9779779 | −2.311595 | −0.006798895 |
| ORFS物理接续后最终RCX | 1.9228593446 | 594.51 | +11.052500 | 0 |

前六行是原Goal理想时钟及placement/GRT寄生估计，最后一行才是共同最终条件下的测量，不能跨测量协议把差值说成某条指令的独立收益。原生功耗表头明确为Watts，按该表解析，未被旁边 `report_units` 的1nW显示误导；原检查点字段名含abs，实际有符号WS/TNS保持。

功耗阶段减小单元却引入时序债，原Goal时序阶段将其收回；GRT后仍有setup WS −2.311595 ps、TNS −0.006798895 ns。Codex通过DF／DI／Query确认该负债，保留原Goal负节点，选择现有显式ORFS物理入口恢复路由环境，运行GRT修复、DRT和RCX。最终重新测量后满足原全部约束。该过程没有将负节点原地改成通过，也没有将ORFS修复称为ECO Agent。

```mermaid
flowchart LR
  B[已有500ps基线] --> G[Goal原功耗与时序配方]
  G --> F[DF / DI / Query：GRT仍有时序债]
  F --> C[Codex选择物理接续]
  C --> P[EF执行ORFS修复与DRT / RCX]
  P --> V[完整功能证明与独立物理重放]
  V --> A[Codex登记采用]
```

## 实际阻断与修复范围

只修改 `var/business/a90-gcd-500ps-native-joint-20261026/` 内的本轮运行脚本和证据；产品源码不变。

- 准备核验最初找错metrics所有者：实际raw_flow_metadata由ORFS导出run登记，不属于common测量包的output_files。改查真正生产者与登记SHA，原失败日志保留，没有重跑EDA。
- Tcl生成最初从脚本路径启动，错误消费旧安装Goal；改在冻结控制器cwd使用 `runpy`，断言实际生成器位于该副本。未加入跨源码PYTHONPATH或sys.path补丁，实际EF执行的Tcl由新冻结控制器生成且SHA固定。
- 六份ODB面积只读诊断最初在同一OpenROAD进程连续read_db，第二次触发ORD-0047。改为每份ODB启动独立子进程，全部仍在同一EF任务内顺序执行；原失败run及日志保留，未重复原优化。

## code-check与证据

七份顶层运行脚本lint、格式、类型检查通过；根驱动按client环境检查，原生Tcl生成器按Goal环境和项目cwd检查。初次递归扫描误纳入未改的冻结专业源码与生成产物，得到182项历史风格诊断；没有修改冻结源码来消除它们，最终静态门禁只针对本轮七份脚本。首轮收尾脚本两处格式差异已纠正。

产品Python与基线哈希一致，复用A82同源754项根回归及A89同源479项Goal／71子项回归。本轮没有新增产品逻辑，不新增镜像实现的单元测试；真实原生运行、完整证明、独立物理重放和数据/Query核验构成本轮业务验证。

25个成功EF证据包登记SHA、96份capture文件SHA核对通过；失败面积诊断保持failed。六阶段事实经既有adapter进入DF，最终与重放各有opendb/orfs/opensta三视图。26份用户保护文件、generic_agent.py、DF/DI在途工作保持；收尾五种活动EF状态均为空。公共边界保持，EDA全部由EF执行，Query经已安装SDK访问DF，不新增框架。

| 关键节点 | EF run |
|---|---|
| 原同条件基线测量 | `run-9b90f0c354b948a9b92dec51aec3a7cd` |
| 原Goal固定配方 | `run-c5e11bb8259f40e1b9f789900468c364` |
| 原ORFS GRT修复 | `run-7bf748a1b1bb4f0cb798c9d281fc6a98` |
| 最终共同测量 | `run-83c126f4d78241fb86165d784daad435` |
| 全18输出PDR证明 | `run-ccf432cc56004e3ba534752c56faa1c5` |
| 独立重放测量 | `run-82e44e6c592e4bc998ef3e45795b4443` |

完整原始指标、各阶段父子/源码/二进制身份、Query原件和采用决定见该var目录的 `native-stage-verification.json`、`handoff-decision.json`、`comparison.json`、`validation-result.json`、`terminal-inspection.json`、`adoption.json`、`code-check.json`、`continuation.json`。共同condition为 `c001ce1866989fd53f7f39103f05ce814a0af0d601451719d10558b1592820dd`，objective为 `4b20adbabe288fc38382f9bab945cff03c8dd316e316275db440b5124b81285e`。

下一项仍按具体功能阻断处理。Ariane/Nangate45最终电气、Ariane/ASAP7 setup、八组各两次独立合格优化及DF大对象实际写入延迟尚未关闭；长搜索继续暂停。本轮已经关闭GCD/Nangate45固定联合策略接续的最终资格缺口，未声称完整专业搜索和八组双次完成。
