# Slice 4D 工程验收报告

**工程门禁通过，待老板业务验收。TUI/Web 继续冻结。**

施工基线是首次补同步的干净 Commit
`4c8bccdf40b16bc32ed0118bef7a940a596e3114`；另一条软件 Commit 是
`e99c33b53a689c2c83aa29af349b20b034ab4d21`。独立目录施工，唯一授权目的地：
`CODA-Team/ChipEvolve:refs/heads/engineering/cleanup-b6cfd1d`。
本报告记录提交前证据，实际 Commit/Push/远程相等核验另存本地交付回执，不预填成功。

## G1–G8

| 门禁 | 可核查结果 |
|---|---|
| G1 profile/身份 | 唯一根布局模板 core/profiles/orfs-common-v1.json；冻结实际 SIF/架构/四工具二进制/安装 Toolkits 与插件身份。只支持既有固定布局族，未改模块协议。 |
| G2 资源/容量 | resources-v1.json 统一预算。159 原位置带新路径映射，另补前缀键/字典审查；21 根 Jobs 调用声明任务族。真实空 EF 超额 CPU/内存拒绝，submit/input/chunk-upload 均为 0、Run 前后均空。Code 准备保留 64 GiB 要求并提前拒绝。 |
| G3 架构 | 51 实现 + 8 骨架共 59 Python 文件递归扫描；物理/实现图 remaining_cycle_group=[]、upward_imports=[]、跨模块私有访问 0，保留原五层逻辑约束。 |
| G4 兼容/类型 | 49 旧模块/公开导出/monkeypatch 接点同对象；47 固定别名 + 2 runner。14 CLI 帮助、2 旧 -m 帮助与基线字节相同，无 stderr 过滤。Pyright strict 7/core 20 文件零错误；原负例 7 条、新负例 4 条预期错误。原 15 清单路径与隔离 staging 闭包回归通过。 |
| G5 根回归 | python3 dev.py root check：1347 passed，Ruff/format/pip check 通过。107 原测试文件的测试名、断言、参数化保留，原 1310 用例未删除/skip。 |
| G6 归档/导航 | 377 项（256 records/121 experiments）迁移前后 SHA256 相同；17 在途内容原地保护。四份主文档、包导航、实际目录表更新，workflow 三入口明确。AGENTS/SERVER_AUDIT 仅修归档路径。 |
| G7 默认实测 | 原样 prepare-gcd → baseline → validate → select → resume。18/18 输出证明、独立重放七指标相等、三事实视图、零 DRC、采用成功。Flow on/off 共享输入/配方及七指标相等。临时服务停止，六个本轮实例端口关闭。 |
| G8 范围/补丁 | 九模块 HEAD/status/gitlink 和 manifest 保持；原十仓库 HEAD/分支/status/index/diff/config 及 638 根文件保持。独立补丁、逐路径审查、apply/目标 SHA 核对在交付回执记录；业务待验收。 |

## 新目录与职责

```text
ChipEvolve/
├── chip-evolve.py                  用户业务入口
├── chip_evolve/
│   ├── core/                     19：契约/规则/配置/共享执行原语
│   ├── facts/                     6：事实/配方/证据/源码准备
│   ├── execution/                 5：物理执行/证明/交付
│   ├── workflow/                 21：三个入口及适配/交接/验证/恢复
│   │   ├── cli.py                阅读 1：参数 → 类型请求
│   │   ├── commands.py           阅读 2：预检与实验事务
│   │   └── professional.py       阅读 3：交接准备与专家派发
│   ├── _compat.py                47 个固定同对象别名
│   ├── comparisons.py            最小旧 -m runner
│   └── continuation.py           最小旧 -m runner
├── admin/release/                 安装/服务/专业准备工具
├── tests/support/                 测试及维护的辅助脚本
├── archive/records/               256 项冻结记录
├── archive/experiments/           121 项历史实验
├── agent/                        五个专业 Git 子模块
├── execution-foundation/         执行/调度/产物
├── data-foundation/              设计事实
├── data-interface/               SDK，无新增服务
├── toolkits/                     工具适配/解析/测量
├── docs/release/                  限定公开验收证据
└── var/                          本机环境/实例/运行证据，不入提交
```

49 原模块按 17/6/5/21 搬迁，加 toolchain/resources 两个 core 所有者后为
19/6/5/21。完整映射见 package-move-actual.json；377 原/新路径及 SHA 见
archive/INDEX.csv。admin/FILE_CATALOG.csv 明确当前位置与保护例外。
对已跟踪的保护路径，候选可保留旧公开基线；用户未验收修改不进入交付。

