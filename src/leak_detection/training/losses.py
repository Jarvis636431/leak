"""Loss functions used during training."""

import torch
import torch.nn as nn


class MultiTaskLoss(nn.Module):
    """Weighted multi-task loss for detection, distance, and shape prediction."""

    def __init__(self, weights: dict | None = None, learnable: bool = False):
        super().__init__()

        if weights is None:
            weights = {"detection": 1.0, "distance": 0.5, "shape": 0.8}

        if learnable:
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

        loss_detection = self.detection_criterion(detection_logits, has_leak)
        loss_distance = self.distance_criterion(distance_pred.squeeze(), distance)
        loss_shape = self.shape_criterion(shape_logits, shape)

        if self.learnable:
            total_loss = (
                torch.exp(-self.log_vars["detection"]) * loss_detection
                + self.log_vars["detection"]
                + torch.exp(-self.log_vars["distance"]) * loss_distance
                + self.log_vars["distance"]
                + torch.exp(-self.log_vars["shape"]) * loss_shape
                + self.log_vars["shape"]
            )
        else:
            total_loss = (
                self.detection_weight * loss_detection
                + self.distance_weight * loss_distance
                + self.shape_weight * loss_shape
            )

        return {
            "total": total_loss,
            "detection": loss_detection.item(),
            "distance": loss_distance.item(),
            "shape": loss_shape.item(),
        }
