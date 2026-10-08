# Query Agent 主项目

遵守 CONTRIBUTING.md 与 .importlinter 的依赖方向。
保留已有未提交修改，勿重置或替换为旧平台 apps/query_agent。
使用本项目 .venv；跨项目通过 HTTP 或 Data Interface 发布 wheel，不读服务内部数据库。
设计数据端口通过已安装 Data Interface SDK 接入 Data Foundation。当前接通对象、WNS/TNS、时序路径和实验比较；关系/物理查询、自动补分析及自主根因推理仍未完成，不得将 unavailable 状态改为空数据或伪造成功。
