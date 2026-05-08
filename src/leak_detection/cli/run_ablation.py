"""Run ablation experiments over window length, input channels, loss, and network depth."""

from __future__ import annotations

import argparse
import copy
import csv
import sys
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

from leak_detection.data import Stage1Dataset, Stage2Dataset
from leak_detection.data.segmented import _filter_split, _load_signal
from leak_detection.training import Trainer
from leak_detection.utils import load_config

# ---------------------------------------------------------------------------
# Ablation variant definitions
# ---------------------------------------------------------------------------

WINDOW_VARIANTS: list[dict[str, Any]] = [
    {"name": "win_32000", "samples": 32000, "desc": "1.25 s window"},
    {"name": "win_64000", "samples": 64000, "desc": "2.5 s window"},
    {"name": "win_128000", "samples": 128000, "desc": "5 s window (default)"},
    {"name": "win_256000", "samples": 256000, "desc": "10 s window"},
]

CHANNEL_VARIANTS_STAGE2: list[dict[str, Any]] = [
    {"name": "ch1_single", "in_channels": 1, "desc": "Single-channel input (default)"},
    {"name": "ch2_dual", "in_channels": 2, "desc": "Dual-channel input"},
]

CHANNEL_VARIANTS_STAGE1: list[dict[str, Any]] = [
    {"name": "ch2_dual", "in_channels": 2, "desc": "Dual-channel input (default)"},
    {"name": "ch1_single", "in_channels": 1, "desc": "Single-channel input"},
]

LOSS_VARIANTS: list[dict[str, Any]] = [
    {"name": "loss_smooth_l1", "loss": "smooth_l1", "desc": "Smooth L1 loss (default)"},
    {"name": "loss_mse", "loss": "mse", "desc": "MSE loss"},
]

DEPTH_VARIANTS: list[dict[str, Any]] = [
    {"name": "depth_shallow", "channels": [16, 32, 64, 128], "kernel_sizes": [15, 9, 7, 5], "strides": [4, 4, 4, 4], "desc": "Shallow: 16→32→64→128"},
    {"name": "depth_default", "channels": [32, 64, 128, 256], "kernel_sizes": [15, 9, 7, 5], "strides": [4, 4, 4, 4], "desc": "Default: 32→64→128→256"},
    {"name": "depth_deep", "channels": [32, 64, 128, 256, 512], "kernel_sizes": [15, 9, 7, 5, 3], "strides": [4, 4, 4, 4, 2], "desc": "Deep: 32→64→128→256→512"},
]

# ---------------------------------------------------------------------------
# Data-loading helpers for ablation
# ---------------------------------------------------------------------------


def _make_truncated_loader(config: dict, split: str, num_samples: int) -> DataLoader:
    """Create a dataloader that truncates signals to *num_samples*."""
    task = config["task"]
    normalize = config["data"].get("normalize", True)
    manifest_path = config["data"]["manifest"]

    if task == "stage2":
        base_cls = Stage2Dataset

        class TruncatedDataset(base_cls):  # type: ignore
            def __getitem__(self, index: int) -> dict:
                item = super().__getitem__(index)
                sig = item["signal"]
                if sig.shape[-1] > num_samples:
                    sig = sig[..., :num_samples]
                item["signal"] = sig
                return item
    else:
        base_cls = Stage1Dataset

        class TruncatedDataset(base_cls):  # type: ignore
            def __getitem__(self, index: int) -> dict:
                item = super().__getitem__(index)
                sig = item["signal"]
                if sig.shape[-1] > num_samples:
                    sig = sig[..., :num_samples]
                item["signal"] = sig
                return item

    dataset = TruncatedDataset(manifest_path, split, normalize)
    return DataLoader(
        dataset,
        batch_size=config["training"]["batch_size"],
        shuffle=(split == "train"),
        num_workers=config["training"].get("num_workers", 0),
        pin_memory=config["training"].get("pin_memory", False),
    )


def _stage2_pair_key(path: str) -> str:
    stem = Path(path).stem
    if stem.endswith("_left"):
        return stem.removesuffix("_left")
    if stem.endswith("_right"):
        return stem.removesuffix("_right")
    return stem


