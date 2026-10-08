# Agentic EDA Query Agent

This repository is the Phase IV foundation for an evidence-first Query Agent
for ASIC physical design and OpenROAD. It intentionally does not parse DEF,
SPEF, ODB or timing graphs, execute shell commands, or run an agent framework.

The core pipeline is ordinary Python:

```text
QueryRequest -> intent -> QueryPlan -> providers -> Evidence
             -> deterministic sufficiency -> QueryResponse
```

The filesystem adapter is read-only and sandboxed to one workspace. Design-data and analysis use the installed Data Interface SDK over public HTTP.
Object lookup, WNS/TNS, timing paths and aligned experiment comparison are connected.
Relations, physical queries and autonomous diagnosis still have explicit unavailable boundaries.
See [`docs/execution-foundation-integration.md`](docs/execution-foundation-integration.md)
for the execution boundary; current data integration is described below.

The current capability status and overnight review package are in
[`docs/capability-matrix.md`](docs/capability-matrix.md) and
[`docs/tomorrow-report.md`](docs/tomorrow-report.md). A five-minute local demo
is available at [`demo/demo_phase1.sh`](demo/demo_phase1.sh); set
`EDA_CORPUS_ROOT` to a real EDA-Corpus checkout to exercise the knowledge
provider.

## Development

```bash
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
pyright
lint-imports
pytest
```

The project has no dependency on the execution-foundation Python packages.

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
change alone cannot prove resizing caused it. The current planner and evidence
policy are deterministic Python, not a general autonomous LLM reasoning engine.
No automatic supplementary-analysis submission is claimed.

Codex can parse reports and compare values directly. This project supplies a
reusable evidence and answerability policy; the paired pilot does not establish
better reasoning or lower latency. See ../admin/ACCEPTANCE_REPORT.md and
CONTRIBUTING.md for gates and known gaps.
