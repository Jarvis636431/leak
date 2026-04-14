"""Unified trainer for stage1 regression and stage2 classification."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm

from leak_detection.data import build_dataloaders
from leak_detection.models import build_model
from leak_detection.utils import count_parameters, resolve_device, set_seed


class Trainer:
    """Train task-specific models directly on segmented CSV manifests."""

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
        return f"{base_dir}/{task}_{timestamp}"

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

    def _step(self, batch: dict[str, torch.Tensor], training: bool) -> dict[str, float]:
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

        metrics = {"loss": float(loss.item())}
        if self.task == "stage2":
            predictions = torch.argmax(outputs, dim=1)
            metrics["correct"] = float((predictions == targets).sum().item())
            metrics["count"] = float(targets.size(0))
        else:
            errors = torch.abs(outputs - targets)
            squared_errors = torch.square(outputs - targets)
            metrics["mae_sum"] = float(errors.sum().item())
            metrics["mse_sum"] = float(squared_errors.sum().item())
            metrics["count"] = float(targets.size(0))
        return metrics

    def _run_epoch(self, split: str, training: bool) -> dict[str, float]:
        loader = self.loaders[split]
        self.model.train(mode=training)

        summary: dict[str, float] = {"loss": 0.0, "count": 0.0}
        if self.task == "stage2":
            summary["correct"] = 0.0
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
                else:
                    summary["mae_sum"] += metrics["mae_sum"]
                    summary["mse_sum"] += metrics["mse_sum"]

        summary["loss"] /= max(len(loader), 1)
        if self.task == "stage2":
            summary["accuracy"] = summary["correct"] / max(summary["count"], 1.0)
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
                    f"val_acc={val_metrics['accuracy']:.4f}"
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
                f"Test metrics: loss={test_metrics['loss']:.4f} "
                f"accuracy={test_metrics['accuracy']:.4f}"
            )
        else:
            print(f"Best validation MAE: {self.best_val_score:.4f}")
            print(
                f"Test metrics: loss={test_metrics['loss']:.4f} "
                f"mae={test_metrics['mae']:.4f} "
                f"rmse={test_metrics['rmse']:.4f}"
            )
