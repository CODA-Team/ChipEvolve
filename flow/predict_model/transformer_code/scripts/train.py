# 增加 false-worse 专项惩罚
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

from qor_comparator.config import ExperimentConfig
from qor_comparator.dataset import (
    CLASS_NAMES,
    IGNORE_LABEL,
    WORSE,
    QoRPairDataset,
    collate_qor_pairs,
)
from qor_comparator.model import QoRComparator


def set_global_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def choose_device(device_config: str) -> torch.device:
    if device_config == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    device = torch.device(device_config)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("Need CUDA, but no usable CUDA device is available")
    return device


def move_batch_to_device(
    batch: Mapping[str, Any],
    device: torch.device,
) -> Dict[str, Any]:
    return {
        key: value.to(device) if torch.is_tensor(value) else value
        for key, value in batch.items()
    }


def compute_multitask_loss(
    logits: torch.Tensor,
    labels: torch.Tensor,
    loss_weights: torch.Tensor,
    false_worse_weights: torch.Tensor,
    metric_names: List[str],
) -> Tuple[torch.Tensor, Dict[str, Dict[str, float]]]:
    """
    每个 QoR 的训练损失：

        metric_loss = cross_entropy + false_worse_weight * false_worse_penalty

    false_worse_penalty 只作用于真实标签不是 WORSE 的样本，并惩罚模型给 WORSE 类分配过高概率。其稳定实现等价于：

        -log(1 - p_worse)

    最后仍使用每个 QoR 原有的 loss_weight 对 metric_loss 加权。

    Args:
        logits: [B, M, 3]
        labels: [B, M]
        loss_weights: [M]
        false_worse_weights: [M]
        metric_names: 长度为 M
    """
    if logits.ndim != 3 or logits.shape[-1] != 3:
        raise ValueError("logits should be [batch, num_metrics, 3]")
    if labels.shape != logits.shape[:2]:
        raise ValueError(
            "labels' shape should match the first two dimensions of logits"
        )
    if loss_weights.shape != (logits.shape[1],):
        raise ValueError("loss_weights should be [num_metrics]")
    if false_worse_weights.shape != (logits.shape[1],):
        raise ValueError("false_worse_weights should be [num_metrics]")
    if len(metric_names) != logits.shape[1]:
        raise ValueError("metric_names length does not match num_metrics")
    if torch.any(false_worse_weights < 0):
        raise ValueError("false_worse_weights cannot be negative")

    total = logits.new_tensor(0.0)
    valid_weight_sum = logits.new_tensor(0.0)
    details: Dict[str, Dict[str, float]] = {}

    non_worse_class_indices = [
        class_index for class_index in range(3) if class_index != WORSE
    ]

    for metric_index, metric_name in enumerate(metric_names):
        metric_labels = labels[:, metric_index]
        valid = metric_labels != IGNORE_LABEL
        valid_count = int(valid.sum().item())

        if valid_count == 0:
            details[metric_name] = {
                "ce_loss": float("nan"),
                "false_worse_loss": float("nan"),
                "combined_loss": float("nan"),
                "valid_count": 0.0,
                "non_worse_count": 0.0,
                "false_worse_weight": float(
                    false_worse_weights[metric_index].detach().cpu()
                ),
            }
            continue

        metric_logits = logits[valid, metric_index, :]
        valid_labels = metric_labels[valid]

        ce_loss = nn.functional.cross_entropy(
            metric_logits,
            valid_labels,
        )

        # 只惩罚真实 Better/Similar 却给出高 WORSE 概率的样本。
        non_worse_mask = valid_labels != WORSE
        non_worse_count = int(non_worse_mask.sum().item())

        if non_worse_count > 0:
            non_worse_logits = metric_logits[non_worse_mask]

            # 将三分类 logits 转成“WORSE vs 非 WORSE”的二分类 logit：
            # z = logit_worse - logsumexp(logit_better, logit_similar)
            # softplus(z) = -log(1 - p_worse)
            rest_logit = torch.logsumexp(
                non_worse_logits[:, non_worse_class_indices],
                dim=-1,
            )
            worse_binary_logit = (
                non_worse_logits[:, WORSE] - rest_logit
            )
            false_worse_loss = nn.functional.softplus(
                worse_binary_logit
            ).mean()
        else:
            false_worse_loss = ce_loss.new_tensor(0.0)

        false_worse_weight = false_worse_weights[metric_index]
        combined_loss = (
            ce_loss + false_worse_weight * false_worse_loss
        )

        task_weight = loss_weights[metric_index]
        total = total + task_weight * combined_loss
        valid_weight_sum = valid_weight_sum + task_weight

        details[metric_name] = {
            "ce_loss": float(ce_loss.detach().cpu()),
            "false_worse_loss": float(
                false_worse_loss.detach().cpu()
            ),
            "combined_loss": float(combined_loss.detach().cpu()),
            "valid_count": float(valid_count),
            "non_worse_count": float(non_worse_count),
            "false_worse_weight": float(
                false_worse_weight.detach().cpu()
            ),
        }

    if valid_weight_sum.item() <= 0:
        raise RuntimeError("All target labels in the current batch are missing")

    return total / valid_weight_sum, details


