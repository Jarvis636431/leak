"""Datasets for segmented CSV signals produced by prepare_dataset."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset


def _load_signal(path: str | Path, normalize: bool) -> torch.Tensor:
    signal = np.loadtxt(path, delimiter=",", dtype=np.float32)
    if signal.ndim > 1:
        signal = signal.squeeze(-1)

    tensor = torch.from_numpy(signal)
    if normalize:
        std = tensor.std()
        if std > 0:
            tensor = (tensor - tensor.mean()) / (std + 1e-6)
        else:
            tensor = tensor - tensor.mean()
    return tensor


def _filter_split(dataframe: pd.DataFrame, column: str, split: str) -> pd.DataFrame:
    pattern = f"/{split}/"
    mask = dataframe[column].astype(str).str.contains(pattern, regex=False)
    return dataframe.loc[mask].reset_index(drop=True)


class Stage2Dataset(Dataset):
    """Single-channel classification dataset built from stage2.csv."""

    def __init__(self, manifest_path: str | Path, split: str, normalize: bool = True):
        manifest = pd.read_csv(manifest_path)
        self.samples = _filter_split(manifest, "path", split)
        self.normalize = normalize

        if self.samples.empty:
            raise ValueError(f"No stage2 samples found for split={split!r} in {manifest_path}")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor | str]:
        row = self.samples.iloc[index]
        signal = _load_signal(row["path"], self.normalize).unsqueeze(0)
        label = torch.tensor(int(row["label"]), dtype=torch.long)
        return {"signal": signal, "target": label, "path": row["path"]}


class Stage1Dataset(Dataset):
    """Dual-channel distance regression dataset built from stage1.csv."""

    def __init__(self, manifest_path: str | Path, split: str, normalize: bool = True):
        manifest = pd.read_csv(manifest_path)
        self.samples = _filter_split(manifest, "path_left", split)
        self.normalize = normalize

        if self.samples.empty:
            raise ValueError(f"No stage1 samples found for split={split!r} in {manifest_path}")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor | str]:
        row = self.samples.iloc[index]
        left = _load_signal(row["path_left"], self.normalize)
        right = _load_signal(row["path_right"], self.normalize)
        signal = torch.stack((left, right), dim=0)
        target = torch.tensor(float(row["distance"]), dtype=torch.float32)
        return {
            "signal": signal,
            "target": target,
            "path_left": row["path_left"],
            "path_right": row["path_right"],
        }


def build_dataloaders(config: dict) -> dict[str, DataLoader]:
    """Build train/val/test dataloaders for the configured task."""
    task = config["task"]
    normalize = config["data"].get("normalize", True)
    manifest_path = config["data"]["manifest"]
    dataset_cls = Stage1Dataset if task == "stage1" else Stage2Dataset

    loaders: dict[str, DataLoader] = {}
    for split in ("train", "val", "test"):
        dataset = dataset_cls(manifest_path=manifest_path, split=split, normalize=normalize)
        loaders[split] = DataLoader(
            dataset,
            batch_size=config["training"]["batch_size"],
            shuffle=(split == "train"),
            num_workers=config["training"]["num_workers"],
            pin_memory=config["training"].get("pin_memory", False),
        )
    return loaders
