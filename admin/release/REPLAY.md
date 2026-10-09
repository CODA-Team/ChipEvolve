# 同服务器干净安装与业务重放

本说明使用本地 Git bundle，不依赖作者的源码工作树。GitHub 发布尚未执行。
代码包、工程验收、模型效果是分别记录的项目；代码包存在不表示诊断验收通过。

## 安装五个项目

选一个不存在的新目录。最终交付报告会列出包含本说明及管理脚本的代码包路径；在该路径下执行以下命令。

```bash
EDA_DELIVERY=/home/wjyuan/projects/eda-development/var/releases/eda-30h-20261009-code-v2
EDA_WORKSPACE=/home/wjyuan/projects/eda-user-demo
git clone "$EDA_DELIVERY/repositories/workspace.bundle" "$EDA_WORKSPACE"
for EDA_PROJECT in execution-foundation data-foundation data-interface toolkits query-agent; do
  git clone "$EDA_DELIVERY/repositories/$EDA_PROJECT.bundle" "$EDA_WORKSPACE/$EDA_PROJECT"
done
python3 "$EDA_WORKSPACE/admin/install_workspace.py" \
  --workspace "$EDA_WORKSPACE" \
  --packages "$EDA_DELIVERY/packages" \
  --dependencies "$EDA_DELIVERY/dependencies" \
  --evidence "$EDA_WORKSPACE/var/install-record"
```

安装器给五个项目分别创建虚拟环境，使用离线 wheel；记录命令、版本、依赖检查和耗时。
需要 Python 3.12、Git 和已有 Apptainer。工具镜像为同服务器共享部署输入，不随 Python 包复制。
已有实测：新目录本地克隆 18.87 秒、安装 62.96 秒；另从交付 bundle 克隆六个仓库 0.88 秒。
这些是本服务器的单次观察，不能保证其他机器同样耗时。

## 启动一个独立实例

每个实例有独立端口、数据库、任务目录和日志。Data Interface 是 SDK；Query Agent 是 CLI；两者不需要另开服务。
同服务器的所有本轮 EDA 调用必须使用同一活动锁。下面使用正式测量和干净重放共用的锁，路径属于运行状态，不属于源码依赖。

```bash
EDA_CONFIG="$EDA_WORKSPACE/var/instances/demo/configuration.json"
python3 "$EDA_WORKSPACE/admin/release/stack.py" init \
  --config "$EDA_CONFIG" --workspace "$EDA_WORKSPACE" --instance demo \
  --image /home/wjyuan/projects/eda-toolchain/orfs-8e6ee7aac233da07.sif \
  --kernel-port 19710 --data-port 19934 \
  --activity-lock /home/wjyuan/projects/eda-development/var/sprints/20261008-141846/coordination/eda-activity.lock
python3 "$EDA_WORKSPACE/admin/release/stack.py" start --config "$EDA_CONFIG"
python3 "$EDA_WORKSPACE/admin/release/stack.py" status --config "$EDA_CONFIG"
```

启动使用已安装模块和 `python -I`，工作目录为 `/tmp`。实例管理只操作自己登记的 PID、启动身份和准确命令。
停止前检查所有分页的任务记录；存在进行中任务时必须先等其完成或显式取消。

## 完整 ORFS 流程

```bash
python3 "$EDA_WORKSPACE/dev.py" query-agent python \
  "$EDA_WORKSPACE/admin/evaluation/orfs_replay.py" \
  --config "$EDA_WORKSPACE/var/instances/demo/toolchain.json" \
  --kernel-url http://127.0.0.1:19710 --data-url http://127.0.0.1:19934 \
  --output "$EDA_WORKSPACE/var/replay/demo-orfs-1" \
  --revision demo-gcd-01 --snapshot demo-gcd-01-finish
```

重放脚本使用 Toolkits 构造任务，经 Execution Foundation 提交完整 Nangate45/GCD 流程，再导出并导入 Data Foundation。
以上 ID 适用于第一次运行。再次提交新实验时更换 revision、snapshot 和输出目录；需要恢复原任务时使用脚本的 `--resume-flow`/`--resume-export`。
现有可复核重放结果：

- `/home/wjyuan/projects/eda-clean-room-20261009-v1/var/replay-a/orfs-1/summary.json`
- `/home/wjyuan/projects/eda-clean-room-20261009-v1/var/replay-a/sta-recovery-1/summary.json`
- `/home/wjyuan/projects/eda-clean-room-20261009-v1/var/replay-a/clock-pair-1/public/bindings.json`

完整流程成功不等于设计时序收敛。定向 STA 形成新的分析身份与快照，原实验保持可追溯。

## 调查和恢复

```bash
python3 "$EDA_WORKSPACE/dev.py" query-agent python -m query_agent investigate \
  'Inspect the setup and hold results. What is known, what evidence is missing, and which bounded STA would clarify it?' \
  --snapshot demo-gcd-01-finish \
  --data-url http://127.0.0.1:19934 --kernel-url http://127.0.0.1:19710 \
  --state-root "$EDA_WORKSPACE/var/investigations/demo-1" \
  --model codex --codex-mode hosted --max-seconds 180
```

