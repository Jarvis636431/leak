"""Inference CLI for single-file leak predictions."""

import argparse
from pathlib import Path

import torch
import torchaudio
import torchaudio.transforms as T

from leak_detection.models import ConformerLeakDetector
from leak_detection.utils import load_config, resolve_device


def load_audio(filepath, sample_rate=16000, max_length=5.0):
    """Load and preprocess single audio file"""
    waveform, sr = torchaudio.load(filepath)

    # Convert to mono
    if waveform.shape[0] > 1:
        waveform = torch.mean(waveform, dim=0, keepdim=True)

    # Resample if necessary
    if sr != sample_rate:
        resampler = T.Resample(sr, sample_rate)
        waveform = resampler(waveform)

    # Pad or truncate
    target_length = int(sample_rate * max_length)
    current_length = waveform.shape[1]

    if current_length > target_length:
        start = (current_length - target_length) // 2
        waveform = waveform[:, start : start + target_length]
    elif current_length < target_length:
        padding = target_length - current_length
        waveform = torch.nn.functional.pad(waveform, (0, padding))

    return waveform


def extract_features(
    waveform, sample_rate=16000, n_mels=128, n_fft=1024, hop_length=512
):
    """Extract mel spectrogram features"""
    mel_spectrogram = T.MelSpectrogram(
        sample_rate=sample_rate, n_fft=n_fft, hop_length=hop_length, n_mels=n_mels
    )
    amplitude_to_db = T.AmplitudeToDB(st_ref=1.0, top_db=80.0)

    mel_spec = mel_spectrogram(waveform)
    mel_spec = amplitude_to_db(mel_spec)

    # Normalize
    mel_spec = (mel_spec - mel_spec.mean()) / (mel_spec.std() + 1e-8)

    # Reshape to (time, n_mels)
    mel_spec = mel_spec.squeeze(0).transpose(0, 1)

    return mel_spec


def inference(audio_path, config, checkpoint_path, shape_labels=None):
    """
    Run inference on a single audio file

    Args:
        audio_path: Path to audio file
        config: Configuration dict
        checkpoint_path: Path to model checkpoint
        shape_labels: List of shape class names (optional)

    Returns:
        predictions: Dict with prediction results
    """
    # Setup device
    device = resolve_device()

    # Load model
    model = ConformerLeakDetector(config["model"]).to(device)
    checkpoint = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    # Load and preprocess audio
    print(f"Loading audio: {audio_path}")
    waveform = load_audio(
        audio_path,
        sample_rate=config["audio"]["sample_rate"],
        max_length=config["audio"]["max_length"],
    )

    # Extract features
    features = extract_features(
        waveform,
        sample_rate=config["audio"]["sample_rate"],
        n_mels=config["audio"]["n_mels"],
        n_fft=config["audio"]["n_fft"],
        hop_length=config["audio"]["hop_length"],
    )

    # Add batch dimension
    features = features.unsqueeze(0).to(device)

    # Run inference
    print("Running inference...")
    with torch.no_grad():
        predictions = model.predict(features)

    # Format results
    results = {
        "leak_detected": bool(predictions["leak_detected"][0]),
        "leak_probability": float(predictions["leak_probability"][0]),
        "estimated_distance": float(predictions["distance"]),
        "predicted_shape_class": int(predictions["shape_class"][0]),
        "shape_probabilities": predictions["shape_probability"][0].tolist(),
    }

    # Add shape label if provided
    if shape_labels and results["predicted_shape_class"] < len(shape_labels):
        results["predicted_shape_label"] = shape_labels[
            results["predicted_shape_class"]
        ]

    return results


def print_results(results, shape_labels=None):
    """Print prediction results"""
    print("\n" + "=" * 50)
    print("PREDICTION RESULTS")
    print("=" * 50)

    print(f"\n1. Leak Detection:")
    print(f"   Status: {'LEAK DETECTED' if results['leak_detected'] else 'NO LEAK'}")
    print(f"   Confidence: {results['leak_probability'] * 100:.2f}%")

    if results["leak_detected"]:
        print(f"\n2. Distance Estimation:")
        print(f"   Estimated Distance: {results['estimated_distance']:.2f} meters")

        print(f"\n3. Leak Shape Classification:")
        if "predicted_shape_label" in results:
            print(f"   Predicted Shape: {results['predicted_shape_label']}")
        else:
            print(f"   Predicted Shape Class: {results['predicted_shape_class']}")

        print(f"\n   Shape Probabilities:")
        if shape_labels:
            for i, (label, prob) in enumerate(
                zip(shape_labels, results["shape_probabilities"])
            ):
                print(f"      {label}: {prob * 100:.2f}%")
        else:
            for i, prob in enumerate(results["shape_probabilities"]):
                print(f"      Class {i}: {prob * 100:.2f}%")


def main():
    parser = argparse.ArgumentParser(description="Run inference on audio file")
    parser.add_argument("--audio", type=str, required=True, help="Path to audio file")
    parser.add_argument(
        "--config", type=str, default="configs/config.yaml", help="Path to config file"
    )
    parser.add_argument(
        "--checkpoint", type=str, required=True, help="Path to model checkpoint"
    )
    parser.add_argument(
        "--shape-labels",
        type=str,
        nargs="+",
        default=["Circle", "Crack", "Corrosion", "Hole", "Other"],
        help="Labels for shape classes",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    # Run inference
    results = inference(args.audio, config, args.checkpoint, args.shape_labels)

    # Print results
    print_results(results, args.shape_labels)

    # Save results to JSON
    import json

    output_path = Path(args.audio).stem + "_prediction.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
