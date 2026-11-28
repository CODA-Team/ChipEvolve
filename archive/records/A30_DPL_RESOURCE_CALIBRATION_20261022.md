# A30：GCD DPL 物理预约按实测校准

2026-10-22。范围只涉及既有 DPL 接入行为和新实验配置；不改原生源码算法、8 工具线程、编译预约、EF 容量、公共 API 或历史运行。

`chip_evolve/professional.py::run_dpl` 原先不论设计都覆盖模板为 24 GiB。与 Goal 接入一致，改为读取内部绑定 `professional.dpl.physical_memory_gib`，未声明时仍为 24 GiB。本轮新 GCD 接力显式选 8 GiB。

公开 EF 历史证据来自同一 F37 输入的原 GCD DPL 轮次：三个原生布局评估 run-340c980e3b6147cbb40213997bc78b1b / run-a5cac9debfee4e088aa34e95d94cf25d / run-c54ca1291c034e6fb8802ba679419cf4 全 succeeded，峰值分别 304599040 / 280584192 / 314228736 字节。两次 variant build 峰值约 4.56 / 4.59 GiB，原 8 GiB 构建预约保持；core build 仍为 32 GiB。新物理预约 8 GiB 有充分实测余量，不是缩减专业能力。

两项针对回归覆盖实际 run_dpl 写出的冻结 profile：默认保持 24 GiB、显式 8 GiB 生效，同时 build/variant_build/线程/进程和数据父项不变。相关检查 10 通过，根 admin/test_*.py 611 通过；Ruff、格式、Pyright 通过，26 个保护文件 SHA 不变。差异只改一行配置绑定，模块边界保持。

原 GCD 完整接力首评估 run-d965ec307a9e43e8aad17581d179ced5 只有在 queued 且 attempts=0 时才可替换。新实验使用独立 memory8 key，原排队、取消理由和所有输入留存。替换不取消任何已运行计算，也不把新任务排队称作接力/双次平均已完成。

实际取消、替代运行、只读完整接力收集器和两套 Ariane 参考家族更正的回执保存在 var/business/a30-four-design-two-pdk-20261021；当前八组双次合格仍未收齐。