class ClassificationAccumulator:
    """累计每个 QoR 的 accuracy、混淆矩阵与 false-worse 指标。"""

    def __init__(self, metric_names: List[str]) -> None:
        self.metric_names = metric_names
        self.confusion = torch.zeros(
            len(metric_names), 3, 3, dtype=torch.long
        )

    def update(self, logits: torch.Tensor, labels: torch.Tensor) -> None:
        predictions = logits.argmax(dim=-1).detach().cpu()
        labels = labels.detach().cpu()

        for metric_index in range(len(self.metric_names)):
            valid = labels[:, metric_index] != IGNORE_LABEL
            true_values = labels[valid, metric_index]
            pred_values = predictions[valid, metric_index]

            for true, pred in zip(
                true_values.tolist(), pred_values.tolist()
            ):
                self.confusion[metric_index, true, pred] += 1

    def summary(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        accuracies: List[float] = []

        for index, name in enumerate(self.metric_names):
            matrix = self.confusion[index]
            total = int(matrix.sum())
            correct = int(torch.diag(matrix).sum())
            accuracy = correct / total if total else float("nan")

            # 真实 Better/Similar，但预测为 Worse。
            false_worse_count = int(matrix[:WORSE, WORSE].sum())
            non_worse_count = int(matrix[:WORSE, :].sum())
            false_worse_rate = (
                false_worse_count / non_worse_count
                if non_worse_count > 0
                else float("nan")
            )

            if math.isfinite(accuracy):
                accuracies.append(accuracy)

            result[name] = {
                "accuracy": accuracy,
                "count": total,
                "confusion_matrix": matrix.tolist(),
                "class_order": list(CLASS_NAMES),
                "false_worse_count": false_worse_count,
                "non_worse_count": non_worse_count,
                "false_worse_rate": false_worse_rate,
            }

        result["macro_accuracy"] = (
            float(np.mean(accuracies)) if accuracies else float("nan")
        )
        return result


def forward_model(
    model: QoRComparator,
    batch: Mapping[str, Any],
) -> Dict[str, torch.Tensor]:
    return model(
        baseline_features=batch["baseline_features"],
        baseline_checkpoint_ids=batch["baseline_checkpoint_ids"],
        baseline_valid_mask=batch["baseline_valid_mask"],
        ongoing_features=batch["ongoing_features"],
        ongoing_checkpoint_ids=batch["ongoing_checkpoint_ids"],
        ongoing_valid_mask=batch["ongoing_valid_mask"],
        progress=batch["progress"],
        baseline_clock_ratio=batch["baseline_clock_ratio"],
        ongoing_clock_ratio=batch["ongoing_clock_ratio"],
    )


def run_epoch(
    model: QoRComparator,
    loader: DataLoader,
    device: torch.device,
    loss_weights: torch.Tensor,
    false_worse_weights: torch.Tensor,
    optimizer: torch.optim.Optimizer | None,
    grad_clip_norm: float,
    metric_names: List[str],
) -> Dict[str, Any]:
    training = optimizer is not None
    model.train(training)

    loss_sum = 0.0
    sample_count = 0
    accumulator = ClassificationAccumulator(metric_names)

    component_sums: Dict[str, Dict[str, float]] = {
        name: {
            "ce_numerator": 0.0,
            "ce_denominator": 0.0,
            "false_worse_numerator": 0.0,
            "false_worse_denominator": 0.0,
            "combined_numerator": 0.0,
            "combined_denominator": 0.0,
        }
        for name in metric_names
    }

    for raw_batch in loader:
        batch = move_batch_to_device(raw_batch, device)
        if training:
            optimizer.zero_grad(set_to_none=True)

        with torch.set_grad_enabled(training):
            outputs = forward_model(model, batch)
            loss, details = compute_multitask_loss(
                outputs["logits"],
                batch["labels"],
                loss_weights,
                false_worse_weights,
                metric_names,
            )

            if training:
                loss.backward()
                nn.utils.clip_grad_norm_(
                    model.parameters(), grad_clip_norm
                )
                optimizer.step()

        batch_size = batch["labels"].shape[0]
        loss_sum += float(loss.detach().cpu()) * batch_size
        sample_count += batch_size
        accumulator.update(outputs["logits"], batch["labels"])

        for metric_name, detail in details.items():
            valid_count = detail["valid_count"]
            non_worse_count = detail["non_worse_count"]

            if valid_count > 0 and math.isfinite(detail["ce_loss"]):
                component_sums[metric_name]["ce_numerator"] += (
                    detail["ce_loss"] * valid_count
                )
                component_sums[metric_name]["ce_denominator"] += valid_count
                component_sums[metric_name]["combined_numerator"] += (
                    detail["combined_loss"] * valid_count
                )
                component_sums[metric_name]["combined_denominator"] += (
                    valid_count
                )

            if (
                non_worse_count > 0
                and math.isfinite(detail["false_worse_loss"])
            ):
                component_sums[metric_name][
                    "false_worse_numerator"
                ] += detail["false_worse_loss"] * non_worse_count
                component_sums[metric_name][
                    "false_worse_denominator"
                ] += non_worse_count

    summary = accumulator.summary()
    summary["loss"] = loss_sum / max(sample_count, 1)
    summary["samples"] = sample_count
    summary["loss_components"] = {}

    for metric_index, metric_name in enumerate(metric_names):
        values = component_sums[metric_name]
        ce_denominator = values["ce_denominator"]
        false_worse_denominator = values["false_worse_denominator"]
        combined_denominator = values["combined_denominator"]

        summary["loss_components"][metric_name] = {
            "ce_loss": (
                values["ce_numerator"] / ce_denominator
                if ce_denominator > 0
                else float("nan")
            ),
            "false_worse_loss": (
                values["false_worse_numerator"]
                / false_worse_denominator
                if false_worse_denominator > 0
                else float("nan")
            ),
            "combined_loss": (
                values["combined_numerator"] / combined_denominator
                if combined_denominator > 0
                else float("nan")
            ),
            "loss_weight": float(loss_weights[metric_index].cpu()),
            "false_worse_weight": float(
                false_worse_weights[metric_index].cpu()
            ),
        }

    return summary


def build_loader(
    dataset: QoRPairDataset,
    batch_size: int,
    shuffle: bool,
    num_workers: int,
) -> DataLoader:
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        collate_fn=collate_qor_pairs,
        pin_memory=torch.cuda.is_available(),
    )


