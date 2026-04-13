"""Training CLI for the Conformer-based pipeline leak detector."""

import argparse
from datetime import datetime
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm

from leak_detection.data import create_dataloader
from leak_detection.models import ConformerLeakDetector
from leak_detection.utils import count_parameters, load_config, resolve_device


class MultiTaskLoss(nn.Module):
    """Multi-task loss with learnable weights (optional)"""

    def __init__(self, weights=None, learnable=False):
        super().__init__()

        if weights is None:
            weights = {"detection": 1.0, "distance": 0.5, "shape": 0.8}

        if learnable:
            # Learnable log variance for uncertainty weighting
            self.log_vars = nn.ParameterDict(
                {
                    "detection": nn.Parameter(torch.zeros(1)),
                    "distance": nn.Parameter(torch.zeros(1)),
                    "shape": nn.Parameter(torch.zeros(1)),
                }
            )
        else:
            self.register_buffer("detection_weight", torch.tensor(weights["detection"]))
            self.register_buffer("distance_weight", torch.tensor(weights["distance"]))
            self.register_buffer("shape_weight", torch.tensor(weights["shape"]))

        self.learnable = learnable
        self.detection_criterion = nn.CrossEntropyLoss()
        self.distance_criterion = nn.MSELoss()
        self.shape_criterion = nn.CrossEntropyLoss()

    def forward(self, predictions, targets):
        detection_logits, distance_pred, shape_logits = predictions
        has_leak, distance, shape = targets

        # Individual losses
        loss_detection = self.detection_criterion(detection_logits, has_leak)
        loss_distance = self.distance_criterion(distance_pred.squeeze(), distance)
        loss_shape = self.shape_criterion(shape_logits, shape)

        if self.learnable:
            # Uncertainty weighting
            loss = (
                torch.exp(-self.log_vars["detection"]) * loss_detection
                + self.log_vars["detection"]
                + torch.exp(-self.log_vars["distance"]) * loss_distance
                + self.log_vars["distance"]
                + torch.exp(-self.log_vars["shape"]) * loss_shape
                + self.log_vars["shape"]
            )
        else:
            # Fixed weighting
            loss = (
                self.detection_weight * loss_detection
                + self.distance_weight * loss_distance
                + self.shape_weight * loss_shape
            )

        return {
            "total": loss,
            "detection": loss_detection.item(),
            "distance": loss_distance.item(),
            "shape": loss_shape.item(),
        }


