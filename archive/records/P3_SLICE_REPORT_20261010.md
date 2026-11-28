# P3 本轮收尾与暂停汇报

老板视角：真实优化器已跑通，平台已能管理真实物理阶段、取消任务、统一保存和查询结果。本轮补齐“同一实验继续跑”的实现和自动评价回流接线；完整真实中断恢复尚未验收，所以目前还不能对用户承诺稳定续跑或自主端到端优化。

## 已证明的效果

| 业务需求 | 当前证据与结论 |
|---|---|
| 专业优化器真实工作 | P1 同一实验两轮三候选完成，参数被工具实际消费，物理产物完整。 |
| 优化效果可核对 | 固定 CP0 / 功耗条件下单次最优 TNS 绝对值降低约 5.73%；公平平台收益仍未证明。 |
| 执行统一管理 | P2 真实 place→CTS→route→eval、实际路由取消和资源释放通过。 |
| 数据统一、来源可查 | P2 实体/关系/指标导入、重复导入、重启持久性和 SDK 来源字节通过。 |
| 中断后不浪费已完成工作 | 本轮代码与模拟边界检查通过；完整真实实验待老板运行验证。 |
| Codex 自主查询并优化 | P4 尚未实现真正 Flow receiver 和完整业务闭环。 |
| 为什么变好/变差 | Query 已有事实查证、比较与引用；完整归因/因果能力尚未业务验收。 |
| 源码优化 / 教学交付 | DPLEvolve / GoalEvolve 接入、公平对照、干净安装、Tutorial / 论文材料待后续切片。 |

## 当前代码如何工作

原生 A2 继续生成、排序与继承候选；单候选物理任务通过公共 EF wheel/HTTP 执行，注册产物按实际 donor 和 ODB/SDC hash 投影回原生路径。

每个原生阶段提交后保存小状态 archive 与 EF 产物引用。恢复显式使用 `--resume`，核对同一实验和冻结条件，恢复最后提交点；未提交 DRP 先还原输入再重做，已完成模型响应按完整请求 hash 复用原 call_id、工具决策和实际用量。没有 durable response 的中断保留未知用量和原生回退，不伪造零成本。

真实固定 CP0 评价的 metadata 通过既有 Toolkits ORFS adapter 导出，再通过 DF HTTP 指定产物导入；保留物理 run、评价 run、metadata artifact 与 hash。数据事实由 Codex 判断，未新增评测底座。

## 本轮逐文件差异审查

基线：Flow `38548ee`，workspace `962acd3`。原有 workspace evaluation 和 DF 用户修改保留，不纳入提交。Flow 在独立 `p3-resume-20261010` 分支保存实现检查点，标题注明待业务验收。

| 文件 | 改动职责 / 影响面 |
|---|---|
| flow-agent/flow/platform_campaign.py | 原生 phase 0–7 提交、同 campaign 恢复、冻结身份和产物引用；不复制大型物理产物进 journal。 |
| flow-agent/flow/platform_model.py | 保存真实模型响应，恢复账本窗口与复用成功决策；限定本次实验。 |
| flow-agent/flow/platform_feedback.py | 真实评价 metadata 导出和指定产物导入，复用公开契约。 |
| flow-agent/flow/maindriver.sh | 增加 opt-in 平台恢复入口、阶段提交/跳过；共享主驱动，原生模式仍走原流程。 |
| flow-agent/flow/common.py | 共享模型 wrapper 接入 durable completion；原生传输语义保留。 |
| flow-agent/flow/optimize_agentic.py | 跨轮模型 wrapper 使用同一 completion helper；候选生成算法保持。 |
| flow-agent/flow/llm_usage.py | 平台 request_started 附加进程身份；原有账本 schema 与计量语义保留。 |
| flow-agent/flow/llm_client.py | 平台下保存 Codex 独立 session 的身份，避免中断掩盖活跃模型子进程。 |
| flow-agent/flow/platform_execution.py | 显式实测提交受理后、run_id 落盘前的可选中断 gate。 |
| flow-agent/flow/platform_leaf.py | 实际评价成功后调用回流；物理任务接点不变。 |
| flow-agent/flow/test/test_platform_resume.py | 原响应重放、账本窗口、未知用量、真实 archive 引用恢复等模拟边界。 |
| flow-agent/flow/test/test_platform_feedback.py | 回流幂等、实际 metadata hash、物理 lineage、失败响应保留等边界。 |
| flow-agent/RUNNING.md | 运行配置、恢复入口、数据回流及实测限制。 |
| admin/run_platform_campaign.py | 独立完整两轮三候选验收入口，真实四个中断 gate；尚未运行，不自动签署 P3 验收。 |
| PROJECT.md | 老板确认的产品能力、三项工程问题及 Codex 分工。 |
| ARCHITECTURE.md | 现有模块边界、依赖与数据流，标出未交付接点。 |
| TASKS.md | 切片状态、前置、业务标准与暂停位置。 |
| AGENTS.md | 新协作协议：计划确认、切片边界、工程门禁和用户验证。 |
| admin/STATUS.md | 最新状态改为等待 P3 验证并按老板要求暂停。 |
| admin/P3_SLICE_REPORT_20261010.md | 本汇报、逐文件审查与验证交接。 |

