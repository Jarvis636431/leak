"""Baseline comparison: SVM, KNN, Decision Tree with handcrafted features."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn import metrics as skmetrics
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.svm import SVC, SVR
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

from leak_detection.data.segmented import _load_signal, _filter_split
from leak_detection.utils import set_seed

# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------


def _extract_time_features(signal: np.ndarray) -> dict[str, float]:
    """Extract time-domain features from a 1-D signal array."""
    x = signal.astype(np.float64)
    n = len(x)
    mean = float(np.mean(x))
    std = float(np.std(x, ddof=0))
    rms = float(np.sqrt(np.mean(x**2)))
    peak = float(np.max(np.abs(x)))
    ptp = float(np.ptp(x))

    # Skewness
    if std > 0:
        skew = float(np.mean((x - mean) ** 3) / (std**3))
    else:
        skew = 0.0

    # Kurtosis (excess)
    if std > 0:
        kurt = float(np.mean((x - mean) ** 4) / (std**4))
    else:
        kurt = 0.0

    # Crest factor
    crest = peak / rms if rms > 0 else 0.0

    # Shape factor
    mean_abs = float(np.mean(np.abs(x)))
    shape = rms / mean_abs if mean_abs > 0 else 0.0

    # Impulse factor
    impulse = peak / mean_abs if mean_abs > 0 else 0.0

    # Energy
    energy = float(np.sum(x**2))

    # Zero-crossing rate
    zc = float(np.sum(np.diff(np.signbit(x)) > 0)) / max(n - 1, 1)

    return {
        "mean": mean,
        "std": std,
        "rms": rms,
        "peak": peak,
        "peak_to_peak": ptp,
        "skewness": skew,
        "kurtosis": kurt,
        "crest_factor": crest,
        "shape_factor": shape,
        "impulse_factor": impulse,
        "energy": energy,
        "zero_crossing_rate": zc,
    }


def _extract_freq_features(signal: np.ndarray, fs: float = 25600.0) -> dict[str, float]:
    """Extract frequency-domain features via FFT."""
    x = signal.astype(np.float64)
    n = len(x)
    fft_vals = np.fft.rfft(x)
    magnitudes = np.abs(fft_vals)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)

    positive_mask = freqs > 0
    freqs = freqs[positive_mask]
    magnitudes = magnitudes[positive_mask]

    if len(magnitudes) == 0:
        return {"spectral_centroid": 0.0, "dominant_freq": 0.0, "spectral_rolloff_85": 0.0}

    total_energy = np.sum(magnitudes)
    if total_energy == 0:
        return {"spectral_centroid": 0.0, "dominant_freq": 0.0, "spectral_rolloff_85": 0.0}

    # Spectral centroid
    centroid = float(np.sum(freqs * magnitudes) / total_energy)

    # Dominant frequency
    dominant_idx = np.argmax(magnitudes)
    dominant_freq = float(freqs[dominant_idx])

    # Spectral roll-off (85th percentile)
    cumsum = np.cumsum(magnitudes)
    rolloff_idx = np.searchsorted(cumsum, 0.85 * total_energy)
    rolloff = float(freqs[min(rolloff_idx, len(freqs) - 1)])

    # Band energies: divide spectrum into 8 bands
    n_bands = 8
    band_edges = np.linspace(0, len(magnitudes), n_bands + 1, dtype=int)
    feats: dict[str, float] = {
        "spectral_centroid": centroid,
        "dominant_freq": dominant_freq,
        "spectral_rolloff_85": rolloff,
    }
    for b in range(n_bands):
        start, end = band_edges[b], band_edges[b + 1]
        if end > start:
            feats[f"band_energy_{b}"] = float(np.sum(magnitudes[start:end]) / total_energy)
        else:
            feats[f"band_energy_{b}"] = 0.0

    return feats


def extract_features(signal: np.ndarray, fs: float = 25600.0) -> np.ndarray:
    """Combine time- and frequency-domain features into a flat vector."""
    time_feats = _extract_time_features(signal)
    freq_feats = _extract_freq_features(signal, fs)
    all_feats = {**time_feats, **freq_feats}
    return np.asarray(list(all_feats.values()), dtype=np.float64)


FEATURE_NAMES = [
    "mean", "std", "rms", "peak", "peak_to_peak", "skewness", "kurtosis",
    "crest_factor", "shape_factor", "impulse_factor", "energy", "zero_crossing_rate",
    "spectral_centroid", "dominant_freq", "spectral_rolloff_85",
] + [f"band_energy_{b}" for b in range(8)]

# ---------------------------------------------------------------------------
# File-level aggregation
# ---------------------------------------------------------------------------

RAW_ID_PATTERN = re.compile(r"(ABC\d+)_seg\d+")


def _extract_raw_id(path: str) -> str:
    match = RAW_ID_PATTERN.search(Path(path).stem)
    if match is None:
        raise ValueError(f"Cannot extract raw ID from: {path}")
    return match.group(1)


def aggregate_by_file(
    paths: list[str],
    targets: np.ndarray,
    predictions: np.ndarray,
    task: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Aggregate segment predictions to file level."""
    grouped: dict[str, dict] = {}
    for path, target, pred in zip(paths, targets, predictions):
        raw_id = _extract_raw_id(path)
        entry = grouped.setdefault(raw_id, {"target": target, "predictions": []})
        entry["predictions"].append(pred)

    file_targets, file_preds = [], []
    for raw_id in sorted(grouped):
        entry = grouped[raw_id]
        file_targets.append(entry["target"])
        if task == "stage2":
            # Majority vote
            file_preds.append(int(np.argmax(np.bincount([int(p) for p in entry["predictions"]]))))
        else:
            file_preds.append(float(np.mean(entry["predictions"])))

    return np.asarray(file_targets), np.asarray(file_preds)


