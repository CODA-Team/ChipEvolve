# data-foundation

独立项目，负责设计事实、快照、查询与独立数据库。安装包名称与原实现保持一致，保留其文件 Git 历史。

从上级工作区使用：

```bash
python3 dev.py data-foundation check
python3 dev.py data-foundation shell
```

Data Foundation 安装 contracts/client wheel，原始产物通过公开 HTTP API 获取。
独立数据库默认在上级 var/data-foundation；新服务端口 18924。
使用 `python3 dev.py data-foundation serve` 启动；`--kernel-url`、`--native-root`
显式配置外部执行服务和原始 flow 目录。默认不接入旧运行状态。
smoke.py 使用已安装的包启动临时进程，不依赖原 monorepo 目录。
source_fingerprint 覆盖服务及已安装公共包；外部 producer 的溯源属于快照证据。

先前 API 和工具使用说明见 docs/original-project-readme.md（原 monorepo 安装路径
已成为历史示例）。迁移来源见 MIGRATION_SOURCE.json；完整工作区说明见上级 README。

## 0.2 ownership

本服务拥有 `/designs` 聚合、`/scope` 唯一快照选择、按精确名称/ID解析对象，以及按 snapshot 校验 run 所有权的 canonical metrics。多个候选返回 partial，零候选返回 not_found，不隐式取最新。
快照导入只接受实际产物 producer 或公开声明的 analysis parent；原始产物通过执行服务注册身份关联。精确报告路径优先匹配，ZIP 与包内成员哈希分别记录，冲突来源不绑定权威产物。

直接 Python 可以扫描 JSON 或建立内存字典；小数据下可能更快、更省空间。本服务的价值是跨进程持久查询、共同作用域和来源约束。合成 50k 对象测试不代表真实芯片性能；详见 ../admin/ACCEPTANCE_REPORT.md。

## Read and analysis boundaries (0.2.1)

GET and `POST /query` are read-only. `resolve=1`, native pin inventory/geometry,
analysis setup, native area comparison and instance power no longer execute via GET.
Use `POST /snapshots/{id}/analyses/{operation}` for these explicit operations;
`timing-overview`, `pin-engineering`, `pin-inventory`, `analysis-setup`,
`net-inventory`, `instance-power`, `compare-inventory` retain their existing calculation
implementations during Toolkit migration. Object operations receive `name` in the JSON body.

`POST /snapshots/{id}/timing-queries` explicitly submits STA. Status GET does not
import results; `POST /timing-queries/{run}/import` with `{}` explicitly imports.
`POST /imports/ready` explicitly imports completed bundles. Any configured auto-import
is a startup operation, never a read side effect.

For historical databases use `--read-only --no-auto-import`; registration and
analysis POSTs then return HTTP 403. The existing DB is opened in SQLite `mode=ro`.

Historical snapshots can be mounted with repeated `--archive-db <path>` while
new snapshots go into the independently configured `--db`. Archive SQLite
connections use `mode=ro`; duplicate snapshot IDs across databases are rejected.
The global catalog is combined, while scoped fact queries use the owning DB's
physical tables and indexes. `--archive-kernel-url` is used only for original
artifact reads; `--kernel-url` owns new execution and result import.

Cross-experiment comparison is explicit: use `mode=experiment` on timing-path or
metric comparisons. The default stage mode still requires one run/revision.
Experiment mode keeps the two scopes distinct, computes observed matched-path
arrival/required/slack deltas, and exposes registered input hashes and unknowns.
It does not label a changed-constraint result as physical improvement.