def _make_channel_loader(config: dict, split: str, in_channels: int) -> DataLoader:
    """Create a dataloader whose signal channel count matches the ablation model."""
    task = config["task"]
    normalize = config["data"].get("normalize", True)
    manifest_path = config["data"]["manifest"]

    if task == "stage1":
        if in_channels == 2:
            dataset = Stage1Dataset(manifest_path, split, normalize)
        elif in_channels == 1:
            class SingleChannelStage1Dataset(Stage1Dataset):  # type: ignore[misc]
                def __getitem__(self, index: int) -> dict:
                    item = super().__getitem__(index)
                    item["signal"] = item["signal"][:1, :]
                    return item

            dataset = SingleChannelStage1Dataset(manifest_path, split, normalize)
        else:
            raise ValueError(f"Unsupported stage1 channel count: {in_channels}")
    else:
        if in_channels == 1:
            dataset = Stage2Dataset(manifest_path, split, normalize)
        elif in_channels == 2:
            class PairedStage2Dataset(torch.utils.data.Dataset):
                def __init__(self) -> None:
                    manifest = pd.read_csv(manifest_path)
                    samples = _filter_split(manifest, "path", split)
                    grouped: dict[str, dict[str, Any]] = {}
                    for _, row in samples.iterrows():
                        path = str(row["path"])
                        key = _stage2_pair_key(path)
                        entry = grouped.setdefault(key, {"label": int(row["label"])})
                        if path.endswith("_left.csv"):
                            entry["left"] = path
                        elif path.endswith("_right.csv"):
                            entry["right"] = path
                    self.samples = [
                        entry
                        for entry in grouped.values()
                        if "left" in entry and "right" in entry
                    ]
                    if not self.samples:
                        raise ValueError(f"No paired stage2 samples found for split={split!r} in {manifest_path}")

                def __len__(self) -> int:
                    return len(self.samples)

                def __getitem__(self, index: int) -> dict:
                    row = self.samples[index]
                    left = _load_signal(row["left"], normalize)
                    right = _load_signal(row["right"], normalize)
                    signal = torch.stack((left, right), dim=0)
                    target = torch.tensor(row["label"], dtype=torch.long)
                    return {"signal": signal, "target": target, "path": row["left"]}

            dataset = PairedStage2Dataset()
        else:
            raise ValueError(f"Unsupported stage2 channel count: {in_channels}")

    return DataLoader(
        dataset,
        batch_size=config["training"]["batch_size"],
        shuffle=(split == "train"),
        num_workers=config["training"].get("num_workers", 0),
        pin_memory=config["training"].get("pin_memory", False),
    )


# ---------------------------------------------------------------------------
# Single ablation runner
# ---------------------------------------------------------------------------


