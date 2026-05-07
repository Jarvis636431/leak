"""Publication-quality confusion matrix heatmap from a trained checkpoint."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.metrics import confusion_matrix

from leak_detection.data import build_dataloaders
from leak_detection.models import build_model
from leak_detection.utils import load_config, resolve_device, set_seed


def _aggregate_stage2_by_file(
    paths: list[str],
    targets: np.ndarray,
    logits: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Majority-vote aggregation per raw file id."""
    import re

    pattern = re.compile(r"(ABC\d+)_seg\d+")
    grouped: dict[str, dict] = {}
    for path, target, logit in zip(paths, targets, logits):
        match = pattern.search(Path(path).stem)
        if match is None:
            continue
        raw_id = match.group(1)
        entry = grouped.setdefault(raw_id, {"target": int(target), "logits": []})
        entry["logits"].append(logit)

    file_targets, file_preds = [], []
    for raw_id in sorted(grouped):
        entry = grouped[raw_id]
        mean_logits = np.mean(np.stack(entry["logits"], axis=0), axis=0)
        file_targets.append(entry["target"])
        file_preds.append(int(np.argmax(mean_logits)))
    return np.asarray(file_targets, dtype=np.int64), np.asarray(file_preds, dtype=np.int64)


def plot_confusion_matrix(
    cm: np.ndarray,
    class_names: list[str],
    output_path: str | Path,
    title: str = "Confusion Matrix",
    normalize: bool = True,
    figsize: tuple[int, int] = (6, 5),
) -> None:
    """Render and save a publication-quality confusion matrix heatmap."""
    if normalize:
        cm = cm.astype(np.float64)
        row_sums = cm.sum(axis=1, keepdims=True)
        row_sums = np.where(row_sums == 0, 1, row_sums)
        cm = cm / row_sums
        fmt = ".2f"
        vmax = 1.0
    else:
        fmt = "d"
        vmax = cm.max()

    fig, ax = plt.subplots(figsize=figsize)
    im = ax.imshow(cm, interpolation="nearest", cmap="Blues", vmin=0.0, vmax=vmax)

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=10)

    ax.set_xticks(range(len(class_names)))
    ax.set_yticks(range(len(class_names)))
    ax.set_xticklabels(class_names, fontsize=11)
    ax.set_yticklabels(class_names, fontsize=11)
    ax.set_xlabel("Predicted Label", fontsize=12)
    ax.set_ylabel("True Label", fontsize=12)
    ax.set_title(title, fontsize=13, pad=12)

    thresh = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(
                j,
                i,
                f"{cm[i, j]:.2f}" if normalize else f"{int(cm[i, j])}",
                ha="center",
                va="center",
                fontsize=11,
                color="white" if cm[i, j] > thresh else "black",
            )

    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Confusion matrix saved to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot confusion matrix from a trained stage2 checkpoint"
    )
    parser.add_argument("--checkpoint", type=str, required=True, help="Path to checkpoint_best.pth")
    parser.add_argument("--config", type=str, required=True, help="Path to task config YAML")
    parser.add_argument(
        "--output", type=str, default=None, help="Output image path (default: <checkpoint_dir>/confusion_matrix.png)"
    )
    parser.add_argument(
        "--segment",
        action="store_true",
        default=False,
        help="Plot segment-level (rather than file-level) confusion matrix",
    )
    parser.add_argument("--no-normalize", action="store_true", default=False, help="Show raw counts")
    parser.add_argument("--class-names", type=str, nargs="+", default=None, help="Class label names")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    set_seed(args.seed)
    device = resolve_device()

    config = load_config(args.config)
    if config["task"] != "stage2":
        raise ValueError("Confusion matrix plotting is only supported for stage2 (classification) tasks.")

    checkpoint_dir = Path(args.checkpoint).parent
    output_path = args.output or str(checkpoint_dir / "confusion_matrix.png")

    print("Building model and loading checkpoint...")
    model = build_model(config).to(device)
    checkpoint = torch.load(args.checkpoint, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    print("Loading test data...")
    loaders = build_dataloaders(config)

    num_classes = config["model"]["num_classes"]
    default_class_names = [str(i) for i in range(num_classes)]
    class_names = args.class_names or default_class_names
    if len(class_names) != num_classes:
        raise ValueError(f"Expected {num_classes} class names, got {len(class_names)}")

    all_targets: list[np.ndarray] = []
    all_predictions: list[np.ndarray] = []
    all_logits: list[np.ndarray] = []
    all_paths: list[str] = []

    with torch.no_grad():
        for batch in loaders["test"]:
            signals = batch["signal"].to(device)
            targets = batch["target"]
            outputs = model(signals)
            preds = torch.argmax(outputs, dim=1)

            all_targets.append(targets.cpu().numpy())
            all_predictions.append(preds.cpu().numpy())
            all_logits.append(outputs.cpu().numpy())
            all_paths.extend(batch["path"])

    targets = np.concatenate(all_targets, axis=0)
    predictions = np.concatenate(all_predictions, axis=0)
    logits = np.concatenate(all_logits, axis=0)

    if args.segment:
        cm = confusion_matrix(targets, predictions, labels=list(range(num_classes)))
        title_suffix = " (Segment Level)"
    else:
        file_targets, file_preds = _aggregate_stage2_by_file(all_paths, targets, logits)
        cm = confusion_matrix(file_targets, file_preds, labels=list(range(num_classes)))
        title_suffix = " (File Level)"

    plot_confusion_matrix(
        cm=cm,
        class_names=class_names,
        output_path=output_path,
        title=f"Confusion Matrix{title_suffix}",
        normalize=not args.no_normalize,
    )


if __name__ == "__main__":
    main()
