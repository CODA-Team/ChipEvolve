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
