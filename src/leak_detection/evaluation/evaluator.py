"""Model evaluation and artifact generation."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import torch
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)
from tqdm import tqdm

from leak_detection.data import create_dataloader
from leak_detection.models import ConformerLeakDetector
from leak_detection.utils import resolve_device


class Evaluator:
    """Run model evaluation and persist human-readable artifacts."""

    def __init__(self, config: dict, checkpoint_path: str | Path, output_dir: str | Path):
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.device = resolve_device()
        print(f"Using device: {self.device}")

        print("Loading model...")
        self.model = ConformerLeakDetector(config["model"]).to(self.device)
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.eval()

        print("Loading test data...")
        self.test_loader = create_dataloader(config, "test")
        self.results = {
            "filenames": [],
            "true_has_leak": [],
            "pred_has_leak": [],
            "leak_prob": [],
            "true_distance": [],
            "pred_distance": [],
            "true_shape": [],
            "pred_shape": [],
            "shape_probs": [],
        }

    def evaluate(self) -> dict:
        """Run inference across the test set and compute aggregate metrics."""
        print("\nRunning evaluation...")

        with torch.no_grad():
            for batch in tqdm(self.test_loader, desc="Evaluating"):
                predictions = self.model.predict(batch["audio"].to(self.device))
                self.results["filenames"].extend(batch["filename"])
                self.results["true_has_leak"].extend(batch["has_leak"].numpy())
                self.results["pred_has_leak"].extend(predictions["leak_detected"])
                self.results["leak_prob"].extend(predictions["leak_probability"])
                self.results["true_distance"].extend(batch["distance"].numpy())
                self.results["pred_distance"].extend(predictions["distance"])
                self.results["true_shape"].extend(batch["shape"].numpy())
                self.results["pred_shape"].extend(predictions["shape_class"])
                self.results["shape_probs"].extend(predictions["shape_probability"])

        for key in (
            "true_has_leak",
            "pred_has_leak",
            "leak_prob",
            "true_distance",
            "pred_distance",
            "true_shape",
            "pred_shape",
        ):
            self.results[key] = np.array(self.results[key])

        metrics = self.compute_metrics()
        self.plot_confusion_matrices()
        self.plot_distance_scatter()
        self.save_results()
        return metrics

    def compute_metrics(self) -> dict:
        """Compute evaluation metrics and print them to stdout."""
        metrics = {}

        print("\n" + "=" * 50)
        print("LEAK DETECTION METRICS")
        print("=" * 50)
        y_true = self.results["true_has_leak"]
        y_pred = self.results["pred_has_leak"]
        metrics["detection"] = {
            "accuracy": accuracy_score(y_true, y_pred),
            "precision": precision_recall_fscore_support(y_true, y_pred, average="binary")[0],
            "recall": precision_recall_fscore_support(y_true, y_pred, average="binary")[1],
            "f1": precision_recall_fscore_support(y_true, y_pred, average="binary")[2],
        }
        print(f"Accuracy:  {metrics['detection']['accuracy']:.4f}")
        print(f"Precision: {metrics['detection']['precision']:.4f}")
        print(f"Recall:    {metrics['detection']['recall']:.4f}")
        print(f"F1-Score:  {metrics['detection']['f1']:.4f}")
        print("\nClassification Report:")
        print(classification_report(y_true, y_pred, target_names=["No Leak", "Leak"]))

        print("\n" + "=" * 50)
        print("DISTANCE ESTIMATION METRICS")
        print("=" * 50)
        y_true_dist = self.results["true_distance"]
        y_pred_dist = self.results["pred_distance"]
        metrics["distance"] = {
            "mae": np.mean(np.abs(y_true_dist - y_pred_dist)),
            "rmse": np.sqrt(np.mean((y_true_dist - y_pred_dist) ** 2)),
            "mape": np.mean(np.abs((y_true_dist - y_pred_dist) / (y_true_dist + 1e-8))) * 100,
        }
        print(f"MAE:  {metrics['distance']['mae']:.4f} m")
        print(f"RMSE: {metrics['distance']['rmse']:.4f} m")
        print(f"MAPE: {metrics['distance']['mape']:.2f}%")

        print("\n" + "=" * 50)
        print("SHAPE CLASSIFICATION METRICS")
        print("=" * 50)
        y_true_shape = self.results["true_shape"]
        y_pred_shape = self.results["pred_shape"]
        metrics["shape"] = {
            "accuracy": accuracy_score(y_true_shape, y_pred_shape),
            "precision": precision_recall_fscore_support(y_true_shape, y_pred_shape, average="weighted")[0],
            "recall": precision_recall_fscore_support(y_true_shape, y_pred_shape, average="weighted")[1],
            "f1": precision_recall_fscore_support(y_true_shape, y_pred_shape, average="weighted")[2],
        }
        print(f"Accuracy:  {metrics['shape']['accuracy']:.4f}")
        print(f"Precision: {metrics['shape']['precision']:.4f}")
        print(f"Recall:    {metrics['shape']['recall']:.4f}")
        print(f"F1-Score:  {metrics['shape']['f1']:.4f}")
        print("\nClassification Report:")
        print(classification_report(y_true_shape, y_pred_shape))
        return metrics

    def plot_confusion_matrices(self) -> None:
        """Write confusion matrix visualizations."""
        fig, axes = plt.subplots(1, 2, figsize=(15, 6))

        cm_detection = confusion_matrix(self.results["true_has_leak"], self.results["pred_has_leak"])
        sns.heatmap(cm_detection, annot=True, fmt="d", cmap="Blues", ax=axes[0])
        axes[0].set_title("Leak Detection Confusion Matrix")
        axes[0].set_xlabel("Predicted")
        axes[0].set_ylabel("True")
        axes[0].set_xticklabels(["No Leak", "Leak"])
        axes[0].set_yticklabels(["No Leak", "Leak"])

        cm_shape = confusion_matrix(self.results["true_shape"], self.results["pred_shape"])
        sns.heatmap(cm_shape, annot=True, fmt="d", cmap="Blues", ax=axes[1])
        axes[1].set_title("Shape Classification Confusion Matrix")
        axes[1].set_xlabel("Predicted")
        axes[1].set_ylabel("True")

        plt.tight_layout()
        plt.savefig(self.output_dir / "confusion_matrices.png", dpi=300, bbox_inches="tight")
        print(f"\nSaved confusion matrices to {self.output_dir / 'confusion_matrices.png'}")
        plt.close()

    def plot_distance_scatter(self) -> None:
        """Write a scatter plot for distance regression quality."""
        plt.figure(figsize=(10, 8))
        plt.scatter(self.results["true_distance"], self.results["pred_distance"], alpha=0.5, s=20)

        min_val = min(self.results["true_distance"].min(), self.results["pred_distance"].min())
        max_val = max(self.results["true_distance"].max(), self.results["pred_distance"].max())
        plt.plot([min_val, max_val], [min_val, max_val], "r--", lw=2, label="Perfect Prediction")
        plt.xlabel("True Distance (m)")
        plt.ylabel("Predicted Distance (m)")
        plt.title("Distance Estimation: Predicted vs True")
        plt.legend()
        plt.grid(True, alpha=0.3)

        corr = np.corrcoef(self.results["true_distance"], self.results["pred_distance"])[0, 1]
        plt.text(
            0.05,
            0.95,
            f"Correlation: {corr:.4f}",
            transform=plt.gca().transAxes,
            fontsize=12,
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
        )
        plt.savefig(self.output_dir / "distance_scatter.png", dpi=300, bbox_inches="tight")
        print(f"Saved distance scatter plot to {self.output_dir / 'distance_scatter.png'}")
        plt.close()

    def save_results(self) -> None:
        """Persist row-level predictions and simple error analysis."""
        results_df = pd.DataFrame(
            {
                "filename": self.results["filenames"],
                "true_has_leak": self.results["true_has_leak"],
                "pred_has_leak": self.results["pred_has_leak"],
                "leak_probability": self.results["leak_prob"],
                "true_distance": self.results["true_distance"],
                "pred_distance": self.results["pred_distance"],
                "true_shape": self.results["true_shape"],
                "pred_shape": self.results["pred_shape"],
            }
        )
        results_df.to_csv(self.output_dir / "predictions.csv", index=False)
        print(f"\nSaved predictions to {self.output_dir / 'predictions.csv'}")

        error_df = results_df.copy()
        error_df["detection_error"] = (error_df["true_has_leak"] != error_df["pred_has_leak"]).astype(int)
        error_df["distance_error"] = np.abs(error_df["true_distance"] - error_df["pred_distance"])
        error_df["shape_error"] = (error_df["true_shape"] != error_df["pred_shape"]).astype(int)
        error_df["total_errors"] = error_df["detection_error"] + error_df["shape_error"]
        error_df.sort_values("total_errors", ascending=False).to_csv(
            self.output_dir / "error_analysis.csv",
            index=False,
        )
        print(f"Saved error analysis to {self.output_dir / 'error_analysis.csv'}")
