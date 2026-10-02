from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping
import json

Direction = Literal["higher", "lower"]


@dataclass(frozen=True)
class TargetMetricSpec:
    """用于生成 Better / Similar / Worse 标签的 QoR 指标配置。"""

    name: str
    direction: Direction
    relative_tolerance: float = 0.01   #similar相对容忍度
    absolute_tolerance: float = 0.0
    loss_weight: float = 1.0
    decision_weight: float = 1.0

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TargetMetricSpec":
        direction = str(data["direction"]).lower()
        if direction not in {"higher", "lower"}:
            raise ValueError(f"Unsupported metric direction: {direction}")
        return cls(
            name=str(data["name"]),
            direction=direction,  # type: ignore[arg-type]
            relative_tolerance=float(data.get("relative_tolerance", 0.01)),
            absolute_tolerance=float(data.get("absolute_tolerance", 0.0)),
            loss_weight=float(data.get("loss_weight", 1.0)),
            decision_weight=float(data.get("decision_weight", 1.0)),
        )


@dataclass(frozen=True)
class DataConfig:
    """数据读取与训练样本构造配置。"""

    run_manifest: Path
    pair_manifest: Path
    checkpoint_column: str
    input_metrics: List[str]
    checkpoint_order: List[str]
    target_metrics: List[TargetMetricSpec]
    split_column: str = "split"
    train_split_name: str = "train"
    val_split_name: str = "val"
    test_split_name: str = "test"
    min_prefix_checkpoints: int = 2
    train_prefix_ratios: List[float] = field(
        default_factory=lambda: [0.25, 0.5, 0.75, 1.0]
    )
    eval_prefix_ratio: float = 0.5
    normalization_eps: float = 1e-6
    missing_value_fill: float = 0.0
    append_missing_mask: bool = True
    strict_checkpoint_alignment: bool = True


@dataclass(frozen=True)
class ModelConfig:
    """共享 Transformer Encoder 与分类头配置。"""

    d_model: int = 64
    nhead: int = 4
    num_encoder_layers: int = 2
    dim_feedforward: int = 128
    dropout: float = 0.1
    fusion_hidden_dim: int = 128
    fusion_dropout: float = 0.1
    use_hadamard_product: bool = True
    pooling: Literal["masked_mean", "cls"] = "masked_mean"


@dataclass(frozen=True)
class TrainingConfig:
    """训练相关配置。"""

    batch_size: int = 32
    num_workers: int = 0
    epochs: int = 50
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    grad_clip_norm: float = 1.0
    seed: int = 42
    device: str = "auto"
    output_dir: Path = Path("outputs")
    kill_threshold: float = 0.8
    patience: int = 8


@dataclass(frozen=True)
class ExperimentConfig:
    data: DataConfig
    model: ModelConfig
    training: TrainingConfig

    @classmethod
    def from_json(cls, path: str | Path) -> "ExperimentConfig":
        config_path = Path(path)
        raw: Dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))

        data_raw = dict(raw["data"])
        target_specs = [
            TargetMetricSpec.from_dict(item)
            for item in data_raw.pop("target_metrics")
        ]
        run_manifest = Path(data_raw.pop("run_manifest"))
        pair_manifest = Path(data_raw.pop("pair_manifest"))
        if not run_manifest.is_absolute():
            run_manifest = config_path.parent / run_manifest
        if not pair_manifest.is_absolute():
            pair_manifest = config_path.parent / pair_manifest
        data_cfg = DataConfig(
            run_manifest=run_manifest,
            pair_manifest=pair_manifest,
            checkpoint_column=str(data_raw.pop("checkpoint_column")),
            input_metrics=[str(x) for x in data_raw.pop("input_metrics")],
            checkpoint_order=[str(x) for x in data_raw.pop("checkpoint_order")],
            target_metrics=target_specs,
            **data_raw,
        )

        model_cfg = ModelConfig(**raw.get("model", {}))

        training_raw = dict(raw.get("training", {}))
        if "output_dir" in training_raw:
            output_dir = Path(training_raw["output_dir"])
            if not output_dir.is_absolute():
                output_dir = config_path.parent / output_dir
            training_raw["output_dir"] = output_dir
        training_cfg = TrainingConfig(**training_raw)

        return cls(data=data_cfg, model=model_cfg, training=training_cfg)