class Trainer:
    def __init__(self, config, output_dir):
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Setup device
        self.device = resolve_device()
        print(f"Using device: {self.device}")

        # Create dataloaders
        print("Loading datasets...")
        self.train_loader = create_dataloader(config, "train")
        self.val_loader = create_dataloader(config, "val")

        # Create model
        print("Creating model...")
        self.model = ConformerLeakDetector(config["model"]).to(self.device)

        # Count parameters
        total_params, trainable_params = count_parameters(self.model)
        print(f"Total parameters: {total_params:,}")
        print(f"Trainable parameters: {trainable_params:,}")

        # Create optimizer
        self.optimizer = optim.AdamW(
            self.model.parameters(),
            lr=config["training"]["learning_rate"],
            weight_decay=config["training"]["weight_decay"],
        )

        # Create scheduler
        if config["training"]["scheduler"] == "cosine":
            self.scheduler = optim.lr_scheduler.CosineAnnealingLR(
                self.optimizer, T_max=config["training"]["epochs"], eta_min=1e-6
            )
        elif config["training"]["scheduler"] == "step":
            self.scheduler = optim.lr_scheduler.StepLR(
                self.optimizer,
                step_size=config["training"]["scheduler_step"],
                gamma=0.1,
            )
        else:
            self.scheduler = None

        # Create loss function
        self.criterion = MultiTaskLoss(
            weights=config["training"]["loss_weights"], learnable=False
        )

        # Create tensorboard writer
        self.writer = SummaryWriter(self.output_dir / "logs")

        # Training state
        self.current_epoch = 0
        self.best_val_loss = float("inf")
        self.patience_counter = 0

    def train_epoch(self):
        self.model.train()
        total_loss = 0
        detection_loss = 0
        distance_loss = 0
        shape_loss = 0

        pbar = tqdm(self.train_loader, desc=f"Epoch {self.current_epoch}")
        for batch_idx, batch in enumerate(pbar):
            # Move to device
            audio = batch["audio"].to(self.device)
            has_leak = batch["has_leak"].to(self.device)
            distance = batch["distance"].to(self.device)
            shape = batch["shape"].to(self.device)

            # Forward pass
            self.optimizer.zero_grad()
            detection_logits, distance_pred, shape_logits = self.model(audio)

            # Compute loss
            losses = self.criterion(
                (detection_logits, distance_pred, shape_logits),
                (has_leak, distance, shape),
            )

            # Backward pass
            losses["total"].backward()

            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)

            self.optimizer.step()

            # Accumulate losses
            total_loss += losses["total"].item()
            detection_loss += losses["detection"]
            distance_loss += losses["distance"]
            shape_loss += losses["shape"]

            # Update progress bar
            pbar.set_postfix(
                {
                    "loss": f"{losses['total'].item():.4f}",
                    "det": f"{losses['detection']:.4f}",
                    "dist": f"{losses['distance']:.4f}",
                    "shape": f"{losses['shape']:.4f}",
                }
            )

        # Average losses
        n_batches = len(self.train_loader)
        return {
            "total": total_loss / n_batches,
            "detection": detection_loss / n_batches,
            "distance": distance_loss / n_batches,
            "shape": shape_loss / n_batches,
        }

    def validate(self):
        self.model.eval()
        total_loss = 0
        detection_loss = 0
        distance_loss = 0
        shape_loss = 0

        # Metrics
        detection_correct = 0
        detection_total = 0
        shape_correct = 0
        shape_total = 0
        distance_errors = []

        with torch.no_grad():
            for batch in tqdm(self.val_loader, desc="Validation"):
                # Move to device
                audio = batch["audio"].to(self.device)
                has_leak = batch["has_leak"].to(self.device)
                distance = batch["distance"].to(self.device)
                shape = batch["shape"].to(self.device)

                # Forward pass
                detection_logits, distance_pred, shape_logits = self.model(audio)

                # Compute loss
                losses = self.criterion(
                    (detection_logits, distance_pred, shape_logits),
                    (has_leak, distance, shape),
                )

                total_loss += losses["total"].item()
                detection_loss += losses["detection"]
                distance_loss += losses["distance"]
                shape_loss += losses["shape"]

                # Compute metrics
                # Detection accuracy
                detection_pred = torch.argmax(detection_logits, dim=1)
                detection_correct += (detection_pred == has_leak).sum().item()
                detection_total += has_leak.size(0)

                # Shape accuracy
                shape_pred = torch.argmax(shape_logits, dim=1)
                shape_correct += (shape_pred == shape).sum().item()
                shape_total += shape.size(0)

                # Distance MAE
                distance_errors.extend(
                    torch.abs(distance_pred.squeeze() - distance).cpu().numpy()
                )

        n_batches = len(self.val_loader)
        return {
            "total": total_loss / n_batches,
            "detection": detection_loss / n_batches,
            "distance": distance_loss / n_batches,
            "shape": shape_loss / n_batches,
            "detection_acc": detection_correct / detection_total,
            "shape_acc": shape_correct / shape_total,
            "distance_mae": np.mean(distance_errors),
        }

    def log_metrics(self, train_metrics, val_metrics, epoch):
        """Log metrics to tensorboard"""
        # Training losses
        self.writer.add_scalar("Loss/train_total", train_metrics["total"], epoch)
        self.writer.add_scalar(
            "Loss/train_detection", train_metrics["detection"], epoch
        )
        self.writer.add_scalar("Loss/train_distance", train_metrics["distance"], epoch)
        self.writer.add_scalar("Loss/train_shape", train_metrics["shape"], epoch)

        # Validation losses
        self.writer.add_scalar("Loss/val_total", val_metrics["total"], epoch)
        self.writer.add_scalar("Loss/val_detection", val_metrics["detection"], epoch)
        self.writer.add_scalar("Loss/val_distance", val_metrics["distance"], epoch)
        self.writer.add_scalar("Loss/val_shape", val_metrics["shape"], epoch)

        # Validation metrics
        self.writer.add_scalar(
            "Metrics/detection_acc", val_metrics["detection_acc"], epoch
        )
        self.writer.add_scalar("Metrics/shape_acc", val_metrics["shape_acc"], epoch)
        self.writer.add_scalar(
            "Metrics/distance_mae", val_metrics["distance_mae"], epoch
        )

        # Learning rate
        self.writer.add_scalar("LR", self.optimizer.param_groups[0]["lr"], epoch)

    def save_checkpoint(self, is_best=False):
        """Save model checkpoint"""
        checkpoint = {
            "epoch": self.current_epoch,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "best_val_loss": self.best_val_loss,
            "config": self.config,
        }

        # Save latest checkpoint
        torch.save(checkpoint, self.output_dir / "checkpoint_last.pth")

        # Save best checkpoint
        if is_best:
            torch.save(checkpoint, self.output_dir / "checkpoint_best.pth")
            print(f"Saved best model (val_loss: {self.best_val_loss:.4f})")

    def train(self):
        """Main training loop"""
        print(f"\nStarting training for {self.config['training']['epochs']} epochs")
        print(f"Output directory: {self.output_dir}\n")

        for epoch in range(self.config["training"]["epochs"]):
            self.current_epoch = epoch

            # Train
            train_metrics = self.train_epoch()

            # Validate
            val_metrics = self.validate()

            # Update scheduler
            if self.scheduler is not None:
                self.scheduler.step()

            # Log metrics
            self.log_metrics(train_metrics, val_metrics, epoch)

            # Print summary
            print(f"\nEpoch {epoch} Summary:")
            print(f"  Train Loss: {train_metrics['total']:.4f}")
            print(f"  Val Loss: {val_metrics['total']:.4f}")
            print(f"  Detection Acc: {val_metrics['detection_acc']:.4f}")
            print(f"  Shape Acc: {val_metrics['shape_acc']:.4f}")
            print(f"  Distance MAE: {val_metrics['distance_mae']:.4f}")

            # Save checkpoint
            is_best = val_metrics["total"] < self.best_val_loss
            if is_best:
                self.best_val_loss = val_metrics["total"]
                self.patience_counter = 0
            else:
                self.patience_counter += 1

            self.save_checkpoint(is_best)

            # Early stopping
            if (
                self.patience_counter
                >= self.config["training"]["early_stopping_patience"]
            ):
                print(f"\nEarly stopping triggered after {epoch} epochs")
                break

        print(f"\nTraining completed!")
        print(f"Best validation loss: {self.best_val_loss:.4f}")
        self.writer.close()


def main():
    parser = argparse.ArgumentParser(description="Train Conformer Leak Detection Model")
    parser.add_argument(
        "--config", type=str, default="configs/config.yaml", help="Path to config file"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory (default: outputs/timestamp)",
    )
    parser.add_argument(
        "--resume", type=str, default=None, help="Path to checkpoint to resume from"
    )
    args = parser.parse_args()

    config = load_config(args.config)

    # Create output directory
    if args.output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output_dir = f"outputs/{timestamp}"

    # Create trainer and train
    trainer = Trainer(config, args.output_dir)

    # Resume from checkpoint if specified
    if args.resume:
        print(f"Resuming from {args.resume}")
        checkpoint = torch.load(args.resume, map_location=trainer.device)
        trainer.model.load_state_dict(checkpoint["model_state_dict"])
        trainer.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        trainer.current_epoch = checkpoint["epoch"]
        trainer.best_val_loss = checkpoint["best_val_loss"]

    trainer.train()


if __name__ == "__main__":
    main()
