# flow-agent 服务器验证与使用说明

验证日期：2026-10-08（Asia/Shanghai）。上游：`yfz2024/A2-ORFO`，
初始提交：`190ff80ac903d5874e4e70eb8394af0246fceb88`。本地目录：
`/home/wjyuan/flow-agent`。使用浅克隆保留当前 main；本地修复尚未提交或推送。

## 权限与环境

这是私有仓库。服务器现有 GitHub 登录账号 `yuan-fd` 拥有 pull、push、triage
权限，不拥有 admin/maintain 权限。没有新增账号授权，也没有向 GitHub 写入内容。
默认 `127.0.0.1:17898` 代理连接不稳定，直连 DNS 失败；使用现有
`127.0.0.1:7890` HTTP 代理完成下载，并将该代理设置为此克隆的本地 Git 配置。
没有修改服务器的全局代理。

- Python：3.12.13，独立环境 `.venv`。
- OpenROAD：`26Q1-2966-g29d97c45b3`。
- Yosys：`0.63`，Git `d3e297fcd`，slang 插件已实际验证。
- 工具路径：`/opt/EDAs/OpenROAD-flow-scripts/versions/20260409/tools/install/`。
- 平台库：本仓库的 `flow/platforms/`；本版本实际包含这些文件。
- 预测模型：随仓库提供的 `flow/predict_model/best_model.pt`，约 298 KB。
- PyTorch：安装 CPU 版；在线推理模型较小，本次测试不依赖 GPU。
- 已安装版本保存在 `validation/installed-requirements.txt`。
- API key/base URL 未配置；现有 ChatGPT/Codex 登录已完成真实 LLM 测试，
  使用可选的官方 Codex CLI 适配层，详见下文。

## 项目做什么

它是 OpenROAD 芯片物理实现参数优化程序，输入是 RTL、SDC 时序约束、平台库和
参数范围，输出是各轮物理实现结果、参数配置、指标与可追溯实验记录。
随仓库提供 ASAP7/Nangate45 两个平台，各有 AES、IBEX、JPEG 三个设计。

默认研究目标是：在相同参考时钟 CP0 下，使最终总负时序裕量绝对值 `|TNS|`
最小，同时功耗不超过默认设计的基线功耗。`power_budget=0.0` 表示不容许额外
功耗。CP0 由第一轮未扰动 run_1 的最终最小时钟周期乘以 0.9 生成。
本次初始 Nangate45 AES 测试得到 CP0=0.7920 ns。

每轮执行顺序是：

1. `run_sequential.sh` 把参数 CSV 转为独立 `config_N.mk` 和 SDC。
2. `run_stage.sh` / `run_make.sh` 调用本仓库 ORFS Makefile，执行综合和布局。
3. `extract_metrics.py` 提取指标，`drp.py` 在布局阶段边界排序、淘汰和复制检查点，
   `agent.py` 为被替换候选生成下一阶段参数。
4. 执行 CTS，在 CTS 阶段边界重复上述操作，生成布线参数。
5. 执行布线、finish 和 `eval_tns.sh`，在 CP0 下重测 TNS 与功耗。
6. `optimize.py` 或 `optimize_agentic.py` 根据历史生成下一轮参数。
7. 保存完整备份、candidate lineage、实验 manifest、LLM 使用账本和优化状态。

## 声明功能如何实现

| 功能 | 实现与实际含义 |
|---|---|
| 分阶段物理设计 | `maindriver.sh` 组织 place、CTS、route/finish 三个阶段；stage 间有同步屏障 |
| Doomed Run Prediction | `predictor_bridge.py` 加载 Transformer 比较完整基线轨迹与候选的轨迹前缀，预测最终 TNS/功耗的 better/similar/worse 概率 |
| `-P` 的默认排序 | `promising_score=P(power acceptable)×P(TNS better)`，以 `1-score` 作为成本；支持显式 kill-score 消融配置 |
| 提前淘汰与替换 | `drp.py` 在布局/CTS 完成后复制优选候选的 ODB/SDC/配置，并重新生成下游参数，避免继续原来的低潜力分支 |
| Elitist / GWTW | `drp_selection.py` 分别实现按排名选择和带精英保留的概率重采样 |
| Agent1 | `optimize_agentic.py` 的 inspection/model 阶段，LLM 可通过 ReAct 调整 GPR 核、预处理、特征权重和 acquisition |
| Agent2 | 混合 LLM/数值候选与 LHS 候选，使用 GPR、acquisition 和聚类选择，保留精英与探索配额 |
| Agent3 / TextGrad | supervisor 生成批评文本，再重写下一轮 model/selection 指令片段；这里的 gradient 是文本反馈 |
| 无 LLM 运行 | `-A -N` 禁止外部请求，保留数值 Agentic/BO；代码会在 LLM 不可用时采用数值回退 |
| 固定 CP0 / 功耗约束 | `eval_tns.sh` 重载每个候选的物理数据库，在统一时钟下评估；`common.py` 对超预算或缺失功耗给予不可行惩罚 |
| Routing-focus / replay | 代码位于 `search_policy*.py`、`routing_focus.py`、`config_replay.py`，但当前配置没有为随附六个设计启用 calibrated policy |

