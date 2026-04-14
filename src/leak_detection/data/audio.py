"""Waveform loading helpers."""

from pathlib import Path

import numpy as np
import torch
import torchaudio
import torchaudio.transforms as T


def load_waveform(filepath: str | Path, sample_rate: int) -> torch.Tensor:
    """Load an audio file, convert it to mono, and resample if required."""
    waveform, original_sample_rate = torchaudio.load(str(filepath))

    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    if original_sample_rate != sample_rate:
        resampler = T.Resample(original_sample_rate, sample_rate)
        waveform = resampler(waveform)

    return waveform


def fit_waveform_length(
    waveform: torch.Tensor,
    sample_rate: int,
    max_length: float,
    random_crop: bool = False,
) -> torch.Tensor:
    """Pad or crop a waveform to the configured fixed duration."""
    target_length = int(sample_rate * max_length)
    current_length = waveform.shape[1]

    if current_length > target_length:
        if random_crop:
            start = int(np.random.randint(0, current_length - target_length))
        else:
            start = (current_length - target_length) // 2
        return waveform[:, start : start + target_length]

    if current_length < target_length:
        padding = target_length - current_length
        return torch.nn.functional.pad(waveform, (0, padding))

    return waveform
