"""Unified trainer for stage1 regression and stage2 classification."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.metrics import confusion_matrix, f1_score
from torch.utils.tensorboard.writer import SummaryWriter
from tqdm import tqdm

from leak_detection.data import build_dataloaders
from leak_detection.models import build_model
from leak_detection.utils import count_parameters, resolve_device, set_seed


class Trainer:
    """Train task-specific models directly on segmented CSV manifests."""

    RAW_ID_PATTERN = re.compile(r"(ABC\d+)_seg\d+")

    def __init__(self, config: dict, output_dir: str | Path):
        self.config = config
        self.task = config["task"]
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        set_seed(config["training"].get("seed", 42))
        self.device = resolve_device()
        print(f"Using device: {self.device}")
        print(f"Task: {self.task}")

        print("Loading segmented datasets...")
        self.loaders = build_dataloaders(config)

        print("Building model...")
        self.model = build_model(config).to(self.device)
        total_params, trainable_params = count_parameters(self.model)
        print(f"Total parameters: {total_params:,}")
        print(f"Trainable parameters: {trainable_params:,}")

        self.optimizer = optim.AdamW(
            self.model.parameters(),
            lr=config["training"]["learning_rate"],
            weight_decay=config["training"]["weight_decay"],
        )
        self.scheduler = self._build_scheduler()
        self.criterion = self._build_criterion()
        self.writer = SummaryWriter(self.output_dir / "logs")

        self.current_epoch = 0
        self.best_val_score = float("-inf") if self.task == "stage2" else float("inf")
        self.patience_counter = 0

    @staticmethod
    def default_output_dir(base_dir: str, task: str) -> str:
        """Generate the default timestamped output directory."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{base_dir}/{timestamp}"

    def _build_scheduler(self):
        scheduler_name = self.config["training"].get("scheduler")
        if scheduler_name == "cosine":
            return optim.lr_scheduler.CosineAnnealingLR(
                self.optimizer,
                T_max=self.config["training"]["epochs"],
                eta_min=1e-6,
            )
        if scheduler_name == "step":
            return optim.lr_scheduler.StepLR(
                self.optimizer,
                step_size=self.config["training"].get("scheduler_step", 10),
                gamma=self.config["training"].get("scheduler_gamma", 0.1),
            )
        return None

    def _build_criterion(self):
        if self.task == "stage2":
            return nn.CrossEntropyLoss()
        loss_name = self.config["training"].get("regression_loss", "smooth_l1")
        if loss_name == "mse":
            return nn.MSELoss()
        return nn.SmoothL1Loss()

    def resume(self, checkpoint_path: str | Path) -> None:
        """Resume training state from a checkpoint."""
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.current_epoch = checkpoint["epoch"] + 1
        self.best_val_score = checkpoint["best_val_score"]
        print(f"Resumed from {checkpoint_path}")

    @classmethod
    def _extract_raw_id(cls, path: str) -> str:
        match = cls.RAW_ID_PATTERN.search(Path(path).stem)
        if match is None:
            raise ValueError(f"Unable to extract raw file id from path: {path}")
        return match.group(1)

    @staticmethod
    def _compute_stage2_metrics(
        targets: np.ndarray,
        predictions: np.ndarray,
        num_classes: int,
    ) -> dict[str, Any]:
        labels = list(range(num_classes))
        metrics: dict[str, Any] = {
            "accuracy": float(np.mean(predictions == targets)),
            "macro_f1": float(f1_score(targets, predictions, labels=labels, average="macro")),
            "confusion_matrix": confusion_matrix(targets, predictions, labels=labels),
        }
        return metrics

    def _aggregate_stage2_by_file(
        self,
        paths: list[str],
        targets: np.ndarray,
        logits: np.ndarray,
    ) -> dict[str, Any]:
        grouped: dict[str, dict[str, Any]] = {}
        for path, target, logit in zip(paths, targets, logits):
            raw_id = self._extract_raw_id(path)
            entry = grouped.setdefault(raw_id, {"target": int(target), "logits": []})
            if entry["target"] != int(target):
                raise ValueError(f"Inconsistent targets found for raw file id {raw_id}")
            entry["logits"].append(logit)

        file_targets = []
        file_predictions = []
        for raw_id in sorted(grouped):
            entry = grouped[raw_id]
            mean_logits = np.mean(np.stack(entry["logits"], axis=0), axis=0)
            file_targets.append(entry["target"])
            file_predictions.append(int(np.argmax(mean_logits)))

        file_targets_array = np.asarray(file_targets, dtype=np.int64)
        file_predictions_array = np.asarray(file_predictions, dtype=np.int64)
        metrics = self._compute_stage2_metrics(
            targets=file_targets_array,
            predictions=file_predictions_array,
            num_classes=self.config["model"]["num_classes"],
        )
        metrics["file_count"] = int(file_targets_array.size)
        return metrics

    def _step(self, batch: dict[str, Any], training: bool) -> dict[str, Any]:
        signals = batch["signal"].to(self.device)
        targets = batch["target"].to(self.device)

        if training:
            self.optimizer.zero_grad()

        outputs = self.model(signals)
        loss = self.criterion(outputs, targets)

        if training:
            loss.backward()
            clip_norm = self.config["training"].get("gradient_clip_norm")
            if clip_norm:
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=clip_norm)
            self.optimizer.step()

        metrics: dict[str, Any] = {"loss": float(loss.item())}
        if self.task == "stage2":
            predictions = torch.argmax(outputs, dim=1)
            metrics["correct"] = float((predictions == targets).sum().item())
            metrics["count"] = float(targets.size(0))
            metrics["targets"] = targets.detach().cpu().numpy()
            metrics["predictions"] = predictions.detach().cpu().numpy()
            metrics["logits"] = outputs.detach().cpu().numpy()
            metrics["paths"] = list(batch["path"])
        else:
            errors = torch.abs(outputs - targets)
            squared_errors = torch.square(outputs - targets)
            metrics["mae_sum"] = float(errors.sum().item())
            metrics["mse_sum"] = float(squared_errors.sum().item())
            metrics["count"] = float(targets.size(0))
        return metrics

    def _run_epoch(self, split: str, training: bool) -> dict[str, Any]:
        loader = self.loaders[split]
        self.model.train(mode=training)

        summary: dict[str, Any] = {"loss": 0.0, "count": 0.0}
        if self.task == "stage2":
            summary["correct"] = 0.0
            all_targets: list[np.ndarray] = []
            all_predictions: list[np.ndarray] = []
            all_logits: list[np.ndarray] = []
            all_paths: list[str] = []
        else:
            summary["mae_sum"] = 0.0
            summary["mse_sum"] = 0.0

        context = torch.enable_grad() if training else torch.no_grad()
        with context:
            for batch in tqdm(loader, desc=f"{split}:{'train' if training else 'eval'}"):
                metrics = self._step(batch, training=training)
                summary["loss"] += metrics["loss"]
                summary["count"] += metrics["count"]
                if self.task == "stage2":
                    summary["correct"] += metrics["correct"]
                    all_targets.append(metrics["targets"])
                    all_predictions.append(metrics["predictions"])
                    all_logits.append(metrics["logits"])
                    all_paths.extend(metrics["paths"])
                else:
                    summary["mae_sum"] += metrics["mae_sum"]
                    summary["mse_sum"] += metrics["mse_sum"]

        summary["loss"] /= max(len(loader), 1)
        if self.task == "stage2":
            targets = np.concatenate(all_targets, axis=0)
            predictions = np.concatenate(all_predictions, axis=0)
            logits = np.concatenate(all_logits, axis=0)

            segment_metrics = self._compute_stage2_metrics(
                targets=targets,
                predictions=predictions,
                num_classes=self.config["model"]["num_classes"],
            )
            file_metrics = self._aggregate_stage2_by_file(
                paths=all_paths,
                targets=targets,
                logits=logits,
            )

            summary["accuracy"] = segment_metrics["accuracy"]
            summary["macro_f1"] = segment_metrics["macro_f1"]
            summary["confusion_matrix"] = segment_metrics["confusion_matrix"]
            summary["file_accuracy"] = file_metrics["accuracy"]
            summary["file_macro_f1"] = file_metrics["macro_f1"]
            summary["file_confusion_matrix"] = file_metrics["confusion_matrix"]
            summary["score"] = summary["accuracy"]
        else:
            summary["mae"] = summary["mae_sum"] / max(summary["count"], 1.0)
            summary["rmse"] = float(np.sqrt(summary["mse_sum"] / max(summary["count"], 1.0)))
            summary["score"] = -summary["mae"]
        return summary

    def _log_epoch(self, train_metrics: dict[str, float], val_metrics: dict[str, float], epoch: int) -> None:
        self.writer.add_scalar("Loss/train", train_metrics["loss"], epoch)
        self.writer.add_scalar("Loss/val", val_metrics["loss"], epoch)
        self.writer.add_scalar("LR", self.optimizer.param_groups[0]["lr"], epoch)

        if self.task == "stage2":
            self.writer.add_scalar("Metrics/train_accuracy", train_metrics["accuracy"], epoch)
            self.writer.add_scalar("Metrics/val_accuracy", val_metrics["accuracy"], epoch)
            self.writer.add_scalar("Metrics/train_macro_f1", train_metrics["macro_f1"], epoch)
            self.writer.add_scalar("Metrics/val_macro_f1", val_metrics["macro_f1"], epoch)
            self.writer.add_scalar("Metrics/train_file_accuracy", train_metrics["file_accuracy"], epoch)
            self.writer.add_scalar("Metrics/val_file_accuracy", val_metrics["file_accuracy"], epoch)
            self.writer.add_scalar("Metrics/train_file_macro_f1", train_metrics["file_macro_f1"], epoch)
            self.writer.add_scalar("Metrics/val_file_macro_f1", val_metrics["file_macro_f1"], epoch)
        else:
            self.writer.add_scalar("Metrics/train_mae", train_metrics["mae"], epoch)
            self.writer.add_scalar("Metrics/val_mae", val_metrics["mae"], epoch)
            self.writer.add_scalar("Metrics/train_rmse", train_metrics["rmse"], epoch)
            self.writer.add_scalar("Metrics/val_rmse", val_metrics["rmse"], epoch)

    def _save_checkpoint(self, is_best: bool) -> None:
        checkpoint = {
            "epoch": self.current_epoch,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "best_val_score": self.best_val_score,
            "config": self.config,
        }
        torch.save(checkpoint, self.output_dir / "checkpoint_last.pth")
        if is_best:
            torch.save(checkpoint, self.output_dir / "checkpoint_best.pth")

    def _is_improved(self, val_metrics: dict[str, float]) -> bool:
        if self.task == "stage2":
            return val_metrics["score"] > self.best_val_score
        return val_metrics["score"] > -self.best_val_score

    def train(self) -> None:
        """Execute the full training loop and report test metrics for the best run."""
        print(f"Output directory: {self.output_dir}")

        for epoch in range(self.current_epoch, self.config["training"]["epochs"]):
            self.current_epoch = epoch
            train_metrics = self._run_epoch(split="train", training=True)
            val_metrics = self._run_epoch(split="val", training=False)

            if self.scheduler is not None:
                self.scheduler.step()

            if self.task == "stage2":
                improved = val_metrics["accuracy"] > self.best_val_score
                if improved:
                    self.best_val_score = val_metrics["accuracy"]
            else:
                improved = val_metrics["mae"] < self.best_val_score
                if improved:
                    self.best_val_score = val_metrics["mae"]

            self.patience_counter = 0 if improved else self.patience_counter + 1
            self._log_epoch(train_metrics, val_metrics, epoch)
            self._save_checkpoint(is_best=improved)

            if self.task == "stage2":
                print(
                    f"Epoch {epoch}: "
                    f"train_loss={train_metrics['loss']:.4f} "
                    f"val_loss={val_metrics['loss']:.4f} "
                    f"val_acc={val_metrics['accuracy']:.4f} "
                    f"val_macro_f1={val_metrics['macro_f1']:.4f} "
                    f"val_file_acc={val_metrics['file_accuracy']:.4f} "
                    f"val_file_macro_f1={val_metrics['file_macro_f1']:.4f}"
                )
            else:
                print(
                    f"Epoch {epoch}: "
                    f"train_loss={train_metrics['loss']:.4f} "
                    f"val_loss={val_metrics['loss']:.4f} "
                    f"val_mae={val_metrics['mae']:.4f} "
                    f"val_rmse={val_metrics['rmse']:.4f}"
                )

            if self.patience_counter >= self.config["training"]["early_stopping_patience"]:
                print(f"Early stopping at epoch {epoch}")
                break

        self.writer.close()
        self._evaluate_best_checkpoint()

    def _evaluate_best_checkpoint(self) -> None:
        checkpoint_path = self.output_dir / "checkpoint_best.pth"
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        test_metrics = self._run_epoch(split="test", training=False)

        if self.task == "stage2":
            print(f"Best validation accuracy: {self.best_val_score:.4f}")
            print(
                f"Test segment metrics: loss={test_metrics['loss']:.4f} "
                f"accuracy={test_metrics['accuracy']:.4f} "
                f"macro_f1={test_metrics['macro_f1']:.4f}"
            )
            print(
                f"Test file metrics: accuracy={test_metrics['file_accuracy']:.4f} "
                f"macro_f1={test_metrics['file_macro_f1']:.4f}"
            )
            print("Test segment confusion matrix:")
            print(test_metrics["confusion_matrix"])
            print("Test file confusion matrix:")
            print(test_metrics["file_confusion_matrix"])
        else:
            print(f"Best validation MAE: {self.best_val_score:.4f}")
            print(
                f"Test metrics: loss={test_metrics['loss']:.4f} "
                f"mae={test_metrics['mae']:.4f} "
                f"rmse={test_metrics['rmse']:.4f}"
            )
