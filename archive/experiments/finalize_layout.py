"""Write project-specific entry points after extraction."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
ef = ROOT / 'execution-foundation'
df = ROOT / 'data-foundation'
sdk = ROOT / 'data-interface'
query = ROOT / 'query-agent'


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


write(ef / 'README.md', '''# Execution Foundation

独立执行平台：管理执行生命周期、工作空间、资源、原始产物、身份和溯源。
领域解析器仍在 plugins，kernel 只使用公共契约。架构约束见 AGENTS.md。

Data Foundation 和 Query Agent 已移出本仓库；接口 SDK 归 Data Interface。
项目通过 contracts/client wheel 和公开 HTTP API 交互。这里不安装其他项目源码。
独立 Query Agent 是上层主实现；原 apps/query_agent 代码留在迁移前基线。

使用自己的 .venv。统一入口从上级工作区执行：

```bash
python3 dev.py execution-foundation check
python3 dev.py execution-foundation serve
```

`serve` 只在 127.0.0.1:18700 启动开发 gateway；`tools/start-platform.sh`
在新状态目录启动 gateway、worker 和 plan executor（18840），不会接入旧数据库。
跨项目/论文验收测试的迁移归属见上级 admin/migration-manifest.json。
kernel、plugin、gateway 和 guardrails 原始实现及门禁完整保留。

共享依赖 wheel 由上级 admin/bootstrap.py 构建；消费项目安装发布产物，不能使用
跨项目 PYTHONPATH。原始提交与过滤历史映射见 MIGRATION_SOURCE.json 和
.git/filter-repo/commit-map。这里只使用迁移主分支，不是旧实验 worktree。
''')
write(ef / 'tools/start-platform.sh', '''#!/usr/bin/env bash
set -euo pipefail
platform_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
platform_venv="$platform_root/.venv"
state_root="${OPENROAD_PLATFORM_STATE_ROOT:-$platform_root/../var/execution-foundation}"
plugins_root="${OPENROAD_PLATFORM_PLUGINS_ROOT:-$platform_root/plugins}"
admissions_root="${OPENROAD_PLATFORM_ADMISSIONS_ROOT:-$platform_root/admissions}"
export PYTHONNOUSERSITE=1
unset PYTHONPATH PYTHONHOME
export NO_PROXY="127.0.0.1,localhost,::1"
export no_proxy="$NO_PROXY"
mkdir -p "$state_root"
pids=()
cleanup() {
  trap - EXIT INT TERM
  if ((${#pids[@]})); then
    kill "${pids[@]}" 2>/dev/null || true
    wait "${pids[@]}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM
"$platform_venv/bin/openroad-platform-worker" --state-root "$state_root" \\
  --plugins-root "$plugins_root" --admissions-root "$admissions_root" &
pids+=("$!")
"$platform_venv/bin/openroad-app-plan_executor" --host 127.0.0.1 --port 18840 \\
  --kernel-url http://127.0.0.1:18700 --db "$state_root/plan_executor.sqlite" &
pids+=("$!")
"$platform_venv/bin/openroad-platform-gateway" --host 127.0.0.1 --port 18700 --no-auth \\
  --state-root "$state_root" --plugins-root "$plugins_root" \\
  --admissions-root "$admissions_root" --config "$platform_root/examples/gateway-agent.json" &
pids+=("$!")
printf 'gateway: http://127.0.0.1:18700\\nplan service: http://127.0.0.1:18840\\n'
wait -n
''')
sprint = ef / 'tools/start-eda-ai-sprint.sh'
write(ROOT / 'admin/legacy-integration/start-eda-ai-sprint.sh', sprint.read_text())
sprint.unlink()
temp = ef / 'tools/start-eda-ai-sprint.tmp'
if temp.exists():
    temp.unlink()
config = ef / 'examples/gateway-agent.json'
body = json.loads(config.read_text())
for app in body['apps']:
    if app['name'] == 'plan_executor':
        app['base_url'] = 'http://127.0.0.1:18840'
write(config, json.dumps(body, indent=2) + '\n')

for name, project, role in [('data-foundation', df, '设计事实、快照、查询与独立数据库'),
                             ('data-interface', sdk, '对外接口契约和标准库 Python SDK')]:
    write(project / 'AGENTS.md', f'''# {name}

本项目负责{role}。这里只修改自己的源码，使用自己的 .venv。
跨项目只能使用已安装公共 wheel 或 HTTP；禁止 sys.path/PYTHONPATH 指向 sibling。
Data Foundation 不导入 kernel 实现、Query Agent 或其他应用，不直接读 kernel 数据库。
Data Interface 不导入服务存储实现，不新增数据库或服务进程。
安装路径、数据库路径和原始文件根目录由运行参数配置，不硬编码旧机器目录。
运行数据放上级 var，测试使用临时目录。执行验证使用上级 dev.py。
''')
    original = (project / 'README.md').read_text()
    write(project / 'docs/original-project-readme.md', original)
    write(project / 'README.md', f'''# {name}

独立项目，负责{role}。安装包名称与原实现保持一致，保留其文件 Git 历史。

从上级工作区使用：

```bash
python3 dev.py {name} check
python3 dev.py {name} shell
```

''' + ('''Data Foundation 安装 contracts/client wheel，原始产物通过公开 HTTP API 获取。
独立数据库默认在上级 var/data-foundation；新服务端口 18924。
使用 `python3 dev.py data-foundation serve` 启动；`--kernel-url`、`--native-root`
显式配置外部执行服务和原始 flow 目录。默认不接入旧运行状态。
smoke.py 使用已安装的包启动临时进程，不依赖原 monorepo 目录。
source_fingerprint 覆盖服务及已安装公共包；外部 producer 的溯源属于快照证据。
''' if project == df else '''Data Interface 没有独立服务进程，没有运行依赖。
公开契约见 CONTRACT.md，SDK 通过 `from eda_ai_client import EdaAiClient` 使用。
默认显式传入 Data Foundation 的 data_url；原始产物工具另需 Execution Foundation
的 kernel_url。SDK 不导入任何应用内部源码。
''') + '''
先前 API 和工具使用说明见 docs/original-project-readme.md（原 monorepo 安装路径
已成为历史示例）。迁移来源见 MIGRATION_SOURCE.json；完整工作区说明见上级 README。
''')
query_readme = query / 'README.md'
write(query_readme, query_readme.read_text() + '''
## 独立开发工作区（2026-10-08）

这是主 Query Agent 实现，保留原独立仓库的未提交工作。原平台 apps/query_agent
是不同的历史服务实现；没有并入本项目。
使用上级 `python3 dev.py query-agent check` 或 `python3 dev.py query-agent shell`。
执行平台走 HTTP 适配器；当前设计数据 provider 仍是 unavailable，Data Interface
SDK 接入需要后续实现。不要把目录独立误当作该能力已经接通。
''')
write(query / 'AGENTS.md', '''# Query Agent 主项目

遵守 CONTRIBUTING.md 与 .importlinter 的依赖方向。
保留已有未提交修改，勿重置或替换为旧平台 apps/query_agent。
使用本项目 .venv；跨项目通过 HTTP 或 Data Interface 发布 wheel，不读服务内部数据库。
设计数据端口尚未接入 SDK；不得将 unavailable 状态改为空数据或伪造成功。
''')

# Folder-specific interpreter choices for a multi-root editor.
for project in [ef, df, sdk, query]:
    write(project / '.vscode/settings.json', json.dumps({
        'python.defaultInterpreterPath': '${workspaceFolder}/.venv/bin/python',
        'python.terminal.activateEnvironment': True,
    }, indent=2) + '\n')
print('Project layout finalized')
