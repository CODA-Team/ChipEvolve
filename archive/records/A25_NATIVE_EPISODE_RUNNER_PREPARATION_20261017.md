# A25准备：原生调用记录与相同执行条件

这是A23–A28已授权计划的准备检查点，A25尚未冻结，A26/A27未启动。A24的JPEG完整证明、完整专业轮次及预算校准继续进行；不能用本文的入口检查代替它们。

## 实际问题与结果

原生Codex的文件/HTTP成功不足以证明可以执行EDA。实际在`workspace-write`中启动同一个Apptainer镜像时，OpenROAD版本命令返回255，FUSE挂载失败；同账号普通执行的两条版本命令均成功。保持原失败证据后，另用显式的单次`danger-full-access`配置启动原生Codex，两条原样版本命令均返回0，输出与同账号普通执行逐字相同。

这个配置只使用已有账号权限，没有sudo、驱动加载、系统目录写入、服务调整或全局Codex配置修改。正式两侧须使用相同的实际权限；不能一边允许EF在沙箱外执行，另一边因容器挂载限制失败，再把差异算成平台收益。它也不证明完整设计实验、原专业运行和恢复已经通过；这些仍待实际任务资格与正式冻结。

OpenROAD本次实际版本字符串为`unknown`，Yosys为`0.68+post`且Git SHA也是`UNKNOWN`。原输出保留，源码身份继续依靠此前冻结的镜像、源码与二进制证据，不能从字符串补造提交号。

第一份检查schema把未尝试的Yosys退出码规定为整数，模型虽在备注说明未执行，仍填了255。独立验收明确记录`yosys_attempted=false`、退出码为null，并判本次启动资格失败。后一次schema允许null；没有回写首份答案。

证据位于`var/business/a25-formal-preparation-20261017/`：

| 目录或文件 | 含义 |
|---|---|
| `native-codex-container-startup/` | 原沙箱真实失败、原生事件、用量及独立失败验收 |
| `same-account-container-startup/` | 普通同账号的两条实际版本命令 |
| `native-codex-account-startup/` | 显式共同配置下的原生Codex真实成功及独立核对 |
| `preparation-costs-r2.json` | 保留旧快照、包含失败的新增成本快照 |
| `canonical-jpeg-timing-context-observation.json` | 旧参考时序上下文缺失的公开SDK观察 |

三个准备阶段原生调用累计已知输入172,059、输出1,439，输入内缓存117,888。主Codex推理及其他准备成本仍未知，这不是完整总成本，也不支持效率优势。原失败和只读补核只算一次模型调用；所有检查都不是正式episode。

## 文件与数据流

- `admin/run_native_codex_episode.py`：只启动一次现有原生Codex，通过stdin及EOF传提示，分开保存JSONL与stderr，校验固定输入，记录原始用量和最终消息；真正超时复用既有原生子树收尾。没有模型API、推理循环、工具分发或新服务。私有试验spec不是公共EF/DF/SDK契约。
- `admin/test_native_codex_episode.py`：核对缓存不重复计费、完整/未知用量、多轮收据、损坏记录、超时、输入变化、不可覆盖重复尝试及显式共同配置。测试替身只验证记录逻辑，真实启动资格另有上述原生事件。
- 本报告、`TASKS.md`、`ARCHITECTURE.md`与`SOURCE_MANIFEST.json`：记录本次准备、边界和源码基线；九模块gitlink不变。

```mermaid
flowchart LR
  S[冻结前试验输入与模型设置] --> R[单次启动与记录脚本]
  R --> C[现有原生Codex]
  C --> T[原生命令与既有专业能力]
  C --> E[事件 原用量 最终消息]
  T --> V[独立事实与产物核验]
  E --> V
```

脚本的`native_completed`只说明该原生调用完整结束，业务正确性始终要求独立核验。本次FUSE失败时，原生Codex诚实报告失败，CLI仍正常结束；独立核验据实际工具退出判失败，不能仅看CLI退出0。

现实现执行墙钟期限，累计token只测量，没有跨专业调用的硬token上限。正式预算须明确这一点，不把收尾才取得的用量当作事前限额；缓存是输入子集，缺失或中断用量为未知，并保留可知下界。超时收尾只处理原生前端树；独立EF任务仍需依照原公共取消/恢复规则核验终态，不能据前端退出推断EDA结束。

## 数据补充与验证边界

公开SDK确认JPEG原参考的首五条setup路径均缺少analysis/corner/unit。已准备新STA导出脚本，复用原ODB/SPEF/SDC/库，新建补充快照并核对原路径事实；不改旧快照、原结果或PPA。它在当前完整证明结束、Flow通过空队列预检后，接在GCD/AES独立PDR复核之后执行。等待器只触发既定检查，不新增专业搜索；初次直接运行var脚本的导入错误在任何EDA启动前发生，已单独保留，改用根工作目录的runpy入口，没有PYTHONPATH或跨源码导入。

本次新增12项针对检查通过；根业务回归、产品及新增文件Ruff/格式/Pyright检查见运行资产`runner-engineering-checks.json`。额外把全部历史测试文件也纳入Ruff时发现8条已有风格问题，涉及六份旧测试，原样保留；不能称该扩展检查通过。本次没有更改公共模块边界、活跃证明/Flow配置或26份受保护的用户文件。

官方依据：[OpenAI Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)说明原生JSONL、stdin、结构化输出及单次权限配置。这里只沿用其现有执行入口，不新增通用Agent harness或评测服务。
