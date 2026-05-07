"""Plot training curves (loss, accuracy / MAE) from TensorBoard event logs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator


def _load_scalars(log_dir: str | Path, tag: str) -> list[tuple[int, float]]:
    """Load scalar events for a given tag from a TensorBoard log directory."""
    ea = EventAccumulator(str(log_dir))
    ea.Reload()
    available_tags = ea.Tags().get("scalars", [])
    if tag not in available_tags:
        return []
    events = ea.Scalars(tag)
    return [(e.step, e.value) for e in events]


def _save_plot_data(
    curves: dict[str, list[tuple[int, float]]],
    output_dir: str | Path,
) -> None:
    """Save raw curve data as JSON for later reuse."""
    serializable = {k: [{"step": s, "value": v} for s, v in v_list] for k, v_list in curves.items()}
    path = Path(output_dir) / "training_curves_data.json"
    with open(path, "w") as f:
        json.dump(serializable, f, indent=2)
    print(f"Raw curve data saved to {path}")


def _plot_curves_single_ax(
    ax: plt.Axes,
    curves: dict[str, list[tuple[int, float]]],
    ylabel: str,
    title: str,
) -> None:
    """Plot multiple curves on a single axis."""
    for label, steps_and_values in curves.items():
        if not steps_and_values:
            continue
        steps, values = zip(*steps_and_values)
        ax.plot(steps, values, label=label, linewidth=1.5)

    ax.set_xlabel("Epoch", fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_title(title, fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.tick_params(labelsize=10)


def plot_training_curves(
    log_dir: str | Path,
    output_dir: str | Path,
    task: str,
    dpi: int = 300,
) -> None:
    """Generate training curve plots from TensorBoard logs."""
    log_dir = Path(log_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Define tag groups
    if task == "stage2":
        panels = {
            "loss": {
                "ylabel": "Loss",
                "tags": {"Train": "Loss/train", "Validation": "Loss/val"},
            },
            "accuracy": {
                "ylabel": "Accuracy",
                "tags": {
                    "Train Accuracy": "Metrics/train_accuracy",
                    "Val Accuracy": "Metrics/val_accuracy",
                    "Train File Accuracy": "Metrics/train_file_accuracy",
                    "Val File Accuracy": "Metrics/val_file_accuracy",
                },
            },
            "f1": {
                "ylabel": "Macro F1",
                "tags": {
                    "Train F1": "Metrics/train_macro_f1",
                    "Val F1": "Metrics/val_macro_f1",
                    "Train File F1": "Metrics/train_file_macro_f1",
                    "Val File F1": "Metrics/val_file_macro_f1",
                },
            },
        }
    else:
        panels = {
            "loss": {
                "ylabel": "Loss",
                "tags": {"Train": "Loss/train", "Validation": "Loss/val"},
            },
            "mae": {
                "ylabel": "MAE",
                "tags": {
                    "Train MAE": "Metrics/train_mae",
                    "Val MAE": "Metrics/val_mae",
                    "Train File MAE": "Metrics/train_file_mae",
                    "Val File MAE": "Metrics/val_file_mae",
                },
            },
            "rmse_within": {
                "ylabel": "Value",
                "tags": {
                    "Val RMSE": "Metrics/val_rmse",
                    "Val Within 1.0": "Metrics/val_within_1_0",
                    "Val Bias": "Metrics/val_bias",
                },
            },
        }

    all_curves: dict[str, list[tuple[int, float]]] = {}

    for panel_name, panel_info in panels.items():
        curves: dict[str, list[tuple[int, float]]] = {}
        for label, tag in panel_info["tags"].items():
            curve = _load_scalars(log_dir, tag)
            curves[label] = curve
            all_curves[f"{panel_name}/{label}"] = curve

        fig, ax = plt.subplots(figsize=(7, 4.5))
        _plot_curves_single_ax(ax, curves, panel_info["ylabel"], panel_name.upper())
        fig.tight_layout()
        fig.savefig(output_dir / f"{panel_name}_curves.png", dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        print(f"{panel_name}_curves.png saved")

    # Learning rate panel
    lr_curve = _load_scalars(log_dir, "LR")
    if lr_curve:
        fig, ax = plt.subplots(figsize=(7, 3))
        lr_steps, lr_vals = zip(*lr_curve)
        ax.plot(lr_steps, lr_vals, linewidth=1.5, color="gray")
        ax.set_xlabel("Epoch", fontsize=11)
        ax.set_ylabel("Learning Rate", fontsize=11)
        ax.set_title("Learning Rate Schedule", fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=10)
        fig.tight_layout()
        fig.savefig(output_dir / "lr_curve.png", dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        print("lr_curve.png saved")
        all_curves["lr"] = lr_curve

    _save_plot_data(all_curves, output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot training curves from TensorBoard logs in an output directory"
    )
    parser.add_argument(
        "--log-dir", type=str, required=True, help="Path to TensorBoard log directory (e.g. outputs/stage2/<run>/logs)"
    )
    parser.add_argument(
        "--output-dir", type=str, default=None, help="Output directory for plots (default: parent of log_dir)"
    )
    parser.add_argument("--task", type=str, default=None, help="Task type: stage2 or stage1 (auto-detected if omitted)")
    parser.add_argument("--dpi", type=int, default=300, help="Output image DPI")
    args = parser.parse_args()

    log_dir = Path(args.log_dir)

    # Auto-detect task from config if available
    task = args.task
    if task is None:
        config_path = log_dir.parent / "config.yaml"
        config_backup = log_dir.parent.parent / "config.yaml"
        for candidate in [config_path, config_backup]:
            if candidate.exists():
                import yaml
                cfg = yaml.safe_load(candidate.read_text())
                task = cfg.get("task")
                break
    if task not in ("stage1", "stage2"):
        raise ValueError(
            "Could not auto-detect task; please specify --task stage1 or --task stage2"
        )

    output_dir = Path(args.output_dir) if args.output_dir else log_dir.parent
    plot_training_curves(log_dir, output_dir, task, dpi=args.dpi)


if __name__ == "__main__":
    main()