def aggregate_features_by_file(
    paths: list[str],
    features: np.ndarray,
) -> pd.DataFrame:
    """Aggregate segment features by file (mean, std)."""
    grouped: dict[str, list[np.ndarray]] = {}
    raw_ids = []
    for path in paths:
        raw_id = _extract_raw_id(path)
        raw_ids.append(raw_id)

    df = pd.DataFrame(features, columns=FEATURE_NAMES)
    df["raw_id"] = raw_ids
    agg_df = df.groupby("raw_id").agg(["mean", "std"])
    agg_df.columns = [f"{col[0]}_{col[1]}" for col in agg_df.columns]
    return agg_df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------


def load_segment_data(
    manifest_path: str | Path,
    task: str,
    split: str,
    normalize: bool = True,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Load all segments for a split and extract features."""
    manifest = pd.read_csv(manifest_path)

    if "split" in manifest.columns:
        samples = manifest.loc[manifest["split"] == split].reset_index(drop=True)
    else:
        pattern_str = f"/{split}/"
        path_col = "path_left" if task == "stage1" else "path"
        mask = manifest[path_col].astype(str).str.contains(pattern_str, regex=False)
        samples = manifest.loc[mask].reset_index(drop=True)

    if samples.empty:
        raise ValueError(f"No {split} samples found in {manifest_path}")

    all_features: list[np.ndarray] = []
    all_targets: list[float] = []
    all_paths: list[str] = []

    if task == "stage2":
        for _, row in samples.iterrows():
            signal = _load_signal(row["path"], normalize).numpy()
            all_features.append(extract_features(signal))
            all_targets.append(float(row["label"]))
            all_paths.append(row["path"])
    else:
        for _, row in samples.iterrows():
            left = _load_signal(row["path_left"], normalize).numpy()
            feats = extract_features(left)
            # Also extract from right channel and concatenate
            right = _load_signal(row["path_right"], normalize).numpy()
            right_feats = extract_features(right)
            combined = np.concatenate([feats, right_feats])
            all_features.append(combined)
            all_targets.append(float(row["distance"]))
            all_paths.append(row["path_left"])

    feat_array = np.stack(all_features, axis=0)
    target_array = np.asarray(all_targets)
    if task == "stage2":
        target_array = target_array.astype(np.int64)

    return feat_array, target_array, all_paths


# ---------------------------------------------------------------------------
# Model definitions
# ---------------------------------------------------------------------------

BASELINE_MODELS: dict[str, Any] = {
    "svm": {
        "stage2": lambda: SVC(kernel="rbf", C=10.0, gamma="scale", random_state=42),
        "stage1": lambda: SVR(kernel="rbf", C=10.0, gamma="scale"),
    },
    "knn": {
        "stage2": lambda: KNeighborsClassifier(n_neighbors=5, weights="distance"),
        "stage1": lambda: KNeighborsRegressor(n_neighbors=5, weights="distance"),
    },
    "decision_tree": {
        "stage2": lambda: DecisionTreeClassifier(max_depth=10, random_state=42),
        "stage1": lambda: DecisionTreeRegressor(max_depth=10, random_state=42),
    },
}

# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate_stage2(targets: np.ndarray, predictions: np.ndarray) -> dict[str, Any]:
    """Classification metrics."""
    return {
        "accuracy": float(skmetrics.accuracy_score(targets, predictions)),
        "macro_f1": float(skmetrics.f1_score(targets, predictions, average="macro")),
        "weighted_f1": float(skmetrics.f1_score(targets, predictions, average="weighted")),
        "precision": float(skmetrics.precision_score(targets, predictions, average="macro")),
        "recall": float(skmetrics.recall_score(targets, predictions, average="macro")),
    }


def evaluate_stage1(targets: np.ndarray, predictions: np.ndarray) -> dict[str, Any]:
    """Regression metrics."""
    errors = predictions - targets
    abs_errors = np.abs(errors)
    return {
        "mae": float(np.mean(abs_errors)),
        "rmse": float(np.sqrt(np.mean(errors**2))),
        "bias": float(np.mean(errors)),
        "median_ae": float(np.median(abs_errors)),
        "p95_ae": float(np.percentile(abs_errors, 95)),
        "within_0_5": float(np.mean(abs_errors <= 0.5)),
        "within_1_0": float(np.mean(abs_errors <= 1.0)),
        "r2": float(skmetrics.r2_score(targets, predictions)),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run traditional ML baselines (SVM, KNN, DT) on segmented signals"
    )
    parser.add_argument("--config", type=str, required=True, help="Path to config YAML")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory for results")
    parser.add_argument("--models", type=str, nargs="+", choices=list(BASELINE_MODELS), default=list(BASELINE_MODELS))
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    from leak_detection.utils import load_config
    config = load_config(args.config)
    task = config["task"]
    manifest_path = config["data"]["manifest"]
    output_dir = Path(args.output_dir or f"outputs/baselines/{task}_{Path(args.config).stem}")
    output_dir.mkdir(parents=True, exist_ok=True)

    set_seed(args.seed)

    print(f"Task: {task}")
    print(f"Loading data from {manifest_path}")

    # Load train and test features
    train_feats, train_targets, train_paths = load_segment_data(
        manifest_path, task, "train", normalize=True
    )
    test_feats, test_targets, test_paths = load_segment_data(
        manifest_path, task, "test", normalize=True
    )
    print(f"Train segments: {len(train_feats)}, features: {train_feats.shape[1]}")
    print(f"Test segments: {len(test_feats)}, features: {test_feats.shape[1]}")

    # Standardize features
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    train_feats_scaled = scaler.fit_transform(train_feats)
    test_feats_scaled = scaler.transform(test_feats)

    # Also prepare file-level aggregated features
    train_file_feats = aggregate_features_by_file(train_paths, train_feats_scaled)
    # File-level targets
    train_file_targets = []
    for path in sorted(set(_extract_raw_id(p) for p in train_paths)):
        train_file_targets.append(train_targets[train_paths.index(path)])

    results: list[dict[str, Any]] = []

    for model_name in args.models:
        print(f"\n{'='*50}")
        print(f"Training {model_name}...")
        model_cls = BASELINE_MODELS[model_name][task]

        # ---- Segment-level ----
        model = model_cls()
        model.fit(train_feats_scaled, train_targets)
        seg_preds = model.predict(test_feats_scaled)

        if task == "stage2":
            seg_metrics = evaluate_stage2(test_targets, seg_preds)
        else:
            seg_metrics = evaluate_stage1(test_targets, seg_preds)

        print(f"  Segment-level: ", seg_metrics)

        # ---- File-level aggregation ----
        file_targets, file_preds = aggregate_by_file(
            test_paths, test_targets, seg_preds, task
        )
        if task == "stage2":
            file_metrics = evaluate_stage2(file_targets, file_preds)
        else:
            file_metrics = evaluate_stage1(file_targets, file_preds)

        print(f"  File-level: ", file_metrics)

        row: dict[str, Any] = {"model": model_name, "level": "segment"}
        row.update(seg_metrics)
        results.append(row)

        row = {"model": model_name, "level": "file"}
        row.update(file_metrics)
        results.append(row)

        # ---- Also train on file-level features (for comparison) ----
        if len(train_file_feats) > 10 and model_name != "knn":
            file_model = model_cls()
            file_model.fit(train_file_feats, train_file_targets)
            # can't evaluate on test easily without file-level test features
            # skip this for simplicity

    # Write results
    fieldnames = ["model", "level"]
    if task == "stage2":
        fieldnames += ["accuracy", "macro_f1", "weighted_f1", "precision", "recall"]
    else:
        fieldnames += ["mae", "rmse", "bias", "median_ae", "p95_ae", "within_0_5", "within_1_0", "r2"]

    results_path = output_dir / "baseline_results.csv"
    with open(results_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(f"\nResults saved to {results_path}")

    # Print comparison table
    print(f"\n{'='*60}")
    print("Baseline Results Summary")
    print(f"{'='*60}")
    for row in results:
        line = f"  {row['model']:>15} [{row['level']:>7}] "
        if task == "stage2":
            line += f"acc={row.get('accuracy', 0):.4f}  f1={row.get('macro_f1', 0):.4f}"
        else:
            line += f"mae={row.get('mae', 0):.4f}  rmse={row.get('rmse', 0):.4f}  within1.0={row.get('within_1_0', 0):.4f}"
        print(line)


if __name__ == "__main__":
    main()
