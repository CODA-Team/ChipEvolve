from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import torch
from torch import nn

from .config import ModelConfig


class SharedTrajectoryEncoder(nn.Module):
    """
    将一条 QoR 轨迹编码为固定长度向量。

    baseline 与 ongoing 都调用同一个实例，因此输入投影、检查点嵌入和
    Transformer Encoder 的所有参数完全共享。
    """

    def __init__(
        self,
        input_dim: int,
        num_checkpoints: int,
        config: ModelConfig,
    ) -> None:
        super().__init__()
        self.config = config
        self.input_projection = nn.Linear(input_dim, config.d_model)
        self.checkpoint_embedding = nn.Embedding(num_checkpoints, config.d_model)
        self.input_norm = nn.LayerNorm(config.d_model)
        self.input_dropout = nn.Dropout(config.dropout)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.d_model,
            nhead=config.nhead,
            dim_feedforward=config.dim_feedforward,
            dropout=config.dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=config.num_encoder_layers,
            norm=nn.LayerNorm(config.d_model),
            enable_nested_tensor=False,
        )

        if config.pooling == "cls":
            self.cls_token = nn.Parameter(torch.zeros(1, 1, config.d_model))
            nn.init.normal_(self.cls_token, mean=0.0, std=0.02)
        else:
            self.register_parameter("cls_token", None)

    def forward(
        self,
        features: torch.Tensor,
        checkpoint_ids: torch.Tensor,
        valid_mask: torch.Tensor,
    ) -> torch.Tensor:
        """
        Args:
            features: [batch, length, input_dim]
            checkpoint_ids: [batch, length]
            valid_mask: [batch, length]，True 表示真实检查点，False 表示 padding

        Returns:
            [batch, d_model] 的轨迹摘要向量。
        """
        if features.ndim != 3:
            raise ValueError(f"features 应为 3 维，当前形状为 {features.shape}")
        if checkpoint_ids.shape != features.shape[:2]:
            raise ValueError("checkpoint_ids 与 features 的前两维不一致")
        if valid_mask.shape != features.shape[:2]:
            raise ValueError("valid_mask 与 features 的前两维不一致")

        # 先把原始 QoR 特征投影到 d_model，再加入可学习的检查点编码。
        hidden = self.input_projection(features)
        hidden = hidden + self.checkpoint_embedding(checkpoint_ids)
        hidden = self.input_dropout(self.input_norm(hidden))

        if self.config.pooling == "cls":
            batch_size = hidden.shape[0]
            cls = self.cls_token.expand(batch_size, -1, -1)
            hidden = torch.cat([cls, hidden], dim=1)
            cls_valid = torch.ones(
                batch_size, 1, dtype=torch.bool, device=valid_mask.device
            )
            valid_mask = torch.cat([cls_valid, valid_mask], dim=1)

        # PyTorch 的 src_key_padding_mask 中 True 表示“需要忽略”。
        padding_mask = ~valid_mask
        encoded = self.encoder(hidden, src_key_padding_mask=padding_mask)

        if self.config.pooling == "cls":
            return encoded[:, 0]

        # Masked Mean Pooling：padding 位置不能参与平均。
        mask = valid_mask.unsqueeze(-1).to(encoded.dtype)
        summed = (encoded * mask).sum(dim=1)
        denominator = mask.sum(dim=1).clamp_min(1.0)
        return summed / denominator


