# A30：按实测校准确定性事实任务预约

业务问题：JPEG/Nangate45 完整 DRT/RCX 已成功，但共同测量仍固定预约 8 GiB。在其他正常计算保留内存时，小事实任务无法进入剩余 4 GiB 的窗口。平台应帮助完成交付，不应让不必要的固定预约阻碍结果可见。

改动文件：`chip_evolve/physical.py` 在既有 `fact_execution` 私有设计绑定读取 `memory_gib`，共同测量及 OpenDB/ORFS/OpenSTA 导出使用该预约；默认 8 GiB、CPU2、时限、完整原件/事实、模型与目标均保持。显式非默认配置使用独立 `-m4` 等任务与测量目录，不覆盖原任务和失败记录。`admin/test_fact_execution_budget.py` 覆盖完整三视图、相同配置复用、输入及条件不变、measurement/analysis 父项保持。

公开 EF 实测：JPEG/Nangate45 原共同测量 run-bc50b032238147aba152a66305cca89e 峰值 701112320 字节；Ariane/Nangate45 run-cee1e01bd7454c0693b7e8af699c87db 峰值 2606338048 字节。本轮相关新配置取 4 GiB，分别留约 6.1 倍和 1.65 倍空间；不是删数据或缩减优化能力。EDA 优化/布线的预约保持独立，不受此字段影响。

运行边界：仅对本轮明确未完成的确定性交付使用新配置；已经完成的历史实验保持原样。若替换原排队事实任务，先核对 queued/零 attempt，再保留原取消证据并使用新的 `-m4` 任务；复用已成功的 DRT/RCX 与原输入 SHA，不重跑专业优化。健康计算不取消，服务、32 GiB 总容量、公共 CLI/EF/DF/DI 接口、数据库和专业算法不变。

检查：11 项针对回归、613 根回归通过，Ruff/格式/Pyright 通过，26 个保护文件 SHA 不变；逐文件差异只涉及预约和非默认任务身份，无跨模块内部依赖。修改清单另含 TASKS.md、ARCHITECTURE.md 的事实同步与本文档。本改动不是八组实验或两次完整协作已完成的证明。

另：原 Goal 实验性 MeasuredCriticalPathPolicy 在全局/原生增量 RC 两种既有模式下分别触发 STA 路径访问断言/崩溃，均无最终可采用产物；本轮不继续堆 CPP 补丁或复跑失败策略。已保存原日志和源码指针，原四 Student、DPL、ECO 与成熟原生工具分支独立保留。最新物理结果继续以实际 EF/DF 记录判断。