数据流：Codex → CLI 类型请求 → 预检/执行计划 → 交接准备 → 专家 →
EF/Toolkits 物理测量 → DF/SDK 事实 → 比较/独立证明与重放 → 采用或保留。
Query 经 Data Interface 查询 DF。五 Agent 加四基础模块等于九个 Git 子模块；
Codex 和根编排不额外计数。专家原生晋升与平台采用保持分离。

## 零手改实测

复用首次补同步独立环境中正确九 Pin 的已安装 Wheel 和已资格化 SIF。
本片未改模块源码，未谎称再次运行九模块全量检查或证明所有模块脱离自身源码。
全新 EF/DF 实例不复用旧库。SIF SHA256：
`8e6ee7aac233da078364649fa8111dac5de33a3589f5445dcffd96f9d6d8dd39`。
默认容量 8 CPU/24 GiB；GCD ORFS 4 GiB；证明 8 GiB/600 s。

| 回执 | Run ID |
|---|---|
| off 共同测量 | run-5f89ea0356f24fbf9b5b703bc867cdbd |
| off ORFS 物理生产者 | run-5063bc4f17e84b438de8045f7d6ecd1e |
| 独立重放共同测量 | run-b7d27cb1d35e484fa41b74a2d86cbad1 |
| 独立重放物理生产者 | run-f459f347885e442890b1dc9d1e1c43b2 |
| 18 输出证明 | run-e0e4061813924462be598386ae2fafa6 |
| on 共同测量 | run-f92afdbd4a7d40a0a1d213e71c74b0c9 |
| on ORFS 物理生产者 | run-c1e1bd78c9b04037a67d8da1f18e6b36 |

功耗 0.0022321124561 W、单元面积 675.64 um²、setup slack 0.0400912 ns、
TNS 0、Route DRC 0。原始 detailed-route JSON 和空 DRC report 从登记归档
取出核 SHA，未只依赖摘要。保留 STA-0450 warning；flow errors 为 0。不主张收益。

Resume 返回原 Run ID；114 实验 JSON、13 Run、214 产物登记前后完全相同。
Off 下载核验 214 项、79395729 字节；on 另核验 101 项，合计 315 项。
Prepare 后 off 11/on 12 个配置/输入原字节不变。
Flow 绑定仅 on 存在；共同 Liberty/SDC/两 Tcl/原旋钮及评价字段相同。
各实例 objective_id 绑定自身来源引用而不同，未篡改它们；比较真实评价字段、
输入 SHA 和七项指标，不把路径绑定身份差异冒充测量差异。

低容量 CLI 实例（2 CPU/4 GiB）在 inputs/local.json/服务/任务出现前拒绝。
真实超额任务的提交及两类上传计数为零；Code 保留 64 GiB/2048 进程/8 编译线程/
单 LTO worker。Busy 排队、未知空远端及坏身份/预算由负例回归覆盖。

[完整命令摘要](e2e-commands.jsonl)。原始日志、登记产物、恢复快照留本机
var/release/slice4d-20261128/；未整批公开数据库、镜像或运行数据。

## 施工中发现的问题

- 早期扫描漏了 DPL/Goal physical_memory_gib、ECO session_memory_gib 和 EQY
  分区并发默认。最终扩大扫描并收敛到命名目录，保留原 24/24/24/2 数值。
  GCD 可选 ECO 的 8 GiB 独立命名，未误换成通用 24 GiB。
- 测量 8 GiB 默认改归 physical-facts；历史 task-key 的 8 GiB/300 s 阈值保留
  并注释，保护旧任务身份，不作为新默认。
- 初步 baseline/validate 成功后发现上述审计缺口，停止初步实例，以最终 policy
  在全新 off-final 空实例重跑完整闭环；不手修旧配置或覆写历史回执。
- 辅助脚本最初将实例各自 objective_id 也强制相等；保留失败日志后改按审定合同
  核真实评价字段和输入字节，未改产品。旧/新路径、环境调用等辅助错误只计最终成功输出。

## 继承缺口和验收边界

4C G6 的完整真实 Code 演化追加交付、Flow 成功/失败 collector 与部分 Goal
历史恢复材料继续待资格化。本片 GCD/静态测试/目录迁移不关闭这些缺口。
未发起新 C++ 长构建、模型搜索、远端 CI、main 合并或部署。未改九模块/Pin/manifest。
TUI/Web 继续冻结。工程、Git 交付和老板业务验收是三个独立状态。

## 公开证据

- [递归物理/实现图](architecture-after.json)
- [7/20 类型检查及 7+4 负例](typecheck-summary.json)
- [全量根日志](root-check.log)
- [默认运行摘要](runtime-summary.json) · [Flow 开关](flow-switch.json)
- [真实容量拒绝](capacity-negative.json) · [低容量准备拒绝](low-capacity.json)
- [资源/路径审计](configuration-audit.json) · [逐位置归属](resource-site-resolution.csv)
- [原文件/模块/断言保护](scope-integrity.json)