class QoRComparator(nn.Module):
    """
    基于共享 Transformer Encoder 的多 QoR 相对比较模型。

    融合特征：
      [h_B, h_C, h_C - h_B, h_C ⊙ h_B, progress, rb, rc]

    每个目标 QoR 有一个独立三分类头，类别顺序固定为：
      0=Better, 1=Similar, 2=Worse
    """

    def __init__(
        self,
        input_dim: int,
        num_checkpoints: int,
        target_metric_names: Sequence[str],
        config: ModelConfig,
    ) -> None:
        super().__init__()
        if not target_metric_names:
            raise ValueError("target_metric_names 不能为空")

        self.config = config
        self.target_metric_names = list(target_metric_names)
        self.trajectory_encoder = SharedTrajectoryEncoder(
            input_dim=input_dim,
            num_checkpoints=num_checkpoints,
            config=config,
        )

        # 融合层向量：baseline向量特征 + ongoing向量特征 + 二者差值 + hadamard积 + 
        # progress + baseline的cp比例 + ongoing的cp比例
        num_vector_blocks = 4 if config.use_hadamard_product else 3
        num_scalar_features = 3
        fusion_input_dim = (
            num_vector_blocks * config.d_model + num_scalar_features
        )                                                   

        self.fusion = nn.Sequential(
            nn.Linear(fusion_input_dim, config.fusion_hidden_dim),
            nn.GELU(),
            nn.LayerNorm(config.fusion_hidden_dim),
            nn.Dropout(config.fusion_dropout),
            nn.Linear(config.fusion_hidden_dim, config.fusion_hidden_dim),
            nn.GELU(),
            nn.Dropout(config.fusion_dropout),
        )

        # 概念上是“每个 QoR 一个独立分类头”；实现上用 ModuleList 避免
        # 指标名含特殊字符时成为非法模块键。
        self.classification_heads = nn.ModuleList(
            [
                nn.Linear(config.fusion_hidden_dim, 3)
                for _ in self.target_metric_names
            ]
        )

    def forward(
        self,
        baseline_features: torch.Tensor,
        baseline_checkpoint_ids: torch.Tensor,
        baseline_valid_mask: torch.Tensor,
        ongoing_features: torch.Tensor,
        ongoing_checkpoint_ids: torch.Tensor,
        ongoing_valid_mask: torch.Tensor,
        progress: torch.Tensor,
        baseline_clock_ratio: torch.Tensor,
        ongoing_clock_ratio: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        # 同一个 trajectory_encoder 被调用两次，参数完全共享。
        h_baseline = self.trajectory_encoder(
            baseline_features,
            baseline_checkpoint_ids,
            baseline_valid_mask,
        )
        h_ongoing = self.trajectory_encoder(
            ongoing_features,
            ongoing_checkpoint_ids,
            ongoing_valid_mask,
        )

        difference = h_ongoing - h_baseline
        blocks = [h_baseline, h_ongoing, difference]
        if self.config.use_hadamard_product:
            hadamard = h_ongoing * h_baseline
            blocks.append(hadamard)

        if progress.ndim == 1:
            progress = progress.unsqueeze(-1)
        if progress.ndim != 2 or progress.shape[1] != 1:
            raise ValueError(f"progress 应为 [batch, 1]，当前为 {progress.shape}")

        fused_input = torch.cat(
            [
                *blocks,
                progress,
                baseline_clock_ratio,
                ongoing_clock_ratio,
            ],
            dim=-1,
        )
        fused_features = self.fusion(fused_input)

        # [batch, num_metrics, 3]
        logits = torch.stack(
            [head(fused_features) for head in self.classification_heads],
            dim=1,
        )
        probabilities = torch.softmax(logits, dim=-1)

        return {
            "logits": logits,
            "probabilities": probabilities,
            "h_baseline": h_baseline,
            "h_ongoing": h_ongoing,
            "difference": difference,
            "fused_features": fused_features,
        }

    @staticmethod
    def compute_kill_score(
        probabilities: torch.Tensor,
        tns_metric_index: int,
        power_metric_index: int,
    ) -> Dict[str, torch.Tensor]:
        """
        约束感知的 killing score。

        优化目标：
        1. power 相比 baseline 的恶化不得超过标签中设定的容忍度；
        2. 在满足 power 约束的前提下优化 TNS。

        Args:
            probabilities:
                [batch, num_metrics, 3]
                类别顺序固定为 Better / Similar / Worse。
            tns_metric_index:
                TNS 在 target_metrics 中的位置。
            power_metric_index:
                power_total 在 target_metrics 中的位置。

        """
        if probabilities.ndim != 3 or probabilities.shape[-1] != 3:
            raise ValueError(
                "probabilities 应为 [batch, num_metrics, 3]"
            )

        num_metrics = probabilities.shape[1]
        if not (0 <= tns_metric_index < num_metrics):
            raise ValueError("tns_metric_index 越界")
        if not (0 <= power_metric_index < num_metrics):
            raise ValueError("power_metric_index 越界")
        if tns_metric_index == power_metric_index:
            raise ValueError("TNS 和 power 不能使用同一个指标位置")

        power_violation_probability = probabilities[
            :, power_metric_index, 2
        ]
        tns_worse_probability = probabilities[
            :, tns_metric_index, 2
        ]

        power_feasible_probability = (
            1.0 - power_violation_probability
        )

        tns_better_probability = probabilities[
            :,tns_metric_index, 0
        ]

        kill_score = 1.0 - (
            1.0 - power_violation_probability
        ) * (
            1.0 - tns_worse_probability
        )

        promising_score = (
            power_feasible_probability
            * tns_better_probability
        )

        return {
            "power_violation_probability": (
                power_violation_probability
            ),
            "power_feasible_probability": (
                power_feasible_probability
            ),
            "tns_worse_probability": (
                tns_worse_probability
            ),
            "tns_better_probability": (
                tns_better_probability
            ),
            "kill_score": kill_score.clamp(0.0, 1.0),
            "promising_score": promising_score.clamp(0.0, 1.0),
        }