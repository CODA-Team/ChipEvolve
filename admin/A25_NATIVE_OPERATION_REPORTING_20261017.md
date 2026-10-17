# A25：原生 Codex 对照的离线汇总

正式操作对照现在有独立、可执行的冻结和汇总入口。它保留声明清单中的全部任务，以外部独立核查决定正确性，再报告模型成本；不会因退出码为零、错误答案更快、缺失用量或未开始而制造效率收益。本片补齐结果汇总能力，没有启动正式 A27，也没有新增模型或 EDA 运行。

## 文件和数据流

- `admin/report_native_operation_matrix.py`：冻结原生两侧的任务/规格/oracle 身份，读取原 recorder 收据与绑定的独立核查，输出全清单和可比较成对成本。
- `admin/test_native_operation_matrix.py`：验证失败/缺失/运行中记录、未知用量、缓存子集、相同后端/模型/预算、独立核查身份、冻结内容以及正确性优先的行为。

数据流是：声明两侧任务 → 内容冻结 → 既有 `run_native_codex_episode.py` 执行 → 外部领域 oracle 核查 → 离线汇总。这个文件不运行模型或 EDA，不判断 PPA 是否更好，不访问 EF/DF 内部数据库，也不使用用户未提交的 evaluation 代码。

调用方式（从根目录，使用已安装依赖的 client Python）：

```text
python -m admin.report_native_operation_matrix freeze --input request.json --output matrix.json
python -m admin.report_native_operation_matrix report --input matrix.json --output report.json
```

request 声明 purpose、pair_id、design_id、scenario、共同 task 文件、工作量是否等价，以及 direct/platform 各自的原生 specification、episode 输出目录、oracle 输出及 oracle 程序路径。正式两侧必须同一 native Codex 后端、模型、推理设置、墙钟预算，规格均包含共同 task，且输出目录尚不存在；已有准备案例不能事后改成正式试次。既有原生 recorder 的 token 硬限额能力没有改变，正式总预算和物理资源政策仍须由 A25 全局协议另行冻结。

oracle 输出将 verdict 绑定到 episode、receipt SHA、核查程序 SHA 和证据文件 SHA。缺少核查为未验证，退出零不自动通过。缺失或运行中的用量保留未知；已知失败用量仍计入下界，cached input 只作为 input 子集。只有正式等价工作量、双方正确且用量完整、原生执行完成时，才报告成对 input+output 和墙钟成本。CPU 范围沿 recorder 原限制，不计算完整主机 CPU 比。

## 检查及真实案例

13 项针对测试、464 项根回归、Ruff/格式/Pyright 和差异检查通过。依赖仅为根项目已有配置/哈希助手及标准库，专业模块、活动 JPEG、服务、接口和 26 份用户文件保持。

用已有真实 GCD 恢复案例做了离线复核，重新检查直接侧 129 份产物/证据哈希：

| 资格观察 | 独立正确数 | 已知 input+output | 用量缺失 | 正式成本比 |
|---|---:|---:|---|---|
| 原失败平台 r1 + 直接侧 r1 | 1/2 | 2,388,254，下界 | 平台 TLS 中断 | 无 |
| 修复平台 r2 + 同一直接侧 r1 | 2/2 | 2,057,309 | 无 | 无 |

原平台目标身份错误和重复发布改变结果哈希均从原保存文件再核实，仍记失败。上述两张表是事后资格观察，共用同一个直接侧 episode，不能相加为独立重复，也不能比较两行 token 总量来宣称收益。没有新调用，原 11 次外层 native CLI 及失败账本不变；原数据和收据未回写。

证据：`var/business/a25-formal-preparation-20261017/native-operation-matrix-live-r1/` 内的 `acceptance.json`、before/after 的冻结矩阵、报告与 oracle 绑定；门禁日志为同目录上级的 `native-matrix-root-regression-final.log`。JPEG 完整优化、两个 Code 健康轮次、真正专业接力和预算校准仍未结束，A25 尚未冻结，A26–A28 尚未开始。