## 工程检查与验收区别

现有 Flow 回归加新增对应检查共 **47 passed**，依赖 `pip check` 通过。新增模块和验收入口的 lint、类型、格式检查通过，共享 shell 语法和差异空白检查通过。原生历史代码没有为了本切片做全量格式/类型重写；新增模块的检查不代表整个历史源码已经通过新的全量静态标准。

日志及对应命令在 `var/flow-agent/p3-resume-preparation-20261010`；状态回执明确 `p3_accepted=false`、`real_campaign_started=false`。早期检查出现测试 fixture 缺 `kind` 以及类型错误，已修正；最终完整回归为 47 项通过，不降低真实验收标准。

架构审查：没有访问 sibling 源码或私有数据库、没有跨项目 PYTHONPATH/sys.path 接线；Flow 使用已安装公共 EF wheel，Toolkits/DF 沿用原有任务/API；未修改 Query、EF、DF、SDK、Toolkits 的实现或公共契约。

## 交给老板的真实验证入口

按新协议由老板运行验证。本轮未启动下列长时间实验，避免暂停后继续后台施工。它保持两轮三候选、真实 Codex、`-A -P`、固定 CP0 / 功耗、物理并发一 / 八线程及三小时总预算，单次原生参考约需两小时。

```bash
cd /home/wjyuan/projects/eda-development
execution-foundation/.venv/bin/python admin/run_platform_campaign.py prepare \
  --run-root /home/wjyuan/projects/eda-development/var/flow-agent/p3-platform-campaign-20261010
execution-foundation/.venv/bin/python admin/run_platform_campaign.py supervise \
  --run-root /home/wjyuan/projects/eda-development/var/flow-agent/p3-platform-campaign-20261010
```

程序检查的四个实际窗口为：提交已受理但本地未保存 run_id、真实模型响应已保存但 DRP 未提交、DRP 阶段提交后、第一轮全部提交后跨轮恢复。程序正常结束只是实验运行结果，仍需核对四次中断前后原 run_id/产物 hash/模型 call_id、不重复计成本、两轮完整产物和 SDK 真实评价来源，老板确认后才记 P3 通过。

如发现失败，仅在 P3 内修复，保留原失败目录、不开 P4。若要由工程师代跑这次验证，需老板在暂停后明确继续此切片。

## 对新材料的结论

采用“三个工程问题：可复现性、统一性、可观测性与归因”。实现组织是 **两项基础设施 + Query Agent**，Data Interface 是 SDK；不采用“三个底座 + 一个 Query-Agent”的矛盾计数。

Query 的目标包括“为什么”，但相关性对比和已知证据不自动等于已证明因果；后续验收应明确受控对比和归因证据。论文不能声称 ECO 和 Code 已交付。文中 Reset 的调参职责映射现有 Flow，不擅自改名。Codex 负责全局判断与决策，API 保留为专业项目内部的可选实现细节。

## 三句话交接

1. 本轮改动集中在 Flow 的阶段恢复、模型响应复用与真实数据回流，并补齐对应检查、验收入口和协作文档；完整文件职责见上表。
2. 原生 A2 → 公共 EF 任务 → Toolkits 真实工具/评价 → DF 指定产物导入 → SDK/Query 提供事实与证据 → Codex 判断；Query→Flow 的真正自主接收器留待 P4。
3. 改续跑行为看 platform_campaign，改模型响应复用看 platform_model，改评价回流看 platform_feedback，改优化策略仍看原生 A2；新的模块边界/接口/升级先由老板确认。