首轮 `-P` 尚无完整基线，先用阶段指标 bootstrap；得到完整基线后，后续轮次才
按预测模型排序。仅测试首轮不能证明在线预测排序闭环可用。

## 已验证结果

- AES Nangate45 综合通过，见 `validation/baseline-synth.log`。
- IBEX Nangate45 综合通过，包括真正调用 slang，见 `validation/ibex-synth.log`。
- 上游耗时统计测试 5 项通过，见 `validation/upstream-tests.log`。
- 预测模型 preflight 通过，见 `validation/predictor-preflight.log`。
- 对第一轮真实 AES 布局与 CTS 轨迹推理通过，所有概率字段有限且在 [0,1]，
  见 `validation/predictor-real-trajectory.json`。
- 初始 2 候选测试完成全物理流程，但第二轮参数生成失败，原因见下表。
  第一轮默认候选 TNS=-4.36 ns、功耗=0.400 W；另一候选 TNS=-2.15 ns、
  功耗=0.459 W。后者时序更好但超出功耗预算，不能当作可行改进。
- 3 候选、2 轮、启用预测排序的测试完成两轮物理流程、状态写入和备份，第二轮
  3/3 最终评估有效。结果保存在 `validation/two-iteration-result.json` 和
  `validation/nangate45-aes-predictor-smoke.log`。可行最优 |TNS| 从 4.36 降为
  4.29 ns，功耗仍为报告精度下的 0.400 W；其他候选为 -2.69 ns/0.440 W，
  被功耗约束判为不可行。这一小样本变化不证明稳定优化收益。
- 上述驱动最后退出码为 2：测试期间 agent 给运行中的 shell 文件插入启动检查，
  使 Bash 已打开文件的后续读取位置失效，造成最后摘要阶段语法错误。当前文件
  逐项 `bash -n` 通过；这是本次操作引入的问题，不能归因于上游算法。
  原始失败记录保留在
  `flow/backup_dir/nangate45/aes/campaign_20261008_112414/`。
- 固定脚本的单轮完整复测已通过：`-i 1 -r 2 -k 0 -A -N -P`，进程退出码 0，
  使用账本状态 `completed`，completed_iterations=1，两个候选均生成最终 ODB/GDS。
  最优可行候选为 TNS=-4.36 ns、功耗=0.400 W；另一候选为 -5.44 ns/0.390 W。
  见 `validation/stable-driver-smoke.log`、`validation/final-verification.json`。
  驱动文件在复测期间哈希保持不变。这个复测确认入口、完整物理流程、最终状态
  写入、备份、日志清理及正常退出；之前的两轮记录确认跨轮生成和实际预测排序。
- 第一轮已成功生成下一轮参数并进入第二轮；混合候选池包含 6 个 DRP 候选
  与 24 个 LHS 候选。小样本触发了 dummy surrogate 回退，因此本次冒烟测试
  验证流程接线，不证明 GPR 训练质量或优化收益。
- 第二轮实际使用 `promising` 预测排序：布局检查点为 2/3 个候选评分，CTS
  检查点为 3/3 个候选评分。探索候选因 `PLACE_DENSITY > 1.0` 失败后，由 DRP
  复制 run_1 布局检查点替换，随后继续 CTS；失败候选恢复路径已验证。
- 六个设计的完整物理流程、多种 seed、大规模 25×50 优化质量尚未验证。

## 使用现有账号的真实 LLM 测试

