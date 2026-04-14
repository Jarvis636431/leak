"""Optional Conformer models for segmented signal experiments.

These models are intentionally not wired into the default training path yet.
They are kept as opt-in alternatives while the 1D CNN baseline remains the
active production path.
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn


class Swish(nn.Module):
    """Memory-light swish activation."""

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return inputs * torch.sigmoid(inputs)


class GLU(nn.Module):
    """Gated linear unit for the convolution module."""

    def __init__(self, dim: int):
        super().__init__()
        self.dim = dim

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        output, gate = inputs.chunk(2, dim=self.dim)
        return output * torch.sigmoid(gate)


class FeedForwardModule(nn.Module):
    """Macaron-style feed-forward block."""

    def __init__(self, d_model: int, d_ff: int, dropout: float):
        super().__init__()
        self.block = nn.Sequential(
            nn.LayerNorm(d_model),
            nn.Linear(d_model, d_ff),
            Swish(),
            nn.Dropout(dropout),
            nn.Linear(d_ff, d_model),
            nn.Dropout(dropout),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.block(inputs)


class MultiHeadSelfAttention(nn.Module):
    """Standard multi-head self-attention."""

    def __init__(self, d_model: int, num_heads: int, dropout: float):
        super().__init__()
        if d_model % num_heads != 0:
            raise ValueError("d_model must be divisible by num_heads")

        self.num_heads = num_heads
        self.d_head = d_model // num_heads
        self.scale = math.sqrt(self.d_head)

        self.query = nn.Linear(d_model, d_model)
        self.key = nn.Linear(d_model, d_model)
        self.value = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        batch_size, seq_len, d_model = inputs.shape

        query = self.query(inputs).view(batch_size, seq_len, self.num_heads, self.d_head)
        key = self.key(inputs).view(batch_size, seq_len, self.num_heads, self.d_head)
        value = self.value(inputs).view(batch_size, seq_len, self.num_heads, self.d_head)

        query = query.transpose(1, 2)
        key = key.transpose(1, 2)
        value = value.transpose(1, 2)

        scores = torch.matmul(query, key.transpose(-2, -1)) / self.scale
        attention = torch.softmax(scores, dim=-1)
        attention = self.dropout(attention)

        context = torch.matmul(attention, value)
        context = context.transpose(1, 2).contiguous().view(batch_size, seq_len, d_model)
        return self.out_proj(context)


class DepthwiseConv1d(nn.Module):
    """Depthwise separable 1D convolution."""

    def __init__(self, channels: int, kernel_size: int):
        super().__init__()
        padding = (kernel_size - 1) // 2
        self.depthwise = nn.Conv1d(
            channels,
            channels,
            kernel_size=kernel_size,
            padding=padding,
            groups=channels,
        )
        self.pointwise = nn.Conv1d(channels, channels, kernel_size=1)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        outputs = self.depthwise(inputs)
        return self.pointwise(outputs)


class ConvolutionModule(nn.Module):
    """Conformer convolution branch."""

    def __init__(self, channels: int, kernel_size: int, dropout: float):
        super().__init__()
        self.layer_norm = nn.LayerNorm(channels)
        self.pointwise_conv1 = nn.Conv1d(channels, channels * 2, kernel_size=1)
        self.glu = GLU(dim=1)
        self.depthwise_conv = DepthwiseConv1d(channels, kernel_size)
        self.batch_norm = nn.BatchNorm1d(channels)
        self.activation = Swish()
        self.pointwise_conv2 = nn.Conv1d(channels, channels, kernel_size=1)
        self.dropout = nn.Dropout(dropout)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        outputs = self.layer_norm(inputs)
        outputs = outputs.transpose(1, 2)
        outputs = self.pointwise_conv1(outputs)
        outputs = self.glu(outputs)
        outputs = self.depthwise_conv(outputs)
        outputs = self.batch_norm(outputs)
        outputs = self.activation(outputs)
        outputs = self.pointwise_conv2(outputs)
        outputs = self.dropout(outputs)
        return outputs.transpose(1, 2)


class ConformerBlock(nn.Module):
    """Single Conformer block."""

    def __init__(self, d_model: int, d_ff: int, num_heads: int, kernel_size: int, dropout: float):
        super().__init__()
        self.ffn1 = FeedForwardModule(d_model, d_ff, dropout)
        self.attention_norm = nn.LayerNorm(d_model)
        self.attention = MultiHeadSelfAttention(d_model, num_heads, dropout)
        self.attention_dropout = nn.Dropout(dropout)
        self.conv = ConvolutionModule(d_model, kernel_size, dropout)
        self.ffn2 = FeedForwardModule(d_model, d_ff, dropout)
        self.final_norm = nn.LayerNorm(d_model)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        outputs = inputs + 0.5 * self.ffn1(inputs)
        outputs = outputs + self.attention_dropout(self.attention(self.attention_norm(outputs)))
        outputs = outputs + self.conv(outputs)
        outputs = outputs + 0.5 * self.ffn2(outputs)
        return self.final_norm(outputs)


class ConvSubsampler(nn.Module):
    """Downsample long 1D signals before the transformer blocks."""

    def __init__(self, in_channels: int, hidden_channels: int, strides: list[int], dropout: float):
        super().__init__()
        blocks = []
        current_channels = in_channels
        for stride in strides:
            blocks.extend(
                [
                    nn.Conv1d(
                        current_channels,
                        hidden_channels,
                        kernel_size=7,
                        stride=stride,
                        padding=3,
                    ),
                    nn.BatchNorm1d(hidden_channels),
                    nn.GELU(),
                    nn.Dropout(dropout),
                ]
            )
            current_channels = hidden_channels
        self.network = nn.Sequential(*blocks)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        outputs = self.network(inputs)
        return outputs.transpose(1, 2)


class SegmentedSignalConformer(nn.Module):
    """Shared Conformer encoder for long segmented signals."""

    def __init__(self, config: dict, in_channels: int):
        super().__init__()
        d_model = config["d_model"]
        dropout = config.get("dropout", 0.1)
        self.subsampler = ConvSubsampler(
            in_channels=in_channels,
            hidden_channels=d_model,
            strides=config.get("subsample_strides", [8, 4]),
            dropout=dropout,
        )
        self.layers = nn.ModuleList(
            [
                ConformerBlock(
                    d_model=d_model,
                    d_ff=config["d_ff"],
                    num_heads=config["num_heads"],
                    kernel_size=config.get("kernel_size", 31),
                    dropout=dropout,
                )
                for _ in range(config["num_layers"])
            ]
        )
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.output_dim = d_model

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        outputs = self.subsampler(inputs)
        for layer in self.layers:
            outputs = layer(outputs)
        outputs = outputs.transpose(1, 2)
        return self.pool(outputs).squeeze(-1)


class Stage2ConformerClassifier(nn.Module):
    """Optional Conformer classifier for stage2 experiments."""

    def __init__(self, config: dict):
        super().__init__()
        self.encoder = SegmentedSignalConformer(config, in_channels=1)
        hidden_dim = config.get("hidden_dim", self.encoder.output_dim)
        dropout = config.get("dropout", 0.1)
        self.head = nn.Sequential(
            nn.Linear(self.encoder.output_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, config["num_classes"]),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.head(self.encoder(inputs))


class Stage1ConformerRegressor(nn.Module):
    """Optional Conformer regressor for stage1 experiments."""

    def __init__(self, config: dict):
        super().__init__()
        self.encoder = SegmentedSignalConformer(config, in_channels=2)
        hidden_dim = config.get("hidden_dim", self.encoder.output_dim)
        dropout = config.get("dropout", 0.1)
        self.head = nn.Sequential(
            nn.Linear(self.encoder.output_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.head(self.encoder(inputs)).squeeze(-1)
