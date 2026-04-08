"""
Dataset and DataLoader for Pipeline Leak Detection
"""

import os
import torch
import numpy as np
import pandas as pd
from torch.utils.data import Dataset, DataLoader
import torchaudio
import torchaudio.transforms as T


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
        self.audio_dir = audio_dir
        self.annotations = pd.read_csv(annotation_file)
        self.sample_rate = sample_rate
        self.max_length = max_length
        self.augment = augment

        # Audio transforms
        self.mel_spectrogram = T.MelSpectrogram(
            sample_rate=sample_rate, n_fft=n_fft, hop_length=hop_length, n_mels=n_mels
        )
        self.amplitude_to_db = T.AmplitudeToDB(st_ref=1.0, top_db=80.0)

        # Augmentation transforms
        if augment:
            self.time_masking = T.TimeMasking(time_mask_param=10)
            self.freq_masking = T.FrequencyMasking(freq_mask_param=10)

    def __len__(self):
        return len(self.annotations)

    def _load_audio(self, filepath):
        """Load and preprocess audio file"""
        waveform, sr = torchaudio.load(filepath)

        # Convert to mono if stereo
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)

        # Resample if necessary
        if sr != self.sample_rate:
            resampler = T.Resample(sr, self.sample_rate)
            waveform = resampler(waveform)

        return waveform

    def _pad_or_truncate(self, waveform):
        """Pad or truncate to fixed length"""
        target_length = int(self.sample_rate * self.max_length)
        current_length = waveform.shape[1]

        if current_length > target_length:
            # Random crop during training, center crop during validation
            if self.augment:
                start = np.random.randint(0, current_length - target_length)
            else:
                start = (current_length - target_length) // 2
            waveform = waveform[:, start : start + target_length]
        elif current_length < target_length:
            # Pad with zeros
            padding = target_length - current_length
            waveform = torch.nn.functional.pad(waveform, (0, padding))

        return waveform

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
        filepath = os.path.join(self.audio_dir, row["filename"])
        waveform = self._load_audio(filepath)

        # Pad/truncate
        waveform = self._pad_or_truncate(waveform)

        # Convert to mel spectrogram
        mel_spec = self.mel_spectrogram(waveform)  # (1, n_mels, time)
        mel_spec = self.amplitude_to_db(mel_spec)

        # Normalize
        mel_spec = (mel_spec - mel_spec.mean()) / (mel_spec.std() + 1e-8)

        # Apply augmentation
        mel_spec = self._apply_augmentation(mel_spec)

        # Reshape to (time, n_mels) for Conformer
        mel_spec = mel_spec.squeeze(0).transpose(0, 1)  # (time, n_mels)

        # Get labels
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


if __name__ == "__main__":
    # Test dataset
    import tempfile
    import os

    # Create dummy data
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create dummy audio files
        audio_dir = os.path.join(tmpdir, "audio")
        os.makedirs(audio_dir)

        for i in range(10):
            waveform = torch.randn(1, 16000 * 3)  # 3 seconds
            torchaudio.save(os.path.join(audio_dir, f"audio_{i}.wav"), waveform, 16000)

        # Create dummy annotation CSV
        annotations = pd.DataFrame(
            {
                "filename": [f"audio_{i}.wav" for i in range(10)],
                "has_leak": np.random.randint(0, 2, 10),
                "distance": np.random.uniform(0, 100, 10),
                "shape": np.random.randint(0, 5, 10),
            }
        )
        annotation_file = os.path.join(tmpdir, "annotations.csv")
        annotations.to_csv(annotation_file, index=False)

        # Test dataset
        dataset = LeakAudioDataset(
            audio_dir=audio_dir,
            annotation_file=annotation_file,
            sample_rate=16000,
            n_mels=128,
            max_length=5.0,
            augment=True,
        )

        print(f"Dataset size: {len(dataset)}")

        # Test getitem
        sample = dataset[0]
        print(f"\nSample shapes:")
        print(f"  Audio: {sample['audio'].shape}")
        print(f"  Has leak: {sample['has_leak']}")
        print(f"  Distance: {sample['distance']}")
        print(f"  Shape: {sample['shape']}")

        # Test dataloader
        from torch.utils.data import DataLoader

        dataloader = DataLoader(dataset, batch_size=4, shuffle=True)

        batch = next(iter(dataloader))
        print(f"\nBatch shapes:")
        print(f"  Audio: {batch['audio'].shape}")
        print(f"  Has leak: {batch['has_leak'].shape}")
        print(f"  Distance: {batch['distance'].shape}")
        print(f"  Shape: {batch['shape'].shape}")
