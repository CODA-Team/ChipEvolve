# A31.1：复用已完成证明，恢复验证交付

业务问题：Ibex/ASAP7 EQY原生已产出PASS及成功日志，但独立续算脚本读取不存在的`status`文件，原EF任务最终记录为extractor_error。历史失败记录保留；恢复任务登记已有证明原件，不重做PDR。

## 当前实现

- `chip_evolve/validation.py`：验证收尾优先检查已有`logic/logical-equivalence.json`；核对结果对、完整输出义务、已声明Liberty及全部冻结输入，要求证明/证据生产者在公开EF中成功，再继续物理与数据交付。不存在完整证明收据时仍走原证明入口。
- `admin/test_validation_completed_proof.py`：覆盖原生产者复用、重放中断后续接、部分证明/旧SAT/不同结果/失败EF/缺失或变更模型拒绝。
- 公共CLI/函数签名、EF/DF/DI契约、专业算法与条件保持。只新增内部收据消费检查，Codex仍决定采用。

## 验证与真实进展

静态检查、格式、Pyright零错误；25项相关检查、627项当前根回归通过。逐文件差异与依赖检查限于验证模块和相应测试。

真实审计确认18,737分区全部PASS，106输出与1938原始状态义务覆盖来源保持，16691个实际额外切点已经作为义务证明。全部冻结网表/库、配置与覆盖文件哈希一致，两次物理试验的最终网表都与被证明网表同字节。完整原始分区状态、PASS、日志、配置和独立审计已打包并由新EF证据任务登记。

运行目录：`var/business/a31-result-recovery-20261024`。`ibex-completed-proof-audit.json`记录完整核验，`runtime/experiments/ibex/a31-ibex-asap7-recovered-proof-validation-r1/logic/logical-equivalence.json`关联新EF证据生产者与原失败句柄。

完整平台validation已接续物理重放和DF/DI核对；本提交是实现与证明恢复检查点，不把待完成重放或最终采用写成通过。没有重启原搜索、重新计算PDR或覆盖历史失败状态。
