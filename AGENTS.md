# data-foundation

本项目负责设计事实、快照、查询与独立数据库。这里只修改自己的源码，使用自己的 .venv。
跨项目只能使用已安装公共 wheel 或 HTTP；禁止 sys.path/PYTHONPATH 指向 sibling。
Data Foundation 不导入 kernel 实现、Query Agent 或其他应用，不直接读 kernel 数据库。
Data Interface 不导入服务存储实现，不新增数据库或服务进程。
安装路径、数据库路径和原始文件根目录由运行参数配置，不硬编码旧机器目录。
运行数据放上级 var，测试使用临时目录。执行验证使用上级 dev.py。