该命令使用上一步生成的真实 snapshot ID。Codex 使用已有订阅；Flash 需要本地模型配置及成本账本。
凭据不随代码、配置样例或证据包分发。JEV 默认关闭；采用结论须看整项任务的 E/D 对照，不能仅看分类准确率。
调查暂停时从输出中取得 investigation_id，再用同一 state-root 执行 `query_agent resume ID`；原范围、证据和预算随状态恢复，不重新创建调查。
本轮真实恢复案通过来源与原生数值审查；干净时序比较第一次在 180 秒内未完成，第二次 360 秒演示用了 183.31 秒。
第二次不计入 180 秒正式成绩。完整评分和限制见 [本轮验收报告](ACCEPTANCE_20261009.md)。

## 指定 endpoint 的补 STA 和真实模型恢复

```bash
python3 "$EDA_WORKSPACE/dev.py" query-agent python \
  "$EDA_WORKSPACE/admin/evaluation/investigation_lifecycle.py" \
  --data-url http://127.0.0.1:19934 --kernel-url http://127.0.0.1:19710 \
  --snapshot demo-gcd-01-finish --output "$EDA_WORKSPACE/var/replay/demo-sta-1"
```

该验收脚本显式提出 resp_msg[12] 的定向 setup/hold 请求，重建应用宿主并等待新快照回流。
脚本输出调查 ID 后，下面把 ID 换成真实输出，使用模型继续该状态：

```bash
"$EDA_WORKSPACE/query-agent/.venv/bin/python" -I -m query_agent resume INV_ID \
  --data-url http://127.0.0.1:19934 --kernel-url http://127.0.0.1:19710 \
  --state-root "$EDA_WORKSPACE/var/replay/demo-sta-1" --model codex --codex-mode hosted
```

这是一次明确发起的补分析和模型恢复演示。正式评测中另有模型自行提出分析的原始轨迹，不能把脚本预定动作当作模型推理成绩。

## 制造受控的时钟退化并调查

```bash
mkdir -p "$EDA_WORKSPACE/var/replay"
cat > "$EDA_WORKSPACE/var/replay/demo-clock-specs.json" <<'JSON'
{"e00": {}, "e01": {"period_ns": 0.2}}
JSON
python3 "$EDA_WORKSPACE/dev.py" query-agent python \
  "$EDA_WORKSPACE/admin/evaluation/controlled_native_cases.py" \
  --kernel-url http://127.0.0.1:19710 --data-url http://127.0.0.1:19934 \
  --snapshot demo-gcd-01-finish --output "$EDA_WORKSPACE/var/replay/demo-clock-pair-1" \
  --specs "$EDA_WORKSPACE/var/replay/demo-clock-specs.json" --cases e00 e01 --prefix demo-clock
"$EDA_WORKSPACE/query-agent/.venv/bin/python" -I -m query_agent investigate \
  'Investigate setup degradation from baseline to candidate. Compare worst stored setup/hold, original input identities and loaded constraints; state evidence, counterevidence, sampling and causal limits.' \
  --snapshot demo-clock-e00-finish --snapshot demo-clock-e01-finish \
  --data-url http://127.0.0.1:19934 --kernel-url http://127.0.0.1:19710 \
  --state-root "$EDA_WORKSPACE/var/replay/demo-clock-investigation-1" \
  --model codex --codex-mode hosted --max-seconds 360 --max-analyses 0
```

受控实验显式改变新候选的约束，保留原实验。原生参考放在 private 子目录，模型只拿公开快照；不要把参考加入提示。
360 秒是可重放演示预算，正式诊断预算仍为 180 秒。模型运行有波动，命令完成后仍须检查来源和答案。

## 真实 Codex 接收者：一个受限缓冲尺寸实验

以下许可针对本说明的 Nangate45/GCD 演示；当前 master 会由 Query Agent 与接收者分别核对，发生变化将拒绝。
不把这份许可套到其他设计上。接收者只调用现有公开 `receive-handoff`，工具任务仍由 Toolkits 构造。

