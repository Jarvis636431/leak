"""Training engine and checkpoint lifecycle."""

from datetime import datetime
from pathlib import Path

import numpy as np
import torch
import torch.optim as optim
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm

from leak_detection.data import create_dataloader
from leak_detection.models import ConformerLeakDetector
from leak_detection.training.losses import MultiTaskLoss
from leak_detection.utils import count_parameters, resolve_device


class Trainer:
    """Own the end-to-end training loop for the leak detector."""

    def __init__(self, config: dict, output_dir: str | Path):
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.device = resolve_device()
        print(f"Using device: {self.device}")

        print("Loading datasets...")
        self.train_loader = create_dataloader(config, "train")
        self.val_loader = create_dataloader(config, "val")

        print("Creating model...")
        self.model = ConformerLeakDetector(config["model"]).to(self.device)

        total_params, trainable_params = count_parameters(self.model)
        print(f"Total parameters: {total_params:,}")
        print(f"Trainable parameters: {trainable_params:,}")

        self.optimizer = optim.AdamW(
            self.model.parameters(),
            lr=config["training"]["learning_rate"],
            weight_decay=config["training"]["weight_decay"],
        )
        self.scheduler = self._build_scheduler()
        self.criterion = MultiTaskLoss(
            weights=config["training"]["loss_weights"],
            learnable=False,
        )
        self.writer = SummaryWriter(self.output_dir / "logs")
        self.current_epoch = 0
        self.best_val_loss = float("inf")
        self.patience_counter = 0

    @staticmethod
    def default_output_dir(base_dir: str = "outputs") -> str:
        """Generate the default timestamped output directory."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{base_dir}/{timestamp}"

    def resume(self, checkpoint_path: str | Path) -> None:
        """Resume training state from a checkpoint."""
        print(f"Resuming from {checkpoint_path}")
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.current_epoch = checkpoint["epoch"]
        self.best_val_loss = checkpoint["best_val_loss"]

    def _build_scheduler(self):
        scheduler_name = self.config["training"]["scheduler"]
        if scheduler_name == "cosine":
            return optim.lr_scheduler.CosineAnnealingLR(
                self.optimizer,
                T_max=self.config["training"]["epochs"],
                eta_min=1e-6,
            )
        if scheduler_name == "step":
            return optim.lr_scheduler.StepLR(
                self.optimizer,
                step_size=self.config["training"]["scheduler_step"],
                gamma=0.1,
            )
        return None

    def _move_batch_to_device(self, batch: dict) -> tuple[torch.Tensor, ...]:
        return (
            batch["audio"].to(self.device),
            batch["has_leak"].to(self.device),
            batch["distance"].to(self.device),
            batch["shape"].to(self.device),
        )

    def _run_epoch(self, loader, training: bool, description: str) -> dict:
        if training:
            self.model.train()
        else:
            self.model.eval()

        total_loss = 0.0
        detection_loss = 0.0
        distance_loss = 0.0
        shape_loss = 0.0
        detection_correct = 0
        detection_total = 0
        shape_correct = 0
        shape_total = 0
        distance_errors = []

        context = torch.enable_grad() if training else torch.no_grad()
        with context:
            for batch in tqdm(loader, desc=description):
                audio, has_leak, distance, shape = self._move_batch_to_device(batch)

                if training:
                    self.optimizer.zero_grad()

                detection_logits, distance_pred, shape_logits = self.model(audio)
                losses = self.criterion(
                    (detection_logits, distance_pred, shape_logits),
                    (has_leak, distance, shape),
                )

                if training:
                    losses["total"].backward()
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                    self.optimizer.step()

                total_loss += losses["total"].item()
                detection_loss += losses["detection"]
                distance_loss += losses["distance"]
                shape_loss += losses["shape"]

                detection_pred = torch.argmax(detection_logits, dim=1)
                shape_pred = torch.argmax(shape_logits, dim=1)
                detection_correct += (detection_pred == has_leak).sum().item()
                detection_total += has_leak.size(0)
                shape_correct += (shape_pred == shape).sum().item()
                shape_total += shape.size(0)
                distance_errors.extend(
                    torch.abs(distance_pred.squeeze() - distance).detach().cpu().numpy()
                )

        n_batches = len(loader)
        metrics = {
            "total": total_loss / n_batches,
            "detection": detection_loss / n_batches,
            "distance": distance_loss / n_batches,
            "shape": shape_loss / n_batches,
            "detection_acc": detection_correct / detection_total,
            "shape_acc": shape_correct / shape_total,
            "distance_mae": float(np.mean(distance_errors)),
        }
        return metrics

    def train_epoch(self) -> dict:
        """Run one training epoch."""
        return self._run_epoch(
            self.train_loader,
            training=True,
            description=f"Epoch {self.current_epoch}",
        )

    def validate(self) -> dict:
        """Run one validation epoch."""
        return self._run_epoch(self.val_loader, training=False, description="Validation")

    def log_metrics(self, train_metrics: dict, val_metrics: dict, epoch: int) -> None:
        """Write epoch metrics to TensorBoard."""
        self.writer.add_scalar("Loss/train_total", train_metrics["total"], epoch)
        self.writer.add_scalar("Loss/train_detection", train_metrics["detection"], epoch)
        self.writer.add_scalar("Loss/train_distance", train_metrics["distance"], epoch)
        self.writer.add_scalar("Loss/train_shape", train_metrics["shape"], epoch)

        self.writer.add_scalar("Loss/val_total", val_metrics["total"], epoch)
        self.writer.add_scalar("Loss/val_detection", val_metrics["detection"], epoch)
        self.writer.add_scalar("Loss/val_distance", val_metrics["distance"], epoch)
        self.writer.add_scalar("Loss/val_shape", val_metrics["shape"], epoch)
        self.writer.add_scalar("Metrics/detection_acc", val_metrics["detection_acc"], epoch)
        self.writer.add_scalar("Metrics/shape_acc", val_metrics["shape_acc"], epoch)
        self.writer.add_scalar("Metrics/distance_mae", val_metrics["distance_mae"], epoch)
        self.writer.add_scalar("LR", self.optimizer.param_groups[0]["lr"], epoch)

    def save_checkpoint(self, is_best: bool = False) -> None:
        """Save the latest checkpoint and optionally the best checkpoint."""
        checkpoint = {
            "epoch": self.current_epoch,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "best_val_loss": self.best_val_loss,
            "config": self.config,
        }

        torch.save(checkpoint, self.output_dir / "checkpoint_last.pth")
        if is_best:
            torch.save(checkpoint, self.output_dir / "checkpoint_best.pth")
            print(f"Saved best model (val_loss: {self.best_val_loss:.4f})")

    def train(self) -> None:
        """Execute the full training lifecycle."""
        print(f"\nStarting training for {self.config['training']['epochs']} epochs")
        print(f"Output directory: {self.output_dir}\n")

        for epoch in range(self.current_epoch, self.config["training"]["epochs"]):
            self.current_epoch = epoch
            train_metrics = self.train_epoch()
            val_metrics = self.validate()

            if self.scheduler is not None:
                self.scheduler.step()

            self.log_metrics(train_metrics, val_metrics, epoch)
            print(f"\nEpoch {epoch} Summary:")
            print(f"  Train Loss: {train_metrics['total']:.4f}")
            print(f"  Val Loss: {val_metrics['total']:.4f}")
            print(f"  Detection Acc: {val_metrics['detection_acc']:.4f}")
            print(f"  Shape Acc: {val_metrics['shape_acc']:.4f}")
            print(f"  Distance MAE: {val_metrics['distance_mae']:.4f}")

            is_best = val_metrics["total"] < self.best_val_loss
            if is_best:
                self.best_val_loss = val_metrics["total"]
                self.patience_counter = 0
            else:
                self.patience_counter += 1

            self.save_checkpoint(is_best=is_best)

            if self.patience_counter >= self.config["training"]["early_stopping_patience"]:
                print(f"\nEarly stopping triggered after {epoch} epochs")
                break

        print("\nTraining completed!")
        print(f"Best validation loss: {self.best_val_loss:.4f}")
        self.writer.close()
