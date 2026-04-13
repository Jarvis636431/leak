"""Runtime helpers shared by CLI entry points."""

from pathlib import Path

import torch
import yaml


def load_config(config_path: str | Path) -> dict:
    """Load a YAML config file."""
    with open(config_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def resolve_device() -> torch.device:
    """Choose the best available PyTorch device for the current machine."""
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")
