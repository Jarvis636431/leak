"""Plot prediction error distributions for stage1 regression results."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch

from leak_detection.data import build_dataloaders
from leak_detection.models import build_model
from leak_detection.utils import load_config, resolve_device, set_seed


def _recompute_predictions(config: dict, checkpoint_path: str | Path) -> pd.DataFrame:
    """Re-run test evaluation to get prediction details."""
    device = resolve_device()
    model = build_model(config).to(device)
    checkpoint = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    loaders = build_dataloaders(config)
    rows: list[dict] = []
    with torch.no_grad():
        for batch in loaders["test"]:
            signals = batch["signal"].to(device)
            targets = batch["target"].cpu().numpy()
            outputs = model(signals).cpu().numpy()

            path_left = batch.get("path_left", [""] * len(targets))
            path_right = batch.get("path_right", [""] * len(targets))

            for i in range(len(targets)):
                rows.append(
                    {
                        "path_left": path_left[i],
                        "path_right": path_right[i],
                        "target_distance": float(targets[i]),
                        "predicted_distance": float(outputs[i]),
                        "signed_error": float(outputs[i] - targets[i]),
                        "absolute_error": float(abs(outputs[i] - targets[i])),
                    }
                )
    return pd.DataFrame(rows)


def _load_predictions_from_csv(csv_path: str | Path) -> pd.DataFrame:
    """Load prediction details from CSV saved by Trainer."""
    return pd.read_csv(csv_path)


def plot_error_distribution(
    df: pd.DataFrame,
    output_dir: str | Path,
    dpi: int = 300,
) -> None:
    """Generate three error distribution plots from prediction details."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    errors = df["signed_error"].values
    absolute_errors = df["absolute_error"].values
    targets = df["target_distance"].values
    predictions = df["predicted_distance"].values

    # --- 1. Signed error histogram ---
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(errors, bins=50, color="steelblue", edgecolor="white", alpha=0.85)
    ax.axvline(0.0, color="red", linestyle="--", linewidth=1.2, label="Zero error")
    ax.axvline(
        float(np.mean(errors)),
        color="darkgreen",
        linestyle=":",
        linewidth=1.2,
        label=f"Mean bias = {np.mean(errors):.3f}",
    )
    ax.set_xlabel("Signed Error (m)", fontsize=11)
    ax.set_ylabel("Count", fontsize=11)
    ax.set_title("Prediction Error Distribution", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.tick_params(labelsize=10)
    fig.tight_layout()
    fig.savefig(output_dir / "error_histogram.png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print("error_histogram.png saved")

    # --- 2. Predictions vs Targets scatter ---
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(targets, predictions, alpha=0.4, s=15, c="steelblue", edgecolors="none")
    min_val = min(targets.min(), predictions.min()) - 0.5
    max_val = max(targets.max(), predictions.max()) + 0.5
    ax.plot([min_val, max_val], [min_val, max_val], "r--", linewidth=1.2, label="Ideal")
    ax.set_xlabel("True Distance (m)", fontsize=11)
    ax.set_ylabel("Predicted Distance (m)", fontsize=11)
    ax.set_title("Predictions vs. Targets", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_aspect("equal")
    ax.tick_params(labelsize=10)
    fig.tight_layout()
    fig.savefig(output_dir / "pred_vs_target_scatter.png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print("pred_vs_target_scatter.png saved")

    # --- 3. Absolute error by distance boxplot ---
    distances = sorted(df["target_distance"].unique())
    grouped_data = [df.loc[df["target_distance"] == d, "absolute_error"].values for d in distances]

    # add jittered scatter overlay
    fig, ax = plt.subplots(figsize=(9, 5))
    bp = ax.boxplot(
        grouped_data,
        positions=distances,
        widths=0.6,
        patch_artist=True,
        boxprops=dict(facecolor="lightblue", alpha=0.6),
        medianprops=dict(color="red", linewidth=1.5),
        whiskerprops=dict(linewidth=1.2),
        capprops=dict(linewidth=1.2),
        flierprops=dict(marker="o", markersize=4, alpha=0.4),
    )
    # Overlay individual points with jitter
    for d, vals in zip(distances, grouped_data):
        jitter = np.random.default_rng(42).uniform(-0.15, 0.15, size=len(vals))
        ax.scatter(
            np.full_like(vals, d) + jitter,
            vals,
            alpha=0.35,
            s=10,
            color="steelblue",
            edgecolors="none",
        )
    ax.set_xlabel("True Distance (m)", fontsize=11)
    ax.set_ylabel("Absolute Error (m)", fontsize=11)
    ax.set_title("Absolute Error by Distance", fontsize=13)
    ax.grid(True, alpha=0.3, axis="y")
    ax.tick_params(labelsize=10)
    fig.tight_layout()
    fig.savefig(output_dir / "error_by_distance_boxplot.png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print("error_by_distance_boxplot.png saved")

    # --- Summary statistics ---
    summary = {
        "count": len(df),
        "mae": float(np.mean(absolute_errors)),
        "rmse": float(np.sqrt(np.mean(errors**2))),
        "bias": float(np.mean(errors)),
        "median_ae": float(np.median(absolute_errors)),
        "p95_ae": float(np.percentile(absolute_errors, 95)),
        "within_0.5": float(np.mean(absolute_errors <= 0.5)),
        "within_1.0": float(np.mean(absolute_errors <= 1.0)),
        "within_2.0": float(np.mean(absolute_errors <= 2.0)),
        "min_ae": float(np.min(absolute_errors)),
        "max_ae": float(np.max(absolute_errors)),
    }
    print("\n--- Error Summary ---")
    for k, v in summary.items():
        print(f"{k}: {v:.4f}" if isinstance(v, float) else f"{k}: {v}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot error distribution for stage1 regression results"
    )
    parser.add_argument(
        "--checkpoint", type=str, default=None, help="Path to checkpoint_best.pth (re-run evaluation)"
    )
    parser.add_argument(
        "--config", type=str, default=None, help="Path to config YAML (needed with --checkpoint)"
    )
    parser.add_argument(
        "--csv", type=str, default=None, help="Path to prediction CSV (saved by Trainer as test_stage1_predictions.csv)"
    )
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory for plots")
    parser.add_argument("--dpi", type=int, default=300, help="Output image DPI")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for jitter")
    args = parser.parse_args()

    if not args.checkpoint and not args.csv:
        raise ValueError("Either --checkpoint or --csv must be provided.")
    if args.checkpoint and not args.config:
        raise ValueError("--config is required when using --checkpoint.")

    set_seed(args.seed)

    if args.csv:
        df = _load_predictions_from_csv(args.csv)
        out_dir = args.output_dir or str(Path(args.csv).parent)
    else:
        config = load_config(args.config)
        if config["task"] != "stage1":
            raise ValueError("Error distribution plotting is only supported for stage1 (regression).")
        df = _recompute_predictions(config, args.checkpoint)
        checkpoint_dir = Path(args.checkpoint).parent
        out_dir = args.output_dir or str(checkpoint_dir)

    # Add file-level aggregation per raw_id
    import re
    pattern = re.compile(r"(ABC\d+)_seg\d+")
    df["raw_id"] = df["path_left"].apply(lambda p: pattern.search(str(p)).group(1) if pattern.search(str(p)) else p)
    file_df = df.groupby("raw_id").agg(
        target_distance=("target_distance", "first"),
        predicted_distance=("predicted_distance", "mean"),
    ).reset_index()
    file_df["signed_error"] = file_df["predicted_distance"] - file_df["target_distance"]
    file_df["absolute_error"] = file_df["signed_error"].abs()

    print(f"Plotting file-level aggregated results ({len(file_df)} files from {len(df)} segments)...")
    plot_error_distribution(file_df, out_dir, dpi=args.dpi)


if __name__ == "__main__":
    main()