服务器的官方 Codex CLI 0.159.3 已登录 ChatGPT。它与通用 API Key 是不同的
认证路径，参见[官方登录说明](https://learn.chatgpt.com/docs/auth)。本次没有读取、
复制或转换 OAuth token。新增 `flow/llm_client.py`，由环境变量
`DRP_LLM_TRANSPORT=codex` 选择账号调用；原 OpenAI-compatible API 保持默认。
`common.py` 与 `optimize_agentic.py` 共用此客户端，覆盖阶段内与跨轮的调用入口。

CLI 每次在独立临时目录启动 read-only、ephemeral 会话，通过 structured output
表达 `configure_inspection` / `configure_model` / `configure_selection` 的决策，
随后仍由项目执行真实数值函数。这是配置工具的结构化输出适配，不能视为原生
Chat Completions tool calling 的等价实验。模型被要求不使用 CLI 工具，返回的
工具名、参数类型、枚举及调用事件均校验。

| 测试 | 实际结果 | CLI 报告的总 tokens |
|---|---|---:|
| 账号连通性 | 默认模型 `gpt-5.6-sol` 调用成功，返回指定 JSON | 12,420 |
| Agent1/2/3 调用链 | 7/7 次成功、退出码 0；三个配置工具真实返回并应用，参数建议和两段 TextGrad 改写成功 | 138,515 |
| ReAct GPR 反馈诊断 | 2/2 次成功；真实训练/验证误差送给模型，模型改变配置，下一步重新训练并反馈 | 23,264 |
| 合计 | 10/10 次成功；未发生 LLM 请求失败或配置工具回退 | 174,199 |

Agent 调用链在 `validation/llm-account/agent-chain/` 的独立工作目录运行，
读取之前完整通过的 Nangate45 AES 第一轮物理结果（两条真实历史），生成
`next_iteration.csv` 三行参数。candidate lifecycle 与 CSV 哈希匹配，最终来源
为 replay、LLM、full_probe 各一项，确认 LLM 建议进入实际输出，而非仅请求成功。
Agent1 选择了两类聚类、0.8 相关阈值，以及 Matern/minmax/EI/0.4 探索比例；
Agent2 选择 hybrid/0.2 quality_weight/0 uncertainty_bonus；Agent3 生成批评后，
实际保存了少于 50 词的 model/selection 指令。三组新参数尚未重新跑物理流程。

两条历史会按代码跳过 ReAct，故另用两个既有实验的真实记录去重得到四条观测，
单独运行两步 ReAct（训练三条、验证一条）。未伪造数据，也未将这些记录拼成
新的优化收益实验。第一次实际反馈 dy=7,677,087.373，模型先改为 RBF/robust，
下一步 dy=7,678,860.1968，随后改为 Matern/standard；最终重新评估
dy=7,682,014.0479，误差没有改善。少量样本和功耗违规的 `1e9` 惩罚主导了
拟合；这一结果验证反馈闭环，同时说明需要更多真实数据及更合适的约束建模，
不能据此宣称 LLM 调参有效。代码没有针对本次测试改变目标或功耗惩罚。

token 计数来自 CLI `turn.completed` 事件，包含 CLI 自身上下文，不能只按
项目 prompt 估算。CLI 路径不应用 API 的 `temperature` / `max_tokens`，使用
`codex_reasoning_effort=low` 和每次调用 timeout；CLI 未报告响应 model id 的
字段留空，requested model 保持 `gpt-5.6-sol`。响应审计与 campaign 账本逐次核对。

验证材料：

- `validation/llm-account/verification.json`：调用、token、CSV 来源与范围汇总。
- `validation/llm-account/agent-chain/agent-chain.log`：完整 Agent 调用日志。
- `validation/llm-account/agent-chain/backup_dir/nangate45/aes/llm_usage_summary.json`。
- `validation/llm-account/react-check.log`、`react-check/result.json`：真实反馈诊断。
- `validation/llm-account/regression-tests.log`：22 项适配层测试和 5 项上游测试，27 项通过。

适配层测试覆盖参数/工具校验、真实 usage 转换、超时杀掉整个 CLI 进程组、
失败时不泄露认证 stderr、保留 API 配置，以及 `-N` 不构造任何调用客户端。

## 问题、修改规模与本地修复

| 问题 | 影响 | 处理与规模 |
|---|---|---|
| 脚本以 100644 发布 | `./run.sh`、ORFS shell 脚本及直接执行的 Python 脚本 permission denied | 已修复所需执行权限；很小，不改算法 |
| 工具不在 PATH | 入口检查失败 | 已写入本地 `config/env.local.sh`；纯环境配置 |
| Python 依赖缺失 | NumPy/BO/预测模型无法完整运行 | 已安装独立 `.venv`；无需系统级修改 |
| 缺少 `.gitignore` | 文档声称忽略的 API/环境配置与运行产物实际未忽略 | 已补 `.gitignore`；很小 |
| README/help 指向不存在的 tools/docs/tests | 快速开始命令与目录结构误导用户 | 已修正为实际文件及已随仓库提供的平台库；很小 |
| `-A -i 2 -r 2` 批量不足 | Agent2 固定保留两项后没有探索槽，花完一轮计算才失败 | 已加启动时检查；多轮 Agentic 使用 `-r >= 3`，不改选择算法 |
| Nangate45 四个布线调整参数未接入对应 Tcl | CSV/配置会变化，但 `PIN_LAYER_ADJUST`、`ABOVE_LAYER_ADJUST` 及 floorplan 对应变量不会按配置生效 | 待接入 floorplan/route 两组独立 hook 并做执行验证；局部、中等工作量 |
| ECP 单位与 Nangate45 baseline 不一致 | `extract_metrics.py` 返回 ps，但 `drp_config.json` 的 Nangate45 ecp_base 是 ns，`ecp/combo` 归一化会偏大 1000 倍 | 待统一内部单位、配置和历史兼容；局部、中等工作量，当前测试使用 TNS_EVAL |
| predictor 统一将时间指标乘 0.001 | 需要核对各平台 JSON 实际单位及模型训练数据单位；Nangate45 CSV 的 ns 字段存在单位契约疑点 | 建议按数据生产/训练契约验证后修复，不能仅凭加载成功判断预测质量；中等 |
| 预测功耗容忍度与最终预算不同 | 训练标签把 ±5% 功耗当 similar，但最终预算默认不容许额外功耗 | 配置已有说明；模型排序不能保证最终功耗可行，最后仍需严格门控 |
| 原程序只支持 API Key，服务器现有登录为 ChatGPT | 直接启动会数值回退，无法使用现有账号 | 已增加可选 Codex CLI 适配层，并真实验证 Agent1/2/3 与 ReAct；局部接入改动，不改优化算法 |
| 小样本与 `1e9` 功耗惩罚主导 GPR 拟合 | 本次真实 ReAct 的 held-out 误差很大且未改善 | 待增加真实样本；研究分开建模可行性/时序或调整 surrogate 训练目标尺度，同时保持终评严格功耗门控；属算法实验工作 |

运行成功和优化质量是两件需要分别验证的事。预测模型能输出概率不等于已证明
它对这台服务器、当前工具版本与每个设计都准确；实际收益应在相同 seed、候选
预算、CP0 和功耗约束下，对比开关 `-P`、开关 LLM 与随机/BO 基线。

## 在这台服务器怎么用

先使用已配置环境进行小规模数值测试：

```bash
cd /home/wjyuan/flow-agent
./run.sh -p nangate45 -d aes -o TNS_EVAL \
  -i 2 -r 3 -k 1 -s elitist -A -N -P -F \
  --seed 42 --cpus 12 --max-concurrent-runs 3 -t 10m
```

`-i` 是轮数，`-r` 是每轮候选数，`-k` 是 elitist 在每个 DRP 边界替换的数量；
`--cpus` 是总线程预算；`--max-concurrent-runs` 限制同时跑的候选数。
本次 shell 允许的 CPU 编号为 0-127，不能直接照抄 README 的 `--cpus 250`；
本地示例用 12 个线程。
`-t` 是每个批次阶段的 timeout，覆盖该阶段所有 worker，不是整个实验的期限。
`-F` 会归档上一实验的状态与备份，然后重开新实验。
GWTW 的替换数量由概率重采样决定，`-k` 只控制 elitist。

使用这台服务器已登录的账号，只需选择 Codex transport 并移除 `-N`：

```bash
cd /home/wjyuan/flow-agent
DRP_LLM_TRANSPORT=codex ./run.sh -p nangate45 -d aes -o TNS_EVAL \
  -i 2 -r 3 -k 1 -s elitist -A -P -F \
  --seed 42 --cpus 12 --max-concurrent-runs 3 -t 10m
```

本次验证默认 `gpt-5.6-sol` 可用；此命令是后续运行方式，没有额外启动这轮物理
实验。默认模型与 supervisor 配置在 `flow/drp_config.json`，无需填写 API Key。
也可在两个配置块写入 `"transport": "codex"`。详细限制见 `RUNNING.md`。

若要使用原生 API 接口，复制 `config/api.sh.example` 为 `config/api.sh`，本地
填写 `OPENAI_BASE_URL` / `OPENAI_API_KEY` 并设置权限 600，然后配置实际支持的
`llm.model` / `supervisor.model`，移除 `-N`，不设置 `DRP_LLM_TRANSPORT=codex`。
接口须支持 OpenAI-compatible `chat.completions` 和 tool calling。

结果可查看：

- `flow/backup_dir/nangate45/aes/result_dump_N/`：每轮配置、日志、指标与状态备份。
- `flow/designs/nangate45/aes/optimization_state.json`：优化状态与 best/replay 信息。
- `flow/results/nangate45/aes/run_N/`：当前候选的网表、物理数据库及最终产物。
- `flow/logs/` 和 `validation/`：运行及本次验证日志。成功实验结束后会清理
  `flow/logs/`，每轮日志保留在对应 `result_dump_N/logs_dump/`。
- `flow/backup_dir/nangate45/aes/llm_usage_summary.json`：调用数和 token 账本。

更换设计可改 `-p asap7|nangate45` 与 `-d aes|ibex|jpeg`。
正式规模可逐步增加候选与轮数；大规模命令前应先修正上述参数生效及单位问题，
再评估优化效果。
