# A25：私有构建的资源预约与并发资格

新发现的效率瓶颈来自平台配置：三次成功的DPL私有候选构建，进程树内存峰值分别为4,896,727,040、4,921,700,352、4,897,959,936 bytes，却各自预约32GiB，恰好占满当前执行池。第二个Student的构建、先完成Student的布局评价因此等待。执行底座是在按约定调度，没有卡死；预约粒度需要区分完整工具构建与私有重链接。

## 改动和边界

隔离DPL候选97466b0在原线程预约候选8940667上增加一个私有配置接点：已有profile.resources先查操作同名项，没有则仍按build/physical回退。可以只为variant_build设置资源，而不改变完整构建和其他操作。显式原生线程数仍参与CPU预约的较大值计算，原CLI、算法、线程选择、时限和公共EF接口不变。

文件清单：scripts/platform/execution.py选择已有资源映射；validation/test_platform_execution.py新增四种操作的覆盖与回退检查。新增场景修复前仅variant_build失败，修复后validation全部47项通过，Ruff F/格式/差异及生产文件Pyright basic零错误/警告。候选已发布到ChipEvolve的modules/dplevolve-a25-operation-resources，主DPL和当前r7均未切换。

没有建立新资源管理器或新Agent harness。数据流仍是原Code helper→私有profile→公开EF TaskSpec→原产物→DF/SDK。配置由平台准备，专业Agent继续使用原构建与评价命令。

## 已验证与尚未验证

用真实89份框架源码构造实际request、TaskSpec和容器命令，确认10线程请求预约10核/16GiB，完整构建的默认32GiB保持，原5400秒叶任务期限、单次attempt和只读共同源码绑定保持。只做公开SDK读取及命令组装，没有启动构建或模型。

16GiB约为上述单任务采样峰值的3.49倍，只是待资格验证的私有重链接配置；不能据此保证所有新源码的峰值，更不能套用于完整/冷构建。当前r7仍使用原32GiB预约，历史费用和排队不回写。

## 真实资格验证已排队等待

PID4045467当前只等待既有r7及JPEG超时证据交付成功；随后还须确认前序监督已退出、公开EF空闲及全部输入哈希不变，才执行：

1. 将同一89文件框架各冻结一份到私有目录，用原delegate入口提交两份10线程/16GiB构建。要求两份实际成功、各只执行一次，公开EF的开始/结束区间真实重叠，CPU预约均为10核；同时保留整个构建/排队观察轨迹。
2. 将这两份构建产物分别交给已有DPL业务replay入口；保留原8线程物理评价、共同工具链、三条原基线、完整CTS/DRT/RCX及公共数据交付。没有Teacher/Student新搜索或模型调用。
3. 核验私有框架的原生HPWL与原框架控制相同，两份最终七PPA和DRC一致、布局合法、源码身份/EF产物及DF/SDK事实对应，按run/attempt去重记录已知费用。它验证资源接点和真实业务可用性，不宣称新PPA收益、功能证明或采用。

前序失败时本探针停止在诊断，不插入EDA、不重复搜索。构建沿用原单任务5400秒；两份构建监督和后续两份业务重放分别显式设4小时窗口，等待前序的窗口96小时。不会延长原JPEG/r7的预算。暂时观察读取失败只记录后继续观察同一进程，不把一次读超时判作实验终止。

当前状态是waiting_existing_delivery，尚未发起上述EDA。准备时先采用业务入口直接8线程重建的草案已归档，最终方案改用原native10线程构建，再交付预构建产物给业务replay，避免重复编译并贴合Student实际线程数。

## 后续决定

本候选不在先前已固定的自动启用清单内；原衔接程序仍只启用8940667，没有热改其方案。实际并发资格通过后，才将97466b0合入主DPL、更新根来源清单，并为未来实验选择和冻结资源策略。失败则基于原回执修正这一接点，不能用测试通过或理论并发数代替实测。

验收和续接：var/business/a25-dpl-operation-resources-20261018/acceptance.json、resource-calibration.json、request-preview-acceptance.json、qualification-specification.json、qualification-receipt.json。当前26份用户文件、r7的68份输入及前序衔接器输入全部保持。原DPL轮次继续：截至19:41，12项EF任务中11成功/1候选源码编译失败，第二次修正构建和两份后续布局评价已成功；Teacher计划完成，两个Student仍在原生收尾，第三Student/review和整轮交付未完成。