def _run_ablation_variant(
    base_config: dict,
    variant_name: str,
    output_base: str | Path,
    train_loader_override: Callable | None = None,
    val_loader_override: Callable | None = None,
    test_loader_override: Callable | None = None,
    model_override_fn: Callable | None = None,
    config_modifier_fn: Callable | None = None,
) -> dict[str, Any]:
    """Run one ablation variant and return its test metrics."""
    config = copy.deepcopy(base_config)
    if config_modifier_fn:
        config_modifier_fn(config)

    variant_dir = Path(output_base) / variant_name
    variant_dir.mkdir(parents=True, exist_ok=True)

    # Write variant config
    with open(variant_dir / "config.yaml", "w") as f:
        import yaml
        yaml.dump(config, f)

    trainer = Trainer(config, str(variant_dir))

    # Apply loader overrides
    if train_loader_override is not None:
        trainer.loaders["train"] = train_loader_override(config, "train")
    if val_loader_override is not None:
        trainer.loaders["val"] = val_loader_override(config, "val")
    if test_loader_override is not None:
        trainer.loaders["test"] = test_loader_override(config, "test")

    # Apply model override
    if model_override_fn is not None:
        model = model_override_fn(config)
        trainer.model = model.to(trainer.device)
        trainer.optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=config["training"]["learning_rate"],
            weight_decay=config["training"]["weight_decay"],
        )
        trainer.scheduler = trainer._build_scheduler()
        trainer.criterion = trainer._build_criterion()

    trainer.train()

    # Collect test metrics from best checkpoint
    best_path = variant_dir / "checkpoint_best.pth"
    checkpoint = torch.load(best_path, map_location=trainer.device)
    trainer.model.load_state_dict(checkpoint["model_state_dict"])
    test_metrics = trainer._run_epoch(split="test", training=False)

    summary: dict[str, Any] = {"variant": variant_name}
    if config["task"] == "stage2":
        summary["test_loss"] = test_metrics["loss"]
        summary["test_accuracy"] = test_metrics["accuracy"]
        summary["test_macro_f1"] = test_metrics["macro_f1"]
        summary["test_file_accuracy"] = test_metrics["file_accuracy"]
        summary["test_file_macro_f1"] = test_metrics["file_macro_f1"]
    else:
        summary["test_loss"] = test_metrics["loss"]
        summary["test_mae"] = test_metrics["mae"]
        summary["test_rmse"] = test_metrics["rmse"]
        summary["test_within_1_0"] = test_metrics["within_1_0"]
        summary["test_file_mae"] = test_metrics["file_mae"]
        summary["test_file_rmse"] = test_metrics["file_rmse"]
        summary["test_file_within_1_0"] = test_metrics["file_within_1_0"]

    return summary


# ---------------------------------------------------------------------------
# Per-dimension runners
# ---------------------------------------------------------------------------


def run_window_ablation(base_config: dict, output_base: str | Path) -> list[dict[str, Any]]:
    """Ablate input signal length."""
    results: list[dict[str, Any]] = []
    for variant in WINDOW_VARIANTS:
        print(f"\n{'='*60}\nWindow ablation: {variant['name']} ({variant['desc']})\n{'='*60}")
        summary = _run_ablation_variant(
            base_config,
            f"window_{variant['name']}",
            output_base,
            train_loader_override=lambda cfg, split, ns=variant["samples"]: _make_truncated_loader(cfg, split, ns),
            val_loader_override=lambda cfg, split, ns=variant["samples"]: _make_truncated_loader(cfg, split, ns),
            test_loader_override=lambda cfg, split, ns=variant["samples"]: _make_truncated_loader(cfg, split, ns),
        )
        summary["window_samples"] = variant["samples"]
        results.append(summary)
    return results


def run_channel_ablation(base_config: dict, output_base: str | Path) -> list[dict[str, Any]]:
    """Ablate number of input channels."""
    task = base_config["task"]
    variants = CHANNEL_VARIANTS_STAGE2 if task == "stage2" else CHANNEL_VARIANTS_STAGE1

    results: list[dict[str, Any]] = []
    for variant in variants:
        print(f"\n{'='*60}\nChannel ablation: {variant['name']} ({variant['desc']})\n{'='*60}")

        def _modify_channel_config(cfg: dict, in_channels: int = variant["in_channels"]) -> None:
            cfg["model"]["in_channels"] = in_channels

        summary = _run_ablation_variant(
            base_config,
            f"channel_{variant['name']}",
            output_base,
            train_loader_override=lambda cfg, split, ic=variant["in_channels"]: _make_channel_loader(cfg, split, ic),
            val_loader_override=lambda cfg, split, ic=variant["in_channels"]: _make_channel_loader(cfg, split, ic),
            test_loader_override=lambda cfg, split, ic=variant["in_channels"]: _make_channel_loader(cfg, split, ic),
            config_modifier_fn=_modify_channel_config,
        )
        summary["in_channels"] = variant["in_channels"]
        results.append(summary)
    return results


