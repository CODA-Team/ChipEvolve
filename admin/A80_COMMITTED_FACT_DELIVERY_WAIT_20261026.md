# A80：定位数据导入耗时，修复已提交事实后的无效等待

基线根 `7f14e40`。本轮遵循具体诊断、具体修复、短验证及 code-check，没有 EDA、专业模型调用或 PPA 新结果。工程检查通过，老板业务验收独立。

## 找到了什么、实际解决了什么

A74 三事实交付约20分10秒，其中大对象导出21:48:19Z→21:52:08Z，后续对象导入及收尾占主要时间。22:03:56Z→22:04:50Z的进程采样显示约1.516GB逻辑读写和物理写入；当时持久导入回执已可读。不能把这些耗时笼统称为 HTTP 网络传输。

核查实际服务 PID3537663、43789端口、安装解释器及 `repository.py` 哈希，生产DF仍是原安装代码；当前受保护的DF/DI在途改动未启用、未修改。本轮通过EF公开artifact locator取得已有Ariane OpenDB包，按size/SHA验证，只提取有限真实行做私有性能诊断，不重做EDA。

确认的业务接点缺陷是：`import_snapshot` 先同步等待 `POST /snapshots/from-run`，直到响应或900秒socket超时后才去核对回执。SQLite可以在持久提交可见后继续checkpoint，原调用因此可能在“事实已经可用”时仍空等。

修复让原POST在一个有原超时约束的HTTP线程中等待响应；业务线程同时读取现有持久回执，核对producer/artifact/snapshot、再核对subject run与design，成功后交付。HTTP线程不写本地回执、不重试、不重新派发EDA。未知结果仍沿原reconcile/pending机制，真实拒绝与身份错误仍失败。未改公共签名、HTTP路径、数据结构或数据库。

这解决的是**已提交后的调用侧空等**，不消除大对象的解析、写入、落盘成本，也不保证下一条写请求绕过DF原写锁。没有宣称生产20分钟问题全部消失。

## 有限真实行测量：不靠关闭持久化制造速度

来源EF `run-8e00480e0bfa43b5b056cb96340948cf`、artifact `art-7d638bbb35024f0da1f64bb661e80266`，131523527字节、SHA `02f8956ab2119eb3e7a9f76058d31ad4b50c1587288ddb4bbb196e62cd39096f`。选取20000对象、20000关系、20000物理记录，两个私有数据库各约82.44MB，使用实际安装版DF和相同WAL/FULL。

| 私有诊断条件 | register秒 | 事务退出秒 | 额外显式checkpoint秒 |
|---|---:|---:|---:|
| 原SQLite自动checkpoint，1000页阈值 | 5.214 | 2.259 | <0.001 |
| 仅诊断对照：延后checkpoint | 3.779 | 0.770 | 0.876 |

该单次、固定顺序的小样本受缓存与磁盘负载影响，不外推生产改善比例。它证明提交/收尾成本不可忽略，延后后仍需做checkpoint；**未将禁用自动checkpoint作为产品修复**，生产持久化及WAL配置保持。

样本是截取的不完整设计，只用于定位导入阶段；没有作为公开完整设计事实或PPA实验数据导入生产。原完整产物和旧快照保持。

## 短验证与门禁

新增两项真实HTTP回归在旧源码均失败：服务已提交但扣住POST响应时，旧入口仍等待；修复后能返回正确结果，错误subject仍立即拒绝。既有超时、响应丢失、重入、服务不可用、400拒绝、错误producer等分支全部通过。

进一步用**实际安装版DF Handler/DataStore/ReadPool + 真实EF已登记metadata包 + 实际DI SDK**做隔离HTTP验证：

- 私有新库WAL/FULL真实提交后，刻意扣住事务退出/响应边界；未改变生产服务、生产库或原包。
- 在gate未释放、POST尚未返回时，入口约0.094秒核对回执与快照并返回；DI SDK读取power **0.1604765951633W**，与A79原件一致。
- producer `run-ae27152a35134bc58b2a04a1b9fd2aab`，artifact `art-7584c903f70c4b16b792163e157f0da8`，subject为A79真实native run；attempts=1，重入返回相同结果，无重复导入。
- 该响应延迟是人工控制的验证条件，0.094秒不是生产大设计加速成绩。验证服务已关闭，私有库保留为证据。

根项目完整回归 **742 passed**，其中delivery针对 **25 passed**。产品与私有驱动Ruff、格式、Pyright通过；测试文件已有6项mock类型诊断与基线逐条相同，新增0项，不将既有诊断伪报为全文件类型零错误。第一次私有驱动未识别zip根目录文件、SDK不在DF环境等诊断脚本问题已纠正，未引发EDA或生产修改。

AST核对除 `import_snapshot` 外所有根delivery函数/类相同。26份用户文件和DF/DI WIP哈希保持，安装DF源码哈希保持，EF活动队列0；未引入服务框架或存储迁移。

## 改动文件与后续

| 文件 | 职责 |
|---|---|
| `chip_evolve/delivery.py` | 让当前import等待期间即可核对已提交事实，保留原身份与恢复规则。 |
| `admin/test_delivery_lifecycle.py` | 增加真实HTTP响应扣留控制及正确/错误subject两项回归，保留原分支测试。 |
| 本报告、`admin/STATUS.md`、A54总表、`TASKS.md`、`ARCHITECTURE.md` | 记录具体修复及仍未消除的实际入库成本。 |

证据 `var/business/a80-df-import-latency-20261026/`：`profile-result.json`、两份cProfile、`sample-identity.json`、`real-HTTP-verification.json`、`test-pyright-delta.json`、`code-check.json`及`continuation.json`。

下一项核查Ibex/Nangate45未完成的功能证明：先查精确来源、原任务终态及失败原因，再决定必要的有界验证。Ariane最终电气/功耗、ASAP7闭合、500ps协作、八组双次，以及生产大库写入/checkpoint成本仍未完成，长专业搜索继续暂停，总目标保持进行中。
