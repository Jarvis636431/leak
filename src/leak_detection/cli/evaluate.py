"""Evaluation CLI for trained Conformer checkpoints."""

import argparse
from pathlib import Path

import torch
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
    classification_report,
)
from tqdm import tqdm
import matplotlib.pyplot as plt
import seaborn as sns

from leak_detection.data import create_dataloader
from leak_detection.models import ConformerLeakDetector
from leak_detection.utils import load_config, resolve_device


class Evaluator:
    def __init__(self, config, checkpoint_path, output_dir):
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Setup device
        self.device = resolve_device()
        print(f"Using device: {self.device}")

        # Load model
        print("Loading model...")
        self.model = ConformerLeakDetector(config["model"]).to(self.device)
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.eval()

        # Load test data
        print("Loading test data...")
        self.test_loader = create_dataloader(config, "test")

        # Results storage
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

    def evaluate(self):
        """Run evaluation on test set"""
        print("\nRunning evaluation...")

        with torch.no_grad():
            for batch in tqdm(self.test_loader, desc="Evaluating"):
                audio = batch["audio"].to(self.device)

                # Get predictions
                predictions = self.model.predict(audio)

                # Store results
                self.results["filenames"].extend(batch["filename"])
                self.results["true_has_leak"].extend(batch["has_leak"].numpy())
                self.results["pred_has_leak"].extend(predictions["leak_detected"])
                self.results["leak_prob"].extend(predictions["leak_probability"])
                self.results["true_distance"].extend(batch["distance"].numpy())
                self.results["pred_distance"].extend(predictions["distance"])
                self.results["true_shape"].extend(batch["shape"].numpy())
                self.results["pred_shape"].extend(predictions["shape_class"])
                self.results["shape_probs"].extend(predictions["shape_probability"])

        # Convert to arrays
        for key in [
            "true_has_leak",
            "pred_has_leak",
            "leak_prob",
            "true_distance",
            "pred_distance",
            "true_shape",
            "pred_shape",
        ]:
            self.results[key] = np.array(self.results[key])

        return self.compute_metrics()

    def compute_metrics(self):
        """Compute and save metrics"""
        metrics = {}

        # 1. Leak Detection Metrics
        print("\n" + "=" * 50)
        print("LEAK DETECTION METRICS")
        print("=" * 50)

        y_true = self.results["true_has_leak"]
        y_pred = self.results["pred_has_leak"]
        y_prob = self.results["leak_prob"]

        metrics["detection"] = {
            "accuracy": accuracy_score(y_true, y_pred),
            "precision": precision_recall_fscore_support(
                y_true, y_pred, average="binary"
            )[0],
            "recall": precision_recall_fscore_support(y_true, y_pred, average="binary")[
                1
            ],
            "f1": precision_recall_fscore_support(y_true, y_pred, average="binary")[2],
        }

        print(f"Accuracy:  {metrics['detection']['accuracy']:.4f}")
        print(f"Precision: {metrics['detection']['precision']:.4f}")
        print(f"Recall:    {metrics['detection']['recall']:.4f}")
        print(f"F1-Score:  {metrics['detection']['f1']:.4f}")
        print("\nClassification Report:")
        print(classification_report(y_true, y_pred, target_names=["No Leak", "Leak"]))

        # 2. Distance Estimation Metrics
        print("\n" + "=" * 50)
        print("DISTANCE ESTIMATION METRICS")
        print("=" * 50)

        y_true_dist = self.results["true_distance"]
        y_pred_dist = self.results["pred_distance"]

        metrics["distance"] = {
            "mae": np.mean(np.abs(y_true_dist - y_pred_dist)),
            "rmse": np.sqrt(np.mean((y_true_dist - y_pred_dist) ** 2)),
            "mape": np.mean(np.abs((y_true_dist - y_pred_dist) / (y_true_dist + 1e-8)))
            * 100,
        }

        print(f"MAE:  {metrics['distance']['mae']:.4f} m")
        print(f"RMSE: {metrics['distance']['rmse']:.4f} m")
        print(f"MAPE: {metrics['distance']['mape']:.2f}%")

        # 3. Shape Classification Metrics
        print("\n" + "=" * 50)
        print("SHAPE CLASSIFICATION METRICS")
        print("=" * 50)

        y_true_shape = self.results["true_shape"]
        y_pred_shape = self.results["pred_shape"]

        metrics["shape"] = {
            "accuracy": accuracy_score(y_true_shape, y_pred_shape),
            "precision": precision_recall_fscore_support(
                y_true_shape, y_pred_shape, average="weighted"
            )[0],
            "recall": precision_recall_fscore_support(
                y_true_shape, y_pred_shape, average="weighted"
            )[1],
            "f1": precision_recall_fscore_support(
                y_true_shape, y_pred_shape, average="weighted"
            )[2],
        }

        print(f"Accuracy:  {metrics['shape']['accuracy']:.4f}")
        print(f"Precision: {metrics['shape']['precision']:.4f}")
        print(f"Recall:    {metrics['shape']['recall']:.4f}")
        print(f"F1-Score:  {metrics['shape']['f1']:.4f}")
        print("\nClassification Report:")
        print(classification_report(y_true_shape, y_pred_shape))

        return metrics

    def plot_confusion_matrices(self):
        """Plot confusion matrices"""
        fig, axes = plt.subplots(1, 2, figsize=(15, 6))

        # Leak detection confusion matrix
        cm_detection = confusion_matrix(
            self.results["true_has_leak"], self.results["pred_has_leak"]
        )
        sns.heatmap(cm_detection, annot=True, fmt="d", cmap="Blues", ax=axes[0])
        axes[0].set_title("Leak Detection Confusion Matrix")
        axes[0].set_xlabel("Predicted")
        axes[0].set_ylabel("True")
        axes[0].set_xticklabels(["No Leak", "Leak"])
        axes[0].set_yticklabels(["No Leak", "Leak"])

        # Shape classification confusion matrix
        cm_shape = confusion_matrix(
            self.results["true_shape"], self.results["pred_shape"]
        )
        sns.heatmap(cm_shape, annot=True, fmt="d", cmap="Blues", ax=axes[1])
        axes[1].set_title("Shape Classification Confusion Matrix")
        axes[1].set_xlabel("Predicted")
        axes[1].set_ylabel("True")

        plt.tight_layout()
        plt.savefig(
            self.output_dir / "confusion_matrices.png", dpi=300, bbox_inches="tight"
        )
        print(
            f"\nSaved confusion matrices to {self.output_dir / 'confusion_matrices.png'}"
        )
        plt.close()

    def plot_distance_scatter(self):
        """Plot predicted vs true distance"""
        plt.figure(figsize=(10, 8))
        plt.scatter(
            self.results["true_distance"],
            self.results["pred_distance"],
            alpha=0.5,
            s=20,
        )

        # Plot diagonal line
        min_val = min(
            self.results["true_distance"].min(), self.results["pred_distance"].min()
        )
        max_val = max(
            self.results["true_distance"].max(), self.results["pred_distance"].max()
        )
        plt.plot(
            [min_val, max_val],
            [min_val, max_val],
            "r--",
            lw=2,
            label="Perfect Prediction",
        )

        plt.xlabel("True Distance (m)")
        plt.ylabel("Predicted Distance (m)")
        plt.title("Distance Estimation: Predicted vs True")
        plt.legend()
        plt.grid(True, alpha=0.3)

        # Add correlation coefficient
        corr = np.corrcoef(
            self.results["true_distance"], self.results["pred_distance"]
        )[0, 1]
        plt.text(
            0.05,
            0.95,
            f"Correlation: {corr:.4f}",
            transform=plt.gca().transAxes,
            fontsize=12,
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
        )

        plt.savefig(
            self.output_dir / "distance_scatter.png", dpi=300, bbox_inches="tight"
        )
        print(
            f"Saved distance scatter plot to {self.output_dir / 'distance_scatter.png'}"
        )
        plt.close()

    def save_results(self):
        """Save detailed results to CSV"""
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

        # Save error analysis
        error_df = results_df.copy()
        error_df["detection_error"] = (
            error_df["true_has_leak"] != error_df["pred_has_leak"]
        ).astype(int)
        error_df["distance_error"] = np.abs(
            error_df["true_distance"] - error_df["pred_distance"]
        )
        error_df["shape_error"] = (
            error_df["true_shape"] != error_df["pred_shape"]
        ).astype(int)

        # Sort by total errors
        error_df["total_errors"] = error_df["detection_error"] + error_df["shape_error"]
        error_df = error_df.sort_values("total_errors", ascending=False)

        error_df.to_csv(self.output_dir / "error_analysis.csv", index=False)
        print(f"Saved error analysis to {self.output_dir / 'error_analysis.csv'}")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate Conformer Leak Detection Model"
    )
    parser.add_argument(
        "--config", type=str, default="configs/config.yaml", help="Path to config file"
    )
    parser.add_argument(
        "--checkpoint", type=str, required=True, help="Path to model checkpoint"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="outputs/evaluation",
        help="Output directory for results",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    # Create evaluator
    evaluator = Evaluator(config, args.checkpoint, args.output_dir)

    # Run evaluation
    metrics = evaluator.evaluate()

    # Generate plots
    evaluator.plot_confusion_matrices()
    evaluator.plot_distance_scatter()
    evaluator.save_results()

    print("\n" + "=" * 50)
    print("EVALUATION COMPLETE")
    print("=" * 50)
    print(f"Results saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
