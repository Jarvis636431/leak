"""Inference CLI for single-file leak predictions."""

import argparse
from leak_detection.inference import LeakPredictor, print_prediction_results
from leak_detection.utils import load_config


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

    predictor = LeakPredictor(config, args.checkpoint)
    results = predictor.predict_file(args.audio, args.shape_labels)
    print_prediction_results(results, args.shape_labels)
    output_path = predictor.save_prediction(results, args.audio)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
