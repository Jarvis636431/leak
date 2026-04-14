"""Feature extraction helpers for audio inputs."""

import torch
import torchaudio.transforms as T


def build_mel_transform(
    sample_rate: int,
    n_mels: int,
    n_fft: int,
    hop_length: int,
) -> tuple[T.MelSpectrogram, T.AmplitudeToDB]:
    """Create the mel spectrogram and dB transforms."""
    mel_spectrogram = T.MelSpectrogram(
        sample_rate=sample_rate,
        n_fft=n_fft,
        hop_length=hop_length,
        n_mels=n_mels,
    )
    amplitude_to_db = T.AmplitudeToDB(st_ref=1.0, top_db=80.0)
    return mel_spectrogram, amplitude_to_db


def normalize_mel_spectrogram(mel_spectrogram: torch.Tensor) -> torch.Tensor:
    """Normalize the mel spectrogram per sample."""
    return (mel_spectrogram - mel_spectrogram.mean()) / (mel_spectrogram.std() + 1e-8)


def extract_mel_features(
    waveform: torch.Tensor,
    mel_spectrogram: T.MelSpectrogram,
    amplitude_to_db: T.AmplitudeToDB,
) -> torch.Tensor:
    """Convert a waveform to normalized `(time, n_mels)` features."""
    mel_spec = mel_spectrogram(waveform)
    mel_spec = amplitude_to_db(mel_spec)
    mel_spec = normalize_mel_spectrogram(mel_spec)
    return mel_spec.squeeze(0).transpose(0, 1)