def save_checkpoint(
    path: Path,
    model: QoRComparator,
    optimizer: torch.optim.Optimizer,
    epoch: int,
    config_path: Path,
    validation_summary: Mapping[str, Any],
    false_worse_weights: Mapping[str, float],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "config_path": str(config_path),
            "validation_summary": dict(validation_summary),
            "target_metric_names": model.target_metric_names,
            "false_worse_weights": dict(false_worse_weights),
        },
        path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="train Transformer QoR comparator with false-worse penalty"
    )
    parser.add_argument(
        "--config", type=Path, required=True, help="JSON config"
    )
    args = parser.parse_args()

    config = ExperimentConfig.from_json(args.config)
    set_global_seed(config.training.seed)
    device = choose_device(config.training.device)
    output_dir = config.training.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    train_dataset = QoRPairDataset(
        config.data,
        split=config.data.train_split_name,
        training=True,
        seed=config.training.seed,
    )
    val_dataset = QoRPairDataset(
        config.data,
        split=config.data.val_split_name,
        training=False,
        seed=config.training.seed,
    )

    train_loader = build_loader(
        train_dataset,
        config.training.batch_size,
        shuffle=True,
        num_workers=config.training.num_workers,
    )
    val_loader = build_loader(
        val_dataset,
        config.training.batch_size,
        shuffle=False,
        num_workers=config.training.num_workers,
    )

    metric_names = [spec.name for spec in config.data.target_metrics]
    model = QoRComparator(
        input_dim=train_dataset.raw_feature_dim,
        num_checkpoints=len(config.data.checkpoint_order),
        target_metric_names=metric_names,
        config=config.model,
    ).to(device)

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.training.learning_rate,
        weight_decay=config.training.weight_decay,
    )

    loss_weights = torch.tensor(
        [spec.loss_weight for spec in config.data.target_metrics],
        dtype=torch.float32,
        device=device,
    )
    false_worse_weights = torch.tensor(
        [
            spec.false_worse_weight
            for spec in config.data.target_metrics
        ],
        dtype=torch.float32,
        device=device,
    )
    false_worse_weight_map = {
        metric_name: float(false_worse_weights[index].cpu())
        for index, metric_name in enumerate(metric_names)
    }

    best_val_loss = float("inf")
    epochs_without_improvement = 0
    history: List[Dict[str, Any]] = []

    print(f"device={device}")
    print(
        f"train pairs={len(train_dataset)}, "
        f"val pairs={len(val_dataset)}"
    )
    print(
        "model parameters="
        f"{sum(parameter.numel() for parameter in model.parameters()):,}"
    )
    print(f"false_worse_weights={false_worse_weight_map}")

    for epoch in range(1, config.training.epochs + 1):
        train_summary = run_epoch(
            model,
            train_loader,
            device,
            loss_weights,
            false_worse_weights,
            optimizer,
            config.training.grad_clip_norm,
            metric_names,
        )
        val_summary = run_epoch(
            model,
            val_loader,
            device,
            loss_weights,
            false_worse_weights,
            optimizer=None,
            grad_clip_norm=config.training.grad_clip_norm,
            metric_names=metric_names,
        )

        record = {
            "epoch": epoch,
            "false_worse_weights": false_worse_weight_map,
            "train": train_summary,
            "val": val_summary,
        }
        history.append(record)
        (output_dir / "history.json").write_text(
            json.dumps(
                history,
                indent=2,
                ensure_ascii=False,
                allow_nan=True,
            ),
            encoding="utf-8",
        )

        false_worse_text = " ".join(
            f"val_{name}_fw_rate="
            f"{val_summary[name]['false_worse_rate']:.4f}"
            for name in metric_names
            if math.isfinite(val_summary[name]["false_worse_rate"])
        )

        print(
            f"epoch={epoch:03d} "
            f"train_loss={train_summary['loss']:.6f} "
            f"val_loss={val_summary['loss']:.6f} "
            f"val_macro_acc={val_summary['macro_accuracy']:.4f} "
            f"{false_worse_text}"
        )

        if val_summary["loss"] < best_val_loss:
            best_val_loss = val_summary["loss"]
            epochs_without_improvement = 0
            save_checkpoint(
                output_dir / "best_model.pt",
                model,
                optimizer,
                epoch,
                args.config,
                val_summary,
                false_worse_weight_map,
            )
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= config.training.patience:
                print(
                    "Validation loss has not improved for the configured "
                    "patience; stopping early."
                )
                break

    print(f"Training ends, best validation loss: {best_val_loss:.6f}")
    print(f"The model is saved in {output_dir / 'best_model.pt'}")


if __name__ == "__main__":
    main()
