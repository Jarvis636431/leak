"""Prediction helpers for single audio files."""

import json
from pathlib import Path

import torch

from leak_detection.data.audio import fit_waveform_length, load_waveform
from leak_detection.data.features import build_mel_transform, extract_mel_features
from leak_detection.models import ConformerLeakDetector
from leak_detection.utils import resolve_device


class LeakPredictor:
    """Load a checkpoint once and serve single-file predictions."""

    def __init__(self, config: dict, checkpoint_path: str | Path):
        self.config = config
        self.device = resolve_device()
        self.model = ConformerLeakDetector(config["model"]).to(self.device)
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.eval()
        self.mel_spectrogram, self.amplitude_to_db = build_mel_transform(
            sample_rate=config["audio"]["sample_rate"],
            n_mels=config["audio"]["n_mels"],
            n_fft=config["audio"]["n_fft"],
            hop_length=config["audio"]["hop_length"],
        )

    def predict_file(self, audio_path: str | Path, shape_labels: list[str] | None = None) -> dict:
        """Run inference for one audio file and return a serializable result."""
        waveform = load_waveform(audio_path, self.config["audio"]["sample_rate"])
        waveform = fit_waveform_length(
            waveform,
            sample_rate=self.config["audio"]["sample_rate"],
            max_length=self.config["audio"]["max_length"],
            random_crop=False,
        )
        features = extract_mel_features(
            waveform,
            mel_spectrogram=self.mel_spectrogram,
            amplitude_to_db=self.amplitude_to_db,
        ).unsqueeze(0).to(self.device)

        with torch.no_grad():
            predictions = self.model.predict(features)

        result = {
            "leak_detected": bool(predictions["leak_detected"][0]),
            "leak_probability": float(predictions["leak_probability"][0]),
            "estimated_distance": float(predictions["distance"]),
            "predicted_shape_class": int(predictions["shape_class"][0]),
            "shape_probabilities": predictions["shape_probability"][0].tolist(),
        }
        if shape_labels and result["predicted_shape_class"] < len(shape_labels):
            result["predicted_shape_label"] = shape_labels[result["predicted_shape_class"]]
        return result

    @staticmethod
    def save_prediction(result: dict, audio_path: str | Path) -> Path:
        """Write the prediction result next to the invocation cwd."""
        output_path = Path(audio_path).stem + "_prediction.json"
        with open(output_path, "w", encoding="utf-8") as file:
            json.dump(result, file, indent=2)
        return Path(output_path)


def print_prediction_results(results: dict, shape_labels: list[str] | None = None) -> None:
    """Print prediction results in a readable format."""
    print("\n" + "=" * 50)
    print("PREDICTION RESULTS")
    print("=" * 50)
    print("\n1. Leak Detection:")
    print(f"   Status: {'LEAK DETECTED' if results['leak_detected'] else 'NO LEAK'}")
    print(f"   Confidence: {results['leak_probability'] * 100:.2f}%")

    if not results["leak_detected"]:
        return

    print("\n2. Distance Estimation:")
    print(f"   Estimated Distance: {results['estimated_distance']:.2f} meters")
    print("\n3. Leak Shape Classification:")
    if "predicted_shape_label" in results:
        print(f"   Predicted Shape: {results['predicted_shape_label']}")
    else:
        print(f"   Predicted Shape Class: {results['predicted_shape_class']}")

    print("\n   Shape Probabilities:")
    if shape_labels:
        for label, probability in zip(shape_labels, results["shape_probabilities"]):
            print(f"      {label}: {probability * 100:.2f}%")
    else:
        for index, probability in enumerate(results["shape_probabilities"]):
            print(f"      Class {index}: {probability * 100:.2f}%")
