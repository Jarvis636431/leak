"""
Utility functions for pipeline leak detection
"""

import os
import random
import numpy as np
import torch
import torchaudio


def set_seed(seed=42):
    """Set random seed for reproducibility"""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def count_parameters(model):
    """Count trainable and total parameters"""
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return total, trainable


def get_audio_duration(filepath):
    """Get audio file duration in seconds"""
    info = torchaudio.info(filepath)
    return info.num_frames / info.sample_rate


def get_audio_stats(audio_dir):
    """Get statistics of audio files in directory"""
    durations = []
    sample_rates = []
    channels = []

    for filename in os.listdir(audio_dir):
        if filename.endswith((".wav", ".mp3", ".flac")):
            filepath = os.path.join(audio_dir, filename)
            try:
                info = torchaudio.info(filepath)
                durations.append(info.num_frames / info.sample_rate)
                sample_rates.append(info.sample_rate)
                channels.append(info.num_channels)
            except Exception as e:
                print(f"Error reading {filename}: {e}")

    return {
        "num_files": len(durations),
        "duration_mean": np.mean(durations),
        "duration_std": np.std(durations),
        "duration_min": np.min(durations),
        "duration_max": np.max(durations),
        "sample_rate_mode": max(set(sample_rates), key=sample_rates.count),
        "channels_mode": max(set(channels), key=channels.count),
    }


def collate_fn(batch):
    """Custom collate function for variable length sequences"""
    # This is a simple version - assumes all sequences are padded to same length
    return torch.utils.data.dataloader.default_collate(batch)


class EarlyStopping:
    """Early stopping handler"""

    def __init__(self, patience=10, min_delta=0, mode="min"):
        self.patience = patience
        self.min_delta = min_delta
        self.mode = mode
        self.counter = 0
        self.best_score = None
        self.early_stop = False

    def __call__(self, score):
        if self.best_score is None:
            self.best_score = score
            return False

        if self.mode == "min":
            improved = score < (self.best_score - self.min_delta)
        else:
            improved = score > (self.best_score + self.min_delta)

        if improved:
            self.best_score = score
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True

        return self.early_stop


def save_checkpoint(model, optimizer, epoch, loss, filepath):
    """Save training checkpoint"""
    checkpoint = {
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "loss": loss,
    }
    torch.save(checkpoint, filepath)


def load_checkpoint(filepath, model, optimizer=None, device="cpu"):
    """Load training checkpoint"""
    checkpoint = torch.load(filepath, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])

    if optimizer is not None and "optimizer_state_dict" in checkpoint:
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])

    return checkpoint.get("epoch", 0), checkpoint.get("loss", None)