def run_loss_ablation(base_config: dict, output_base: str | Path) -> list[dict[str, Any]]:
    """Ablate regression loss function (stage1 only)."""
    if base_config["task"] != "stage1":
        print("Loss ablation is only meaningful for stage1 (regression). Skipping.")
        return []

    results: list[dict[str, Any]] = []
    for variant in LOSS_VARIANTS:
        print(f"\n{'='*60}\nLoss ablation: {variant['name']} ({variant['desc']})\n{'='*60}")

        def _modify_loss_config(cfg: dict, loss_name: str = variant["loss"]) -> None:
            cfg["training"]["regression_loss"] = loss_name

        summary = _run_ablation_variant(
            base_config,
            f"loss_{variant['name']}",
            output_base,
            config_modifier_fn=_modify_loss_config,
        )
        summary["loss_function"] = variant["loss"]
        results.append(summary)
    return results


def run_depth_ablation(base_config: dict, output_base: str | Path) -> list[dict[str, Any]]:
    """Ablate network depth (channel configuration)."""
    results: list[dict[str, Any]] = []
    for variant in DEPTH_VARIANTS:
        print(f"\n{'='*60}\nDepth ablation: {variant['name']} ({variant['desc']})\n{'='*60}")

        def _modify_depth_config(cfg: dict, ch=variant["channels"], ks=variant["kernel_sizes"], st=variant["strides"]) -> None:
            cfg["model"]["channels"] = ch
            cfg["model"]["kernel_sizes"] = ks
            cfg["model"]["strides"] = st

        summary = _run_ablation_variant(
            base_config,
            f"depth_{variant['name']}",
            output_base,
            config_modifier_fn=_modify_depth_config,
        )
        summary["channels"] = str(variant["channels"])
        results.append(summary)
    return results


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

ABLATION_FIELDS = [
    "variant",
    "test_loss",
    "test_accuracy",
    "test_macro_f1",
    "test_file_accuracy",
    "test_file_macro_f1",
]
REGRESSION_FIELDS = [
    "variant",
    "test_loss",
    "test_mae",
    "test_rmse",
    "test_within_1_0",
    "test_file_mae",
    "test_file_rmse",
    "test_file_within_1_0",
]


def _write_results(results: list[dict[str, Any]], output_path: str | Path, fields: list[str]) -> None:
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(f"\nResults saved to {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ablation experiments")
    parser.add_argument("--config", type=str, required=True, help="Base config YAML")
    parser.add_argument("--output-dir", type=str, default="outputs/ablation", help="Output base directory")
    parser.add_argument(
        "--ablation",
        type=str,
        nargs="+",
        choices=["window", "channel", "loss", "depth", "all"],
        default=["all"],
        help="Which ablation dimensions to run",
    )
    parser.add_argument("--resume", type=str, default=None, help="Path to checkpoint to resume from (not used in ablation)")
    args = parser.parse_args()

    base_config = load_config(args.config)
    output_base = Path(args.output_dir) / f"{base_config['task']}_{Path(args.config).stem}"
    output_base.mkdir(parents=True, exist_ok=True)

    ablations = args.ablation
    if "all" in ablations:
        ablations = ["window", "channel", "loss", "depth"]

    all_results: list[dict[str, Any]] = []

    if "window" in ablations:
        results = run_window_ablation(base_config, str(output_base))
        all_results.extend(results)

    if "channel" in ablations:
        results = run_channel_ablation(base_config, str(output_base))
        all_results.extend(results)

    if "loss" in ablations:
        results = run_loss_ablation(base_config, str(output_base))
        all_results.extend(results)

    if "depth" in ablations:
        results = run_depth_ablation(base_config, str(output_base))
        all_results.extend(results)

    # Write combined results
    fields = REGRESSION_FIELDS if base_config["task"] == "stage1" else ABLATION_FIELDS
    _write_results(all_results, output_base / "ablation_results.csv", fields)

    # Print summary table
    print(f"\n{'='*60}")
    print("Ablation Results Summary")
    print(f"{'='*60}")
    field_widths = {f: max(len(f), 12) for f in fields}
    header = " | ".join(f"{f:<{field_widths[f]}}" for f in fields)
    print(header)
    print("-" * len(header))
    for row in all_results:
        vals = []
        for f in fields:
            v = row.get(f, "")
            vals.append(f"{v:<{field_widths[f]}}" if isinstance(v, str) else f"{v:<{field_widths[f]}.4f}")
        print(" | ".join(vals))


if __name__ == "__main__":
    main()
