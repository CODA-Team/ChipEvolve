# A25准备：修正基线后的GCD完整来源与分支核查

JPEG原完整搜索保持运行。本轮补齐GCD的规范时钟来源/环境与分支事实，原生完整调参预演另行记录；A25公平协议仍未冻结，本文不记正式协同收益。

## 新来源与原能力

以已复验的显式310ps约束和新ORFS控制目标建立完整Yosys来源。采用原`SYNTH_USE_SYN=0`、`SYNTH_HIERARCHICAL=0`起点与全部原placement/CTS/routing参数，层次化旋钮仍可搜索；两个ASAP7路由hook按既有已注册通用脚本逐字节复制，没有GCD网名/路径补丁。源码、库与共同工具链保持。

真实完整来源完成综合至详细布线/finish；原Make展开确认CORE_UTILIZATION=65及所有原旋钮均有明确值。复制到原生控制器后，三阶段继承与七PPA逐值相同，EF→DF→SDK核对通过；对正确ORFS参考的全18输出、整体1分区PDR通过。环境ID为`fd48a23880dfd9bad0f07509fb3145d7e917d7bea1ccbb7a9d631547d341ef41`，新配置`runtime/local-qualified-r1.json`，没有改旧GCD/JPEG配置。

权威记录：`var/business/a25-gcd-canonical-source-20261017/source-qualification-process.json`，含新目标、复制比较、证明、环境和原文件hash。资格通过只表示可复现执行和完整功能一致，不表示当前来源已经满足全部PPA约束。

## 同新条件下的实际事实

| 分支 | 功耗mW | 单元面积µm² | 新对照不退化约束 |
|---|---:|---:|---|
| 正确时钟ORFS控制 | 1.373553765 | 42.6757 | 可行参考 |
| 完整Yosys来源 | 0.8922633715 | 44.8918 | 面积超限；不采用 |
| 历史A7时序闭合分支，重新实际测量 | 1.1775331805 | 40.27 | 全部通过；新18输出PDR通过，未新采用 |
| 历史A21低功耗分支，重新实际测量 | 0.88475551456 | 44.5419 | 面积超限；不能作为新条件下已达标最低功耗 |

两条历史分支均由EF读取原实际ODB/SPEF，在规范SDC和新目标下重新测量，七PPA与各自原共同测量逐值相同，新三快照/SDK通过；原实验、目标、决定与证据不改写。A7新证明为`run-99e657b52fa14a758232b4fd86c246d7`。历史分支此次没有新增独立布线重放或采用决定，不把它们当作正式搜索结果或仅给团队的额外初始来源。

`historical-portfolio-recheck.json`保留上述两条新观察与旧原件关系。规范来源当前setup slack为11.6169ps，setup/hold TNS、电气、布局及原生router DRC为0，失败的是单元面积上限。查询包`query-flow-context/professional-context.json`含1条去重事实与1条明确possible假设，范围与实际来源run一致；现有专业加载器接受。当前Codex给出host动作，没有新增Query内部模型或EDA分析。

这说明来源路线对功耗有显著影响，也说明最低功耗与整体可行并不等价。正式表必须将传统ORFS、完整来源、专业单项和协同分开；旧基线的改善比例不能移作新基线成绩。下一次完整Flow保留原域/评分/阶段继承，最终是否满足新全局约束仍由Codex依事实判断。

## 资源与文件边界

`chip_evolve/flow_recipe.py`的原复制资格检查现在复用`designs.<id>.orfs_execution.memory_gib`，与原生ORFS预约一致，未声明仍24GiB；三阶段算法、八线程、输入和任务身份不变。只有本轮新GCD来源明确预约8GiB，JPEG活跃12GiB任务及Code构建配置保持。此声明已进入原设计环境身份，不根据输赢临时加资源。

`admin/test_orfs_resource_binding.py`新增旧默认与显式8GiB的入口检查，显式情况修复前失败、修复后通过；30项相关检查、425项根回归及产品/新增文件Ruff、格式和Pyright通过。历史扩展根测试的风格问题不改写为已通过。

本检查点文件：上述资格实现、测试、本报告，以及`PROJECT.md`、`ARCHITECTURE.md`、`TASKS.md`、`SOURCE_MANIFEST.json`和正式协议草案。没有新后台、通用harness、公共SDK或评测服务；用户26份文件保持。

实际EF运行与资源回执位于`qualification-costs.json`，模型/成本未知值保留。本轮来源准备与历史分支核查均不是正式计时试次；GCD/JPEG并发时的排队必须独立记录，不能用受争用的墙钟代替专业固有成本。
