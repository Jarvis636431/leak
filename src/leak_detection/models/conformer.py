"""
Conformer model for pipeline leak detection.
Based on "Conformer: Convolution-augmented Transformer for Speech Recognition"
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import math


class Swish(nn.Module):
    """Swish activation function"""

    def forward(self, x):
        return x * torch.sigmoid(x)


class GLU(nn.Module):
    """Gated Linear Unit"""

    def __init__(self, dim):
        super().__init__()
        self.dim = dim

    def forward(self, x):
        out, gate = x.chunk(2, dim=self.dim)
        return out * torch.sigmoid(gate)


class ConvSubsample(nn.Module):
    """Convolutional Subsampling Layer"""

    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.conv1 = nn.Conv2d(1, out_channels, 3, stride=2, padding=1)
        self.conv2 = nn.Conv2d(out_channels, out_channels, 3, stride=2, padding=1)
        self.relu = nn.ReLU()

    def forward(self, x):
        # x: (batch, time, freq)
        x = x.unsqueeze(1)  # (batch, 1, time, freq)
        x = self.relu(self.conv1(x))
        x = self.relu(self.conv2(x))
        # Reshape back to (batch, time, features)
        batch, channels, time, freq = x.shape
        x = x.permute(0, 2, 1, 3).reshape(batch, time, channels * freq)
        return x


class DepthwiseConv1d(nn.Module):
    """Depthwise Separable Convolution"""

    def __init__(self, in_channels, out_channels, kernel_size, padding=0):
        super().__init__()
        self.depthwise = nn.Conv1d(
            in_channels, in_channels, kernel_size, padding=padding, groups=in_channels
        )
        self.pointwise = nn.Conv1d(in_channels, out_channels, 1)

    def forward(self, x):
        x = self.depthwise(x)
        x = self.pointwise(x)
        return x


class ConvolutionModule(nn.Module):
    """Conformer Convolution Module"""

    def __init__(self, channels, kernel_size=31, expansion_factor=2, dropout=0.1):
        super().__init__()
        self.layer_norm = nn.LayerNorm(channels)
        self.pointwise_conv1 = nn.Conv1d(channels, 2 * channels, 1)
        self.glu = GLU(dim=1)

        padding = (kernel_size - 1) // 2
        self.depthwise_conv = DepthwiseConv1d(
            channels, channels, kernel_size, padding=padding
        )
        self.batch_norm = nn.BatchNorm1d(channels)
        self.swish = Swish()

        self.pointwise_conv2 = nn.Conv1d(channels, channels, 1)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        # x: (batch, time, channels)
        x = self.layer_norm(x)
        x = x.transpose(1, 2)  # (batch, channels, time)

        x = self.pointwise_conv1(x)
        x = self.glu(x)

        x = self.depthwise_conv(x)
        x = self.batch_norm(x)
        x = self.swish(x)

        x = self.pointwise_conv2(x)
        x = self.dropout(x)

        x = x.transpose(1, 2)  # (batch, time, channels)
        return x


class FeedForwardModule(nn.Module):
    """Feed Forward Module (Macaron-Net style)"""

    def __init__(self, d_model, d_ff, dropout=0.1):
        super().__init__()
        self.layer_norm = nn.LayerNorm(d_model)
        self.fc1 = nn.Linear(d_model, d_ff)
        self.swish = Swish()
        self.dropout1 = nn.Dropout(dropout)
        self.fc2 = nn.Linear(d_ff, d_model)
        self.dropout2 = nn.Dropout(dropout)

    def forward(self, x):
        residual = x
        x = self.layer_norm(x)
        x = self.fc1(x)
        x = self.swish(x)
        x = self.dropout1(x)
        x = self.fc2(x)
        x = self.dropout2(x)
        return x + residual


class MultiHeadSelfAttention(nn.Module):
    """Multi-Head Self Attention with Relative Positional Encoding"""

    def __init__(self, d_model, num_heads, dropout=0.1):
        super().__init__()
        assert d_model % num_heads == 0

        self.d_model = d_model
        self.num_heads = num_heads
        self.d_head = d_model // num_heads

        self.query = nn.Linear(d_model, d_model)
        self.key = nn.Linear(d_model, d_model)
        self.value = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)

        self.dropout = nn.Dropout(dropout)
        self.scale = math.sqrt(self.d_head)

    def forward(self, x, mask=None):
        batch_size, seq_len, _ = x.shape

        # Linear projections
        Q = (
            self.query(x)
            .view(batch_size, seq_len, self.num_heads, self.d_head)
            .transpose(1, 2)
        )
        K = (
            self.key(x)
            .view(batch_size, seq_len, self.num_heads, self.d_head)
            .transpose(1, 2)
        )
        V = (
            self.value(x)
            .view(batch_size, seq_len, self.num_heads, self.d_head)
            .transpose(1, 2)
        )

        # Scaled dot-product attention
        scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale

        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)

        attn = F.softmax(scores, dim=-1)
        attn = self.dropout(attn)

        context = torch.matmul(attn, V)
        context = (
            context.transpose(1, 2).contiguous().view(batch_size, seq_len, self.d_model)
        )

        output = self.out_proj(context)
        return output


class ConformerBlock(nn.Module):
    """Conformer Block"""

    def __init__(
        self,
        d_model,
        num_heads,
        d_ff,
        kernel_size=31,
        conv_expansion_factor=2,
        dropout=0.1,
    ):
        super().__init__()
        self.ff1 = FeedForwardModule(d_model, d_ff, dropout)
        self.attention = MultiHeadSelfAttention(d_model, num_heads, dropout)
        self.conv = ConvolutionModule(
            d_model, kernel_size, conv_expansion_factor, dropout
        )
        self.ff2 = FeedForwardModule(d_model, d_ff, dropout)
        self.layer_norm = nn.LayerNorm(d_model)

    def forward(self, x, mask=None):
        # Macaron-Net style: Half residual connections
        x = x + 0.5 * self.ff1(x)
        x = x + self.attention(x, mask)
        x = x + self.conv(x)
        x = x + 0.5 * self.ff2(x)
        x = self.layer_norm(x)
        return x


class ConformerEncoder(nn.Module):
    """Conformer Encoder"""

    def __init__(
        self,
        input_dim,
        d_model=256,
        num_layers=6,
        num_heads=8,
        d_ff=1024,
        kernel_size=31,
        dropout=0.1,
    ):
        super().__init__()

        self.conv_subsample = ConvSubsample(input_dim, d_model)
        self.linear_proj = nn.Linear(d_model * ((input_dim + 3) // 4), d_model)
        self.dropout = nn.Dropout(dropout)

        self.layers = nn.ModuleList(
            [
                ConformerBlock(d_model, num_heads, d_ff, kernel_size, dropout=dropout)
                for _ in range(num_layers)
            ]
        )

    def forward(self, x, mask=None):
        # x: (batch, time, freq)
        x = self.conv_subsample(x)
        x = self.linear_proj(x)
        x = self.dropout(x)

        for layer in self.layers:
            x = layer(x, mask)

        return x


class ConformerLeakDetector(nn.Module):
    """
    Conformer-based Pipeline Leak Detection Model
    Multi-task: Detection + Distance Regression + Shape Classification
    """

    def __init__(self, config):
        super().__init__()

        self.config = config
        input_dim = config["n_mels"]  # Number of mel frequency bins
        d_model = config.get("d_model", 256)
        num_layers = config.get("num_layers", 6)
        num_heads = config.get("num_heads", 8)
        d_ff = config.get("d_ff", 1024)
        kernel_size = config.get("kernel_size", 31)
        dropout = config.get("dropout", 0.1)

        # Conformer Encoder
        self.encoder = ConformerEncoder(
            input_dim=input_dim,
            d_model=d_model,
            num_layers=num_layers,
            num_heads=num_heads,
            d_ff=d_ff,
            kernel_size=kernel_size,
            dropout=dropout,
        )

        # Multi-task heads
        # 1. Leak Detection (Binary Classification)
        self.detection_head = nn.Sequential(
            nn.Linear(d_model, config["detection_head"]["hidden_dim"]),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(
                config["detection_head"]["hidden_dim"],
                config["detection_head"]["num_classes"],
            ),
        )

        # 2. Distance Estimation (Regression)
        self.distance_head = nn.Sequential(
            nn.Linear(d_model, config["distance_head"]["hidden_dim"]),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(
                config["distance_head"]["hidden_dim"],
                config["distance_head"]["output_dim"],
            ),
        )

        # 3. Shape Classification
        self.shape_head = nn.Sequential(
            nn.Linear(d_model, config["shape_head"]["hidden_dim"]),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(
                config["shape_head"]["hidden_dim"], config["shape_head"]["num_classes"]
            ),
        )

    def forward(self, x, mask=None):
        """
        Args:
            x: (batch, time, n_mels) - Mel spectrogram
            mask: Optional attention mask

        Returns:
            detection_logits: (batch, num_classes)
            distance_pred: (batch, output_dim)
            shape_logits: (batch, num_classes)
        """
        # Encode
        encoded = self.encoder(x, mask)  # (batch, time, d_model)

        # Global average pooling over time dimension
        pooled = encoded.mean(dim=1)  # (batch, d_model)

        # Task-specific predictions
        detection_logits = self.detection_head(pooled)
        distance_pred = self.distance_head(pooled)
        shape_logits = self.shape_head(pooled)

        return detection_logits, distance_pred, shape_logits

    def predict(self, x):
        """Inference mode"""
        self.eval()
        with torch.no_grad():
            detection_logits, distance_pred, shape_logits = self.forward(x)

            detection_prob = F.softmax(detection_logits, dim=-1)
            detection_class = torch.argmax(detection_prob, dim=-1)

            shape_prob = F.softmax(shape_logits, dim=-1)
            shape_class = torch.argmax(shape_prob, dim=-1)

            return {
                "leak_probability": detection_prob[:, 1].cpu().numpy(),
                "leak_detected": detection_class.cpu().numpy(),
                "distance": distance_pred.squeeze().cpu().numpy(),
                "shape_probability": shape_prob.cpu().numpy(),
                "shape_class": shape_class.cpu().numpy(),
            }


if __name__ == "__main__":
    # Test the model
    config = {
        "n_mels": 128,
        "d_model": 256,
        "num_layers": 4,
        "num_heads": 8,
        "d_ff": 1024,
        "kernel_size": 31,
        "dropout": 0.1,
        "detection_head": {"hidden_dim": 256, "num_classes": 2},
        "distance_head": {"hidden_dim": 256, "output_dim": 1},
        "shape_head": {"hidden_dim": 256, "num_classes": 5},
    }

    model = ConformerLeakDetector(config)

    # Test forward pass
    batch_size = 4
    time_steps = 200
    n_mels = 128
    x = torch.randn(batch_size, time_steps, n_mels)

    detection_logits, distance_pred, shape_logits = model(x)

    print(f"Detection logits shape: {detection_logits.shape}")
    print(f"Distance prediction shape: {distance_pred.shape}")
    print(f"Shape logits shape: {shape_logits.shape}")
    print(f"\nModel parameters: {sum(p.numel() for p in model.parameters()):,}")

    # Test inference
    predictions = model.predict(x)
    print(f"\nPredictions:")
    for key, value in predictions.items():
        print(f"  {key}: shape {value.shape}")
