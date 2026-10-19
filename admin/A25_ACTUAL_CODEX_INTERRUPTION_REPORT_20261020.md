# A25：真实 Codex 启动原生 GCD 的中断收尾资格

本轮补齐此前传输夹具验证的一项限制：实际调用原生 Codex，启动原 ORFS GCD 命令，并在真实物理阶段中断本次记录器。独立核查通过；A25仍未冻结，A26/A27正式试次与A28未完成。

## 实际业务与结果

采用已通过工程门禁的组合根09f95a5，不切换活动根或服务。实际Node/JS/传递调用原生二进制及两份package元数据共五个指纹与已有CLI0.159.3记录一致；请求模型gpt-6.1-sol/medium，服务端模型快照未知。真实events含turn.started与原生工具命令；不是替代传输夹具或零模型调用。

Codex使用普通Python启动器复制原输入、启动持久worker并观察日志。原ORFS命令只重定位私有输出目录与实验key，EDA参数不变；全部staged文件及design.mk与原件同SHA。启动器是本次预先提供的普通脚本，用于显式登记worker身份，不据此宣称任意脱离进程均可自动发现。

观察器发现真实2_1_floorplan.tmp.log后向本次记录器发SIGINT；日志已经出现OpenROAD启动、8线程及read_liberty。该注入点是物理阶段刚开始加载库，不是floorplan完成。记录器保留interrupted，未将其误标为PPA失败或完整业务成功。

- 整个记录器墙钟19.6452秒；worker收尾约0.1572秒，包含在前者内。
- 前端树3个进程、显式worker及捕获后代10个，共13个PID/start ticks逐个独立复核，无同一存活身份。
- 实际覆盖了重挂到PID1的worker；原EF3936549和DF3537663身份保持，26份受保护用户文件保持。
- 一次实际原生Codex调用、一次实际EDA启动。回合被中断，turn.completed为0，完整模型usage为null；已知用量下界为0不等于实际费用为0。

证据在var/business/a25-native-codex-interruption-20261020：episode-specification.json、episode/invocation.json、episode/events.jsonl、episode/receipt.json、injection.json、receipt.json及independent-acceptance.json。独立核对原始事件中的真实启动命令、实际工具命令、五个后端指纹、34份固定输入、全部13个终态身份及原阶段日志；没有只凭汇总passed字段判定成功。

## 范围与成本

该运行属于正式直接侧停止方式的开发资格。生产专业实验仍经过EF；本次直接执行是已授权对照的资格验证，不是新增生产绕行入口。未完成完整RTL到GDS、恢复业务或正式A27效率比较，也不产生PPA改善率。

沿用原记录器的进程CPU观察范围：runner user/system约0.26/0.11秒，已回收前端树user/system约1.85/2.95秒。脱离树的实际EDA CPU不在完整回收计数中，保留unknown_not_zero，不与EF采样CPU叠加。模型完整token及远端计算未知；主Codex、服务和准备/测试成本亦不冒称为零。

新增私有qualification脚本通过Ruff F/I、格式及实际client解释器Pyright；早期格式/一项可空类型诊断保留并已修正。没有产品代码变化，不重复此前组合根564项回归；真实工具及独立身份核验是本次验证依据。既有活动输入、专业源码、EF/DF/DI和受保护评测代码未修改或部署。

## 后续门槛

兼容修复最终OpenROAD链接已实际开始，原构建2674189与故障回放2691230继续；只有最终链接注册二进制与新SHA核验后，才能评价原崩溃回归，不能用此前成功编译/静态归档的旧二进制留存替代。已准备私有独立构建核查脚本，尚未将待完成的构建记为通过。

完整JPEG2×50、五组策略共同最终物理、AES129输出证明、原生完整专业参考与真实Flow→Query→Goal接力仍须完成并核验。正式runtime/专业源码/AST/EPD/模型/来源/冷热准备及两侧停止方式还要绑定冻结；本次收尾资格不能代替其余门槛。

主根文件清单：本报告保存真实资格及限制；TASKS.md记录A25新增已验证项与未完成项。私有脚本/模型事件/运行产物留var，未发布运行数据。

## 同轮后续：链接成功未形成新二进制

最终链接随后成功，但独立SHA仍为旧父项c2ff1adc…。已定位gcc-ar-11未被旧静态库清理逻辑识别、保留重复对象的问题；该构建未通过候选生效验收，原回放已公开取消。修复分支d5a3a95完成工程门禁并进入真实r3重建。原未派发的完整专业参考/接力守候者已收尾，需用合格来源重新绑定；真实Codex中断资格本身保持通过。具体范围、历史归因限制和继续入口见[A25归档器核查](A25_GCC_AR_ARCHIVE_REPORT_20261020.md)。
