# A25准备：真实阶段进度与双搜索并发读取

JPEG/GCD原完整搜索仍在运行，A7新目标下的标准完整验证仍等待资源。本检查点补齐状态封装与真实读取证据，不记新的PPA采用、完整搜索收尾或正式效率收益。

## 业务入口

现有`status --design <id>`在每个真实原生Flow实验附加`native_progress`，直接报告当前iteration、上次完成的阶段屏障、计划候选数和各阶段的准备/提交/排队/运行/终态计数。原`status`、`result`、`lifecycle`和`active_eda_jobs`字段继续提供。

原生检查点phase0表示上一个已提交屏障，实际place任务可能已经完成很多；现在调用者可以从实际任务状态区分这一点。EF任务成功也不代表整个实验交付、满足最终PPA或已采用，结果明确保留这条语义。

聚合只读本实验的原生账本和公开EF接口，按实际原生design别名、project、campaign、iteration、stage、candidate和slot核对。活跃任务分页读取；已完成任务使用原EF终态回执，刚结束但本地尚未投影的任务重查同一run handle，不提交新任务。反馈/导入回执不当作EDA任务，未提交原生iteration的scope不伪造进度。

同一命令的既有`lifecycle`现在也显示标准验证的`logic/jobs`、`replay/jobs`及`replay/imports`等待信息，仅扫描明确的运行命名空间，不递归扫描源码树。真实A7验证的`parse-gold`资源等待及其run ID已在该入口显示，不能把它说成验证成功或无人消费。

## 实际验收

- 九项Flow状态检查及一项嵌套验证检查通过：包括运行与屏障区分、同句柄终态竞态、跨campaign/candidate拒绝、分页、原生别名、无状态不查询、未提交iteration及反馈回执边界、原命令字段与嵌套等待。
- 首次真实JPEG状态读取暴露反馈文件类型混入、未提交scope缺iteration两处边界；原失败stdout/stderr保留，两项新测试修复前失败、修复后通过。嵌套验证缺失的测试也先失败再通过，没有通用异常吞掉或返回假进度。
- 新入口在实际JPEG/GCD目录读取通过，例：JPEG当时place为14成功/6失败/2运行/28排队，GCD为40成功/1运行/9排队；两者各50条、整体仍in_progress，原生屏障尚为0。数目是当时观察，后续以实时入口为准。
- 435项根回归及产品/新增文件Ruff、格式和Pyright通过；历史扩展测试的风格问题未改写为通过。用户26份文件hash保持。

权威入口记录：`var/business/a25-gcd-canonical-source-20261017/progress-entry-qualification/`中的`live-read-acceptance.json`及`nested-live-acceptance.json`。调用只读，没有更换服务、wheel、实验配置、原生算法或活动副本。

## 20分钟真实并发窗口

两条真实原生2×50搜索共享现有32GiB执行池时，完成1200.0003秒观察：60次health、60次GCD及60次JPEG固定来源七PPA/身份检查，合计180/180通过；20次实际campaign状态采样，未见本窗口内的lost记录，且确认两个campaign实际运行。

| 读取 | 最大观察耗时 |
|---|---:|
| EF health | 0.02567秒 |
| GCD七PPA/身份 | 0.29791秒 |
| JPEG七PPA/身份 | 0.10931秒 |

记录位于`dual-flow-observation/{summary,independent-acceptance}.json`及原始`samples.jsonl`。此结果覆盖该20分钟窗口，不代表完整搜索已经通过，也不替代此前A23的取消、真实失联、长写入/读并发检查。

另抽样各四个**最近成功完成**的place任务分解EF时间：GCD平均输入/启动0.104秒、extractor区间54.821秒、输出收尾0.818秒；JPEG分别0.115秒、277.194秒、11.406秒。排队另列，extractor区间也含adapter工作，不能直接当纯CPU时间；收尾含打包、产物托管与最终落盘，不能据此认定唯一I/O或网络原因。成功快样本不代表所有尝试，失败与未完成任务仍须计入完整预算。原始回执和拆分数据在`timing-decomposition/`。

## 文件与边界

- `chip_evolve/progress.py`：只读原生任务状态聚合，没有调度、推理、评分或采用逻辑。
- `chip_evolve/cli.py`：既有status结果附加进度，并显示已存在的嵌套验证等待回执。
- `admin/test_native_progress.py`：十项对应检查。
- 本报告、`PROJECT.md`、`ARCHITECTURE.md`、`TASKS.md`、`SOURCE_MANIFEST.json`与正式协议草案：登记接口语义、证据和未完成范围。

没有跨源码导入、内部数据库访问、新后台或通用Agent harness。完整专业健康轮次、实际接力、A25冻结及A26–A28的公平结果仍需推进。
