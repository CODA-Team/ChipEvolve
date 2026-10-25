# A64：明确物理接力并恢复检查点丢失的原生路由上下文

本轮于10月25日开始、26日零点后收口，接续 A63，基线根 `a72621f`、Query `f31773d`。范围为一个已保存 Goal 布局检查点到原生 ORFS GRT 收尾的定点验证，不启动长专业搜索、模型调用或正式八组实验。产品 Python、公共接口、服务、专业源码与历史产物不变。

## 发现的实际阻断

Goal 原生评价通过 DEF/Verilog 重建设计；OpenDB 的部分路由设置没有随之保留。其 `post_placement.odb` 写出发生在专业自身设置路由层之前。原生 ORFS GRT 则消费原流程早先已初始化过的 `4_cts.odb`，不会为每个外来 ODB 自动重做 floorplan 中的路由初始化。把前者直接别名为后者，会遗漏状态。

实际 EF 探针 `run-9e8404cc49c849219772a1f2448647e0` 分别读四种状态，结果如下。表中的负数是数据库内部未设置/默认哨兵，不是实际金属层编号。

| 来源 | signal min/max | clock min/max | M2–M7 adjustment |
|---|---|---|---|
| 原 ORFS final ODB | 2 / 7 | 4 / 7 | 各 0.25 |
| Goal post_placement ODB | 2 / −1 | −1 / −2 | 各 0 |
| Goal post_route ODB | 2 / 7 | 2 / 7 | 各 0 |
| Goal placement + 原 ORFS initializer | 2 / 7 | 4 / 7 | 各 0.25 |

原生环境从实际镜像和 Makefile 读取：`MIN_ROUTING_LAYER=M2`、`MAX_ROUTING_LAYER=M7`、`MIN_CLK_ROUTING_LAYER=M4`、`ROUTING_LAYER_ADJUSTMENT=0.25`。使用实际 `FASTROUTE_TCL`，SHA256 `0513fb0efd632b4bc3c16882b09d64ce227e48f4bc71486f4d05aec62fe7b0e1`；不换专业 RC 表，也不更改原生源码。

此前 r3 因缺这些设置实际把信号布到 M8/M9/Pad，观察到问题后通过公共 EF 明确取消，终态 `cancelled`，不能将其当有效物理优化。取消的日志和原因由后续纯证据任务 `run-1f886479771246c4af5ff684653ff7a3` 托管，分析任务成功不改变原任务取消事实。

## 修复方式与状态保留

新增独立恢复节点，仅对 Goal 已登记的 `post_placement.odb` 应用原平台 initializer，写出新的 `routing-admitted.odb`。原检查点不改。再把新 ODB 与父序列化 SDC 作为原生 `make do-grt` 的输入；`4_cts.odb` 是阶段输入名称，不能据此声称重新执行了 CTS。

恢复前后同一工具导出校验：210,746 个实例；实例名/单元类型/位置/方向/放置状态 SHA 均为 `daa522fba24e8043f0eaa3675b87b75f20c0105b827dff46814dbe39e5301d9f`，网表 SHA 均为 `2f9dd66fa600f0e856b2d506bbe46c71eca9fc9be9cf92711475bfcd2856c058`。这是实例与逻辑连接不变的验证，不冒充全 ODB 几何逐字段等价。

r4 的 EF 预检 `run-8e4d29c3976048f59c90ea77d8c9bd6b` 成功，核对两级 make dry-run、未运行上游综合/布局/CTS，也没有 DRT/RCX；同时实际读回恢复后的 ODB 完成上述不变量核对。

物理收尾是显式的新接力节点：原 `repair_design_helper`、合法化/增量 GRT、原 `repair_timing_helper`（setup/hold）、后续原生收尾与测量。不往 `qualify` 纯测量路径暗加修复。工具使用共同镜像内原 OpenROAD，显式 8 线程与 EF 8 CPU 对齐，16 GiB、1800 秒；保持原 `TNS_END_PERCENT=100`、setup/hold margin=0、900 ps 目标与原生循环，未缩减动作算法。

输入浮点时钟为 0.8999999964 ns，读回一致性使用 1 fs 数值容差；这不是把 900 ps 业务约束放宽。hook 不更改显示单位，观测值通过 OpenSTA 的单位转换换算为 ns，原生 margin 单位保持。

## 本次实际结果

实际原生修复 `run-672abfa5a3d34f929c284b4433db0bb2` 成功，原命令退出 0。工具墙钟 1070.59 秒，EF 全任务约1084.57秒、CPU4091.48秒、峰值约4.23GiB/10进程。完整阶段未触发资源或时间上限；这些是本次诊断成本，不是公平延迟对照。

