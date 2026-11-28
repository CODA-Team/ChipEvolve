# A30：补回原 TNS 机制，接续中断的真实实验

本轮交付的是已审查的源码迁移补丁、可恢复的重复实验入口及真实续作。八组双次完整 PPA 验收仍在进行，新源码尚未完成二进制实测，不能将测试通过或任务入队当成指标改善。

## 原专业机制的修复

实际编译的 Goal Student03 源码与原项目 p0 对比，确认 TNS 入口没有清除 WNS 访问集合、跳过最差端点、固定每端点单路径，并以 WNS/端点改善代替了原 TNS 收益与损害约束；原配方设置的 `RSZ_TNS_ACCEPT_ENDPOINT_IMPROVE` 没有消费者。这是迁移遗漏，增加迭代预算不能代替修复。

隔离源码补回原 p0 机制，同时保留 Student03 已验证的“未接受尾部动作回滚”和计数。701 个声明源码中仅 `src/rsz/src/policy/SetupTnsPolicy.cc` 改变，其余 700 个逐字节保持。原 p0、旧 Student、正在执行的源码及历史实验均未修改。

可审查补丁发布在 Goal 模块 `toolchain/patches/restore-original-tns-policy.patch`，附基线文件 SHA 和应用说明。补丁从当前 common 源在单文件隔离目录实际应用后，与实验中的修复文件 SHA 完全相同：`4eb847b56eb7208992ab1698836c3e1b5e3f6be512091f75a6d159842df6e672`。

修复源码清单哈希为 `ddbb1fc5915bf5126e72c8327ff1f686757ca30c5e19db5b9945bf3708b50ab9`。原生 AST 已重建，包含 160 个文件、1,989 个符号，保留后续 Teacher/Student 的源码理解入口。

实际构建控制：`a30-gcd-nangate45-restored-tns-native-control-r1`，EF `run-8dfa5818fb564165a1ee694e5f46e22a`。使用原生 evaluator/COW 构建、官方解析和原生检查，完成后核对新二进制的全部 701 个源码哈希，再在相同输入、Tcl、时钟和最终约束下执行完整 TNS 对照。人工补回原机制属于兼容迁移，不冒称新 Student、源码演化成果或晋升。

## 重复实验的交付检查点

大设计 DF 导入等待使原 Ibex 重复链在第一次 15ps 修复后以 `import_outcome_unknown` 退出。其优化和物理计算成功，错误发生在事实交付，不能为此重新执行已完成动作。

`admin/repeat_native_strategy.py` 现在在原优化动作成功后调用既有 `delivery.checkpoint`，然后使用既有 `delivery.finish`。公共 CLI、EF/DF/DI 契约和原算法保持；`resume` 可以接续同一动作的资格测量与事实交付，保留原 EF 生产者身份。

针对性回归模拟事实交付中断，验证 ODB、原生产者、方法和 PDK 检查点已经持久保存，优化只派发一次。28 项重复/交付针对测试、608 项根回归、lint、格式及类型检查通过。

实际 Ibex 续作复用第一棒和第一次修复，继续真实第二次修复、独立第二次完整三动作协议，再汇总原值和均值。旧未完成的整体功能证明没有被宣称通过。

## 在途业务任务

| 任务 | 实际续作 | 验收边界 |
|---|---|---|
| GCD Nangate45 | 原 TNS 修复构建；相同完整协议的新源码对照；原 Flow 1×50 搜索；原 DPL 接力 | 失败分支保留；以最终 PPA/违反和对应功能证明为准 |
| Ibex ASAP7 | 从已完成的第一次修复接续，完成原三动作协议两次 | 物理通过与完整功能证明分别标注 |
| Ariane Nangate45 | 原 ORFS 计算复用、原 DF 交付恢复、Query 后启动带修复源码及新 AST 的原四 Student Goal | 保留 6ns、typical、SRAM、原 PPA 上限，不因准备完成称优化成功 |
| 其他既有任务 | 原 JPEG 两次接力/源码搜索、GCD 两次 DPL→Goal、Ariane ASAP7 参考和 ECO 保持 | 不重启健康计算、不取消等待中的原专业任务 |

Ariane ASAP7 第二次参考的 EF 为 `run-d05441469fa744d2856ec6c24de5aa12`。23:40 的实际日志表明其详细布线持续前进，并出现约19.4GB的中间内存峰值，32GiB 预约有实际依据；服务容量和资源规则未改。

另核查了 ECO 的 `reg2reg` 字符串：原 GCD 实际登记报告虽提示该组未知，仍返回 `core_clock` 的完整路径。因此没有据此修改 ECO 或取消原任务。Ariane 的具体路径覆盖需要以其本次真实会话为准。

## 修改文件与续作入口

- Goal 模块 `toolchain/patches/restore-original-tns-policy.patch` 和 README：原机制迁移补丁与精确基线。
- 根 `admin/repeat_native_strategy.py`、`admin/test_repeat_native_strategy.py`：重复优化动作完成后持久保存交付检查点及中断回归。
- `SOURCE_MANIFEST.json`、Goal gitlink：固定补丁资产版本；原运行 source/binary 身份继续各自留档。
- 本文、`TASKS.md`、`ARCHITECTURE.md`：当前边界和真实进度。

运行证据、补丁应用回执、新 AST、构建/续作 PID 及实际 EF 任务均在 `var/business/a30-four-design-two-pdk-20261021`。26 份保护文件逐 SHA 保持；用户的 DF/DI 与评测改动未触碰。
