# 测试

在项目根目录运行确定性单测。

```bash
python3 -m pytest tests/unit
```

`unit/` 用本地小型夹具验证控制器、AST 和评估器。ChipEvolve 发布检出已包含所需文件。

`artifact/` 需要完整的 GoalEvolve 科研检出，包括冻结的 P0 和官方 AES benchmark。可在完整检出中运行 `python3 -m pytest tests/artifact`，验证发布清单、冻结的 AST 图及官方四项检查。全新 OpenROAD 构建与物理设计运行由集成实验验证。
