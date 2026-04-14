"""Evaluation CLI for trained Conformer checkpoints."""

import argparse
from leak_detection.evaluation import Evaluator
from leak_detection.utils import load_config


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

    evaluator = Evaluator(config, args.checkpoint, args.output_dir)
    evaluator.evaluate()

    print("\n" + "=" * 50)
    print("EVALUATION COMPLETE")
    print("=" * 50)
    print(f"Results saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
