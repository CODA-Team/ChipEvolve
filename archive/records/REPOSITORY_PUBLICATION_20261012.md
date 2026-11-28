# ChipEvolve 仓库发布与旧项目归档

老板于 2026-10-12 明确要求把当前平台推送到 `CODA-Team/ChipEvolve`，将原项目归档至 `discarded/`，以当前平台作为仓库主体。本次操作只调整仓库发布与文档，不实施 U1 工具迁移或专业 Agent 接入。

## 发布结构

- 默认分支保持 `main`，仓库保持 private。
- 根内容来自工作区已提交检查点 `45f817a3a1c416617c068db3daf6016f09227231`，补充正确的项目 README、Git 子模块配置、运行数据忽略规则、来源 manifest 和本记录。
- 旧版 HEAD `5219cd94a92de649afd25367ebf4df5517acf69d` 的整个根 tree 放到 `discarded/`。466 个已跟踪文件的内容、相对结构、文件模式和链接不变；旧 `.github` 也在归档内，不作为当前 CI。
- 新提交保留本机根提交及旧远程提交为父代，两边历史均保留，不 force-push。旧版另保留 `archive/pre-platform-20261012` tag。
- 八个项目都是固定 commit 的 Git 子模块，保持原有独立 Git 和运行边界。六个自有模块完整已提交历史存入本仓库的 `modules/<目录名>` 分支，Code 项目引用已核实的官方上游提交。

| 模块 | 固定提交 | 存储位置 |
|---|---|---|
| Execution Foundation | `d0302c113cd2c786caac621b5afa23a3ca63512a` | ChipEvolve `modules/execution-foundation` |
| Data Foundation | `b29e5a90b1819f63f62e2f02fc43aaa8f2596b42` | ChipEvolve `modules/data-foundation` |
| Data Interface | `4f2e195c05bfe80a72b557985d9577206efe9d9b` | ChipEvolve `modules/data-interface` |
| Query Agent | `b6910d06f522c093b0a2133225ab7d4079e2e097` | ChipEvolve `modules/query-agent` |
| Toolkits | `39f48a478ce1f4bfacfe6a81773bdab54bd8f873` | ChipEvolve `modules/toolkits` |
| Flow Agent | `a90bd07e304e2572fbd3e201809d93d6e50cbe1c` | ChipEvolve `modules/flow-agent` |
| DPLEvolve | `96d8c613d62bf3431083bb5e52c7df8853d5a622` | CODA-Team/DPLEvolve |
| GoalEvolve | `1cc20aa611e687c2745ff7da6a006a5d25f49f85` | CODA-Team/GoalEvolve |

## 本机修改与运行现场

根仓库既有 `admin/evaluation` 修改/未跟踪文件，以及 DF/DI 未提交修改，留在原工作区，未被覆盖或混入发布。源码发布使用上表的已提交检查点；运行中的服务、数据库和专业实验没有迁移或重启。

wheelhouse、虚拟环境、SIF、数据库和运行根 `var/` 不上传；模块原来已提交的研究输入/测试资产和各自许可证保留。DPLEvolve、GoalEvolve 原研究远程没有写入或修改。

## 核查方法

```bash
# 旧项目必须逐字节保留：两个命令的输出应相同。
git rev-parse HEAD:discarded
git rev-parse archive/pre-platform-20261012^{tree}

# 检查根仓库固定的八个模块版本。
git ls-tree HEAD execution-foundation data-foundation data-interface query-agent toolkits flow-agent dplevolve goalevolve
git submodule status

# 查看当前平台与原项目的保留历史。
git log -1 --format='%H %P %s'
```

还需核对远程 main/tag/六个模块分支、gitlink 与 SOURCE_MANIFEST 一致、源文件 hash/模式没有意外变化，以及未提交本机文件仍在原位。本次没有业务逻辑变化，验证以 Git tree/来源、发布差异及子模块获取检查为主；不把仓库推送成功当作 U1、L3 或协同 workflow 的工程验收通过。

本机发布操作/传输/核查回执位于 `var/publication/chipevolve-20261012/`，不纳入远程仓库。