| 最终 GRT 读数 | 数值 | 判断 |
|---|---:|---|
| setup WS | −280.683754 ps | 未闭合 |
| setup TNS | −92.960533493 ns | 未闭合 |
| hold WS | +2.495976 ps | 此阶段通过 |
| hold TNS | 0 ns | 此阶段通过 |
| max slew / capacitance / fanout violations | 0 / 0 / 0 | 此阶段通过 |
| signal / clock routing bounds | M2–M7 / M4–M7 | 与原平台一致 |
| 最终 SDC clock | 900 ps，propagated | 原约束保持 |

原 repair_design 在3条网上插入6个buffer；setup修复实际记录1478次实例调整（133次upsize、1345次VT）、83个buffer插入、623次引脚交换及1次克隆；hold修复插入3个buffer，现场hold TNS清零。末尾原WNS阶段再记录311次VT调整，最终hold仍为0，setup仍有2907个违反端点。原流程合法化/增量路由与最终check_placement实际完成，未报告放置失败。

原 `write_ref_sdc.tcl` 临时写出 `updated_clks.sdc` 后恢复活动时钟；post hook实测仍为0.8999999964ns，最终 `5_1_grt.sdc` 明确 `-period 900.0000`，不能把日志里的临时1121.650ps当成本次放宽了目标。

进一步读取原生最终报告：最差setup从miss-handler状态寄存器到输出 `axi_req_o[143]`，arrival约1000.68ps，900ps时钟减原180ps输出延迟得到required720ps，剩余−280.68ps。另有寄存器间setup路径约−114.20ps。不能只靠更改输出约束“修好”它，也不能断言都是I/O问题；下一步应针对这些实际长路径选择原专业已有策略或更早物理阶段，而不是继续原样重跑VT。

这些报告由纯证据任务 `run-687a0c58c4ed452d80673f005a598b57` 托管，没有再跑EDA。原A62/A63与本次的路由/RC协议不同，不把−451.84、−172.78与−92.96ns直接拼成同条件因果改善率。本轮不做最终DRT/RCX、完整功能证明或采用，不新增功耗/面积收益宣称。

```mermaid
flowchart LR
  G[Goal 原生布局输出] --> I[EF 应用原平台路由初始化]
  I --> N[EF 原生 ORFS GRT 收尾]
  N --> F[EF 事实导出]
  F --> D[DF / DI / Query]
  D --> C[Codex 判断剩余 setup 问题]
```

事实导出 `run-2e5b702e3a0d4495a9c6c01367903be5` 经既有 ORFS adapter→DF→DI；快照 `a64-run-672abfa5a3d34f929c284b4433db0bb2-native-physical-repair` 明确global_route与估算RC角色。八项原始字段逐值一致；独立安装的A63 Query对setup TNS、hold TNS分别返回−92.96053349316935ns、0ns，引用metadata原字节和SHA核验通过。没有把旧父项的PPA复制到新状态。

## code-check 与真实保留范围

- 本轮31项针对回归通过，覆盖交接契约、原生阶段事实、Goal路由控制和双PDK绑定；八份最终host脚本lint、format及Pyright通过。
- code-check核对5份实际EF evidence bundle，共64个输出文件，当前字节均与登记SHA一致；恢复前后实例与网表不变量、实际路由表范围、原生退出码和时钟/参数均通过。
- 26个用户保护文件、冻结输入/目标/库、root业务Python及既有generic_agent/DF/DI修改保持。产品源码与A63相同，复用同源712根回归/211Query回归，不冒充本轮全量重跑。
- r1私有make dry-run断言、r2私有浮点时钟检查、首个探针生成脚本换行错误均保留失败记录；r3因真实上下文失配取消。只有新独立r4使用恢复后的输入；未改已运行的脚本/历史记录后再以同一任务身份重放。
- EF/DF服务与容量不动，未新增公共API、数据库、wheel或专业模型调用。收口时公开EF五种活动状态均为0；最终采用状态不变。

本轮发布只含本报告、A54阻断表、TASKS、ARCHITECTURE、STATUS。实际脚本/配置/原生ODB/网表/日志/JSON和证据留在 `var/business/a64-native-physical-handoff-20261025/`；关键入口为 `code-check.json`、`facts-receipt.json`、`routing-context-observations.json`、`preflight-r4.json`、`actual-execution-r4.json`。修改下一次物理收尾方案，应改明确的接力配置与输入来源；不能在测量路径中暗加修复。

## 下一步

本次得到的是明确接点的验证与原生产物；当前没有新的通用公开物理修复接口，不把私有验证脚本说成所有专业已自动使用的新功能。后续将已验证的原生收尾接点收口到现有业务入口，明确输入阶段、原路由设置、父节点和事实记录；不新增服务/数据库或通用 Agent harness。

Ariane 的最终 DRT/RCX、全部业务时序/电气/供电/功能资格仍需独立完成。Ibex/Nangate45 的完整证明、GCD/Nangate45 500 ps 协作以及八组两次合格重复保持未完成；长搜索未放行。另对 Query 旧 simple-ask 的 hold 路径语义继续核查，不把 A63 标量修复扩大成全部路径调查已完成。
