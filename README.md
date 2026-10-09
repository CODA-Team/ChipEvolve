# Agentic EDA Query Agent

This project provides read-only evidence queries and durable, bounded timing
investigations for ASIC physical design. Design facts come through the Data
Interface SDK/HTTP; Toolkits owns OpenROAD commands and EF owns task execution.

The simple `ask` path retains deterministic planning and sufficiency checks.
The new `investigate` path supports competing hypotheses, original source
retrieval, explicit supplementary STA, pause/resume, and evidence-backed handoff.
Codex hosted/adapter modes and official DeepSeek Flash share one application.
Optional JEV judgments remain advice. See [investigation usage](docs/investigation.md).

Engineering checks and real execution receipts are separate from diagnosis
quality measurements. Development failures and the frozen formal comparison
must be reviewed before claiming reliable causal reasoning or lower cost.

## Development

```bash
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
pyright
lint-imports
pytest
```

Execution uses the published client wheel and HTTP; no kernel implementation
or sibling source checkout is imported.

## 独立开发工作区（2026-10-08）

这是主 Query Agent 实现，保留原独立仓库的未提交工作。原平台 apps/query_agent
是不同的历史服务实现；没有并入本项目。
使用上级 `python3 dev.py query-agent check` 或 `python3 dev.py query-agent shell`。
执行生命周期走 HTTP 适配器；设计数据走已安装的 Data Interface 0.2 wheel。
接口歧义、缺数据与错误归属分别返回 NEEDS_MORE_DATA 或 FAILED，不能伪造成功。

## 0.2 actual integration

```bash
query-agent ask "timing WNS" --data-url http://127.0.0.1:18924 --run RUN --stage timing
query-agent ask "Compare WNS difference" --kernel-url http://127.0.0.1:18700 \
  --data-url http://127.0.0.1:18924 --design DESIGN --stage timing --compare-runs BASE CHANGED
```

Unique snapshot/revision/run/stage identity stays in typed evidence. Successful
execution control stages and indexed data stages have different meanings.
Metric answers require units, corner and registered source digest; a metric
change alone cannot prove resizing caused it. The `ask` planner and sufficiency policy remain deterministic. Supplementary
analysis is available only in the explicit investigation workflow described above.

Codex can parse reports and compare values directly. This project supplies a
reusable evidence and answerability policy; the paired pilot does not establish
better reasoning or lower latency. See ../admin/ACCEPTANCE_REPORT.md and
CONTRIBUTING.md for gates and known gaps.
