"""Task-specific models for segmented signal training."""

from __future__ import annotations

import torch
import torch.nn as nn


class ConvBlock1d(nn.Module):
    """A small 1D block that aggressively downsamples long sequences."""

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int, stride: int):
        super().__init__()
        padding = kernel_size // 2
        self.block = nn.Sequential(
            nn.Conv1d(in_channels, out_channels, kernel_size, stride=stride, padding=padding),
            nn.BatchNorm1d(out_channels),
            nn.GELU(),
            nn.Conv1d(out_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm1d(out_channels),
            nn.GELU(),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.block(inputs)


class SignalEncoder(nn.Module):
    """Common backbone for long 1D segmented signals."""

    def __init__(
        self,
        in_channels: int,
        channels: list[int],
        kernel_sizes: list[int],
        strides: list[int],
        dropout: float,
    ):
        super().__init__()
        if not (len(channels) == len(kernel_sizes) == len(strides)):
            raise ValueError("channels, kernel_sizes, and strides must have the same length")

        blocks = []
        current_channels = in_channels
        for out_channels, kernel_size, stride in zip(channels, kernel_sizes, strides):
            blocks.append(ConvBlock1d(current_channels, out_channels, kernel_size, stride))
            current_channels = out_channels

        self.features = nn.Sequential(*blocks)
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.dropout = nn.Dropout(dropout)
        self.output_dim = current_channels

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        outputs = self.features(inputs)
        outputs = self.pool(outputs).squeeze(-1)
        return self.dropout(outputs)


class Stage2Classifier(nn.Module):
    """Single-channel classifier for stage2 labels."""

    def __init__(self, config: dict):
        super().__init__()
        in_channels = config.get("in_channels", 1)
        self.encoder = SignalEncoder(
            in_channels=in_channels,
            channels=config["channels"],
            kernel_sizes=config["kernel_sizes"],
            strides=config["strides"],
            dropout=config.get("dropout", 0.2),
        )
        hidden_dim = config.get("hidden_dim", self.encoder.output_dim)
        self.head = nn.Sequential(
            nn.Linear(self.encoder.output_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(config.get("dropout", 0.2)),
            nn.Linear(hidden_dim, config["num_classes"]),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.head(self.encoder(inputs))


class Stage1Regressor(nn.Module):
    """Dual-channel regressor for stage1 distance estimation."""

    def __init__(self, config: dict):
        super().__init__()
        in_channels = config.get("in_channels", 2)
        self.encoder = SignalEncoder(
            in_channels=in_channels,
            channels=config["channels"],
            kernel_sizes=config["kernel_sizes"],
            strides=config["strides"],
            dropout=config.get("dropout", 0.2),
        )
        hidden_dim = config.get("hidden_dim", self.encoder.output_dim)
        self.head = nn.Sequential(
            nn.Linear(self.encoder.output_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(config.get("dropout", 0.2)),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.head(self.encoder(inputs)).squeeze(-1)


def build_model(config: dict) -> nn.Module:
    """Create a model that matches the configured task."""
    task = config["task"]
    if task == "stage1":
        return Stage1Regressor(config["model"])
    if task == "stage2":
        return Stage2Classifier(config["model"])
    raise ValueError(f"Unsupported task: {task}")