```bash
cat > "$EDA_WORKSPACE/var/replay/demo-buffer-permissions.json" <<'JSON'
{"demo-gcd-01-finish": [{"instance": "place178", "original_master": "BUF_X1", "allowed_masters": ["BUF_X2", "BUF_X4"], "operation": "buffer_resize"}]}
JSON
"$EDA_WORKSPACE/query-agent/.venv/bin/python" -I -m query_agent investigate \
  'Prepare a bounded ECO handoff for place178 using supplied operator permissions. Verify its master and fixed original inputs, retrieve baseline timing, and use the handoff action to prepare the actual task package. Measure one permitted buffer resize with clocks, constraints, libraries, RC and corner fixed. Preparation is not receiver acceptance or repair success.' \
  --snapshot demo-gcd-01-finish --data-url http://127.0.0.1:19934 --kernel-url http://127.0.0.1:19710 \
  --state-root "$EDA_WORKSPACE/var/replay/demo-handoff-prepare-1" \
  --handoff-permissions "$EDA_WORKSPACE/var/replay/demo-buffer-permissions.json" \
  --model codex --codex-mode hosted --max-seconds 180 --max-analyses 0
"$EDA_WORKSPACE/query-agent/.venv/bin/python" -I "$EDA_WORKSPACE/admin/release/export_prepared_handoff.py" \
  --state-root "$EDA_WORKSPACE/var/replay/demo-handoff-prepare-1" \
  --output "$EDA_WORKSPACE/var/replay/demo-handoff-package.json"
"$EDA_WORKSPACE/query-agent/.venv/bin/python" -I "$EDA_WORKSPACE/admin/release/codex_handoff_replay.py" \
  --package "$EDA_WORKSPACE/var/replay/demo-handoff-package.json" \
  --data-url http://127.0.0.1:19934 --kernel-url http://127.0.0.1:19710 \
  --output "$EDA_WORKSPACE/var/replay/demo-handoff-receiver-1"
"$EDA_WORKSPACE/query-agent/.venv/bin/python" -I "$EDA_WORKSPACE/admin/release/audit_replay_handoff.py" \
  --package "$EDA_WORKSPACE/var/replay/demo-handoff-package.json" \
  --receiver "$EDA_WORKSPACE/var/replay/demo-handoff-receiver-1/receiver" \
  --data-url http://127.0.0.1:19934 --kernel-url http://127.0.0.1:19710 \
  --output "$EDA_WORKSPACE/var/replay/demo-handoff-independent-audit-1"
```

如果准备阶段没有实际 package，导出器明确失败，不会补造任务。
读取 receiver/receipt.json 中的真实 snapshot_id，用下面的 CANDIDATE_ID 替换该值，再让 Query Agent 复查：

```bash
"$EDA_WORKSPACE/query-agent/.venv/bin/python" -I -m query_agent investigate \
  'Review the bounded ECO result: verify original conditions and cell change, compare matched and worst stored setup/hold, and retrieve complete instance geometry via objects/statistics?kind=instance&include_physical=1 for both scopes. State area basis/delta, residual violations and signoff/causal limits. Read only.' \
  --snapshot demo-gcd-01-finish --snapshot CANDIDATE_ID \
  --data-url http://127.0.0.1:19934 --kernel-url http://127.0.0.1:19710 \
  --state-root "$EDA_WORKSPACE/var/replay/demo-handoff-review-1" \
  --model codex --codex-mode hosted --max-seconds 180 --max-analyses 0
```

独立审查重新加载两侧原始数据库，生成同条件 native STA、网表和面积；它不使用产品解析器给自己的答案打分。
setup 改善、任务执行成功和彻底修复分别判断。仍有负 setup slack 就不能称闭合。
本轮完全干净交接的第一次 180 秒复查耗尽 32 次读取、没有答案。另建状态目录的 360 秒演示明确要求最多 16 次读取后回答，在 203.07 秒给出 setup/hold/完整几何面积比较及 `partial` 结论；未取得的机制与物理合法性证据仍列为缺失。需要演示较长预算时，保留首次目录，另建 `demo-handoff-review-2`，把上例预算设为 360，并在问题中加入 `Use at most 16 public reads before answering.`。这不代表 180 秒验收通过，也不自动补跑至成功。

## 失败、超时、取消与证据复核

```bash
python3 "$EDA_WORKSPACE/dev.py" query-agent python \
  "$EDA_WORKSPACE/admin/evaluation/execution_lifecycle.py" \
  --kernel-url http://127.0.0.1:19710 --data-url http://127.0.0.1:19934 \
  --snapshot demo-gcd-01-finish --output "$EDA_WORKSPACE/var/replay/demo-lifecycle-1"
```

这是主动启动真实失败/超时/取消任务的验收，日志、状态和进程记录保留。默认工作盘上的 5 秒取消门槛本轮未通过，重放可能同样失败；失败不会删除记录或算作通过。
代码包的 manifest 给出每个文件哈希；证据包的校验与展开不需要产品 parser：

```bash
python3 "$EDA_WORKSPACE/admin/release/build_evidence_delivery.py" verify \
  --bundle /home/wjyuan/projects/eda-development/var/releases/eda-30h-20261009-evidence-v1 --external
python3 "$EDA_WORKSPACE/admin/release/build_evidence_delivery.py" restore \
  --bundle /home/wjyuan/projects/eda-development/var/releases/eda-30h-20261009-evidence-v1 \
  --output "$EDA_WORKSPACE/var/restored-evidence"
```

外部依赖在本服务器原位置逐一核验；展开只复制内部证据 blob，另外列出大型原生输入/数据库/镜像的路径和哈希。
完整审计会读取大量数据。不要把已经存在的输出目录作为新验收目录复用。

## 停止与复核

```bash
python3 "$EDA_WORKSPACE/admin/release/stack.py" stop --config "$EDA_CONFIG"
```

停止不会删除数据库、日志、原始产物或调查状态。重新启动后通过原 run ID 与 snapshot ID 查询。
完整工程与业务验收、失败和缺测以本轮最终报告及原始证据为准；旧的 `admin/ACCEPTANCE_REPORT.md` 是整理阶段记录。
