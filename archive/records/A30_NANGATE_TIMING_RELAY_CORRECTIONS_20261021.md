# A30 Nangate45 时序接力：实际阻断修复与结果边界

本轮仍在执行八组、每组两次独立完整路径的目标，没有完成验收。已有 ASAP7 GCD/JPEG 合法结果保留。本文只记录新发现、新修复及已观察结果，不将运行成功等同 PPA 合格。

## 1. 三个实际接入问题及修复

| 问题 | 证据 | 修复及边界 |
|---|---|---|
| 直接执行独立 Goal driver，导入了旧安装版本，找不到 Nangate45 库 | 原 RMP native/baseline.json 报 contest ASAP7 LEF/lib assets are missing；实际原 controller 已支持 pdk_root | 使用现有产品 run_goal 同样的 `python -c/runpy` 启动方式，并从该专业项目自己的冻结 controller 工作目录运行；不改 PYTHONPATH、不修改安装环境或原算法 |
| 读取已布线 ODB 后，原生时序修复在缓冲器动作中崩溃 | run-ce03467590594037b4c1b44ae5aad65d、run-da761f1bc3864d6699632482f4c1e55a：getPinGridPositions→makeBufferedNetGroute→BufferCandidate | 完整源时序先按原 SPEF 验证，然后显式清除详细线路、重建 GRT 及寄生，再执行原修复；新动作 run-88fd59000e1a44a8a42bc595ca358d56 成功。线路重置明确属于优化动作，最终仍独立 DRT/RCX，不隐藏在测量中 |
| Nangate45/GCD 原生 Flow 配置缺失 | 原完整搜索 controller.log 在启动前报 drp_config.json has no entry；尚未执行 50 候选 | flow-agent/flow/drp_config.json 新增真实基准归一化参数：wirelength=4531µm，ECP=0.418758ns，默认时钟0.25ns。范围沿用已有 Nangate45 的0.1—1ns；最终共同测量仍使用原250ps约束。97项原模块回归通过 |

Flow 模块提交 `99007aa` 已推送 ChipEvolve 的 modules/flow-agent。公共 CLI、EF/DF/DI 协议、服务、调度容量及其他设计配置不变。旧实验目录不改，新实验独立留档。

## 2. 原算法与真实优化效果不能混为一谈

两条新 Goal 接力均使用原 Student03 的701文件源码身份及完全相同二进制，SHA256为 `aaf5458ff2722f3275b599eccbf4dea43393dddb63372301f93b93b3043839e9`。没有生成新 Student、修改 CPP 或改变晋升规则。

以下为已完成共同测量文件的观察值；新分支仍等待 DF 完整事实交付，尚未采用：

| GCD Nangate45 分支 | 功耗 mW | cell面积 µm² | setup最差裕量 ps | setup TNS ns |
|---|---:|---:|---:|---:|
| 原参考 | 6.334064 | 943.502 | -161.583 | -7.08646 |
| 原 Goal 主结果 | 6.284027 | 945.098 | -157.217 | -6.99576 |
| 主结果→完整原生 TNS 修复，重建路由后 | 6.401361 | 960.526 | -159.266 | -7.11209 |
| 主结果→原 RMP halo 配方 | 6.148120 | 887.376 | -180.445 | -8.05452 |

结论：修复了环境和动作可执行性，并未修复 PPA 合格性。完整 TNS 动作实际执行52次端点迭代、18次升尺寸、3个缓冲器、5次引脚交换，仍未闭合；“只是迭代预算太小”不是充分解释，不能继续原样加次数。RMP配方降低功耗面积、恶化时序，不能采用或把平均值作为掩盖。

完整 ABC speed 配置的两次独立全流程也均有 setup WS=-329.349ps/TNS=-14.5522ns，比它自己的完整Yosys参考差；保留负结果，不记合格。

## 3. RMP 实测暴露的下一步策略依据

原 RMP halo 配方确实调用了 `restructure`，但日志所选路径 `cloud_instances=0`，因此不能称其完成有效逻辑重构。其前置 power 阶段有229个实际动作，TNS从约-6.912变为-10.977ns，后续小预算修复没有完全收回损失。

源码核查更正早先笔记：`Restructure.cpp` 的变量虽叫 `max_depth`，实际条件是 `expanded.size()/2 > max_depth` 才选择路径；`-depth_threshold 16` 在这里是深度筛选门槛，不能按变量名称作“允许的最大深度”。原代码还有 `safeRestructureInst` 的 FF 相邻单元过滤及已有 `RMP_ALLOW_FF_PIN_TOUCH_WITH_NET_GUARD` 策略开关。已据此新增一次原生策略验证：使用已有 FF 邻接允许开关，同时保留原 sequential-pin-net 零变化接受检查、时序收益 guard 和4-cloud/1-accepted预算；深度门槛设8以覆盖原Query观察的14级逻辑，不执行前置80%功耗回收，然后完整原生TNS修复。此为Codex显式选择既有工具策略，未修改CPP或冒充原Teacher新配方/晋升。实际是否产生非空cloud、有收益或通过功能证明仍需实验确认；见运行目录 gcd-rmp-ff-boundary-full-tns-launch.json。

## 4. 新派发与现有任务

- 修正配置后的完整原生 Flow：`a30-gcd-nangate45-full-flow-profile-r3-trial1`；PID见运行目录 launch。复用已完成且同条件的 baseline/Query，新搜索1轮50候选；第一次完整结束后按同协议独立第二次。不是重放现有最优结果，也不声称已执行完50份。
- 原 GCD DPL→Goal 双次整链、JPEG/Ibex 双次接力、JPEG/Ariane 原生四Student搜索及两次参考继续。以公开 EF 和各自真实进程为准。
- Ariane Nangate45 原完整 ORFS 已成功，最终共同测量显示 setup WS=+206.953ps、TNS0，事实交付仍在途，后续原 Query/Goal driver 尚未得到完整 result，不能先写优化成功。
- DF健康端点实测约0.30秒；新大设计事实导入期间 writer线程实际处于D状态，其他已提交导入等待。保留原进程与请求，不因观察时限或低CPU另起一份导入/服务。此处需继续核验落盘与交付，不声称所有事实已经齐全。

## 5. 修改文件与验证

- `flow-agent/flow/drp_config.json`：仅新增实测 Nangate45/GCD 的原生配置登记；JSON解析、原生 config_info/get_design_config、97项 flow/test 回归、607项根集成回归和 git diff --check 通过。
- `SOURCE_MANIFEST.json`、flow-agent gitlink：固定已发布配置提交。
- 本文与 `TASKS.md`：记录可续作状态；运行脚本、真实失败、源码/二进制身份与运行产物均在 var/business/a30-four-design-two-pdk-20261021。

26份保护文件保持原字节，DF/DI及评测目录既有用户修改不碰。八组合格、全部双次整链及相应最终功能证明仍未齐，不标完成。
