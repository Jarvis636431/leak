"""Dataset and dataloader definitions."""

from pathlib import Path

import pandas as pd
import torchaudio.transforms as T
from torch.utils.data import DataLoader, Dataset
import torch

from leak_detection.data.audio import fit_waveform_length, load_waveform
from leak_detection.data.features import build_mel_transform, extract_mel_features


class LeakAudioDataset(Dataset):
    """
    Dataset for pipeline leak audio classification
    Supports: leak detection, distance estimation, shape classification
    """

    def __init__(
        self,
        audio_dir,
        annotation_file,
        sample_rate=16000,
        n_mels=128,
        n_fft=1024,
        hop_length=512,
        max_length=5.0,
        augment=False,
    ):
        """
        Args:
            audio_dir: Directory containing audio files
            annotation_file: CSV file with columns:
                - filename: audio file name
                - has_leak: 0/1 for leak detection
                - distance: float for distance (meters)
                - shape: int for shape class
            sample_rate: Target sample rate
            n_mels: Number of mel frequency bins
            n_fft: FFT window size
            hop_length: Hop length for STFT
            max_length: Maximum audio length in seconds
            augment: Whether to apply data augmentation
        """
        self.audio_dir = Path(audio_dir)
        self.annotations = pd.read_csv(annotation_file)
        self.sample_rate = sample_rate
        self.max_length = max_length
        self.augment = augment

        self.mel_spectrogram, self.amplitude_to_db = build_mel_transform(
            sample_rate=sample_rate,
            n_mels=n_mels,
            n_fft=n_fft,
            hop_length=hop_length,
        )

        # Augmentation transforms
        if augment:
            self.time_masking = T.TimeMasking(time_mask_param=10)
            self.freq_masking = T.FrequencyMasking(freq_mask_param=10)

    def __len__(self):
        return len(self.annotations)

    def _apply_augmentation(self, spec):
        """Apply SpecAugment"""
        if self.augment:
            spec = self.time_masking(spec)
            spec = self.freq_masking(spec)
        return spec

    def __getitem__(self, idx):
        # Get annotation
        row = self.annotations.iloc[idx]

        # Load audio
        filepath = self.audio_dir / row["filename"]
        waveform = load_waveform(filepath, self.sample_rate)

        waveform = fit_waveform_length(
            waveform,
            sample_rate=self.sample_rate,
            max_length=self.max_length,
            random_crop=self.augment,
        )

        mel_spec = extract_mel_features(
            waveform,
            mel_spectrogram=self.mel_spectrogram,
            amplitude_to_db=self.amplitude_to_db,
        )

        mel_spec = self._apply_augmentation(mel_spec)

        has_leak = torch.tensor(row["has_leak"], dtype=torch.long)
        distance = torch.tensor(row["distance"], dtype=torch.float32)
        shape = torch.tensor(row["shape"], dtype=torch.long)

        return {
            "audio": mel_spec,
            "has_leak": has_leak,
            "distance": distance,
            "shape": shape,
            "filename": row["filename"],
        }


def create_dataloader(config, split="train"):
    """
    Create DataLoader for a specific split

    Args:
        config: Configuration dict
        split: 'train', 'val', or 'test'
    """
    audio_dir = config["data"][f"{split}_audio_dir"]
    annotation_file = config["data"][f"{split}_annotation_file"]

    dataset = LeakAudioDataset(
        audio_dir=audio_dir,
        annotation_file=annotation_file,
        sample_rate=config["audio"]["sample_rate"],
        n_mels=config["audio"]["n_mels"],
        n_fft=config["audio"]["n_fft"],
        hop_length=config["audio"]["hop_length"],
        max_length=config["audio"]["max_length"],
        augment=(split == "train"),
    )

    dataloader = DataLoader(
        dataset,
        batch_size=config["training"]["batch_size"],
        shuffle=(split == "train"),
        num_workers=config["training"]["num_workers"],
        pin_memory=True,
    )

    return dataloader
