"""Training CLI for the Conformer-based pipeline leak detector."""

import argparse
from leak_detection.training import Trainer
from leak_detection.utils import load_config


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

    if args.output_dir is None:
        args.output_dir = Trainer.default_output_dir()

    trainer = Trainer(config, args.output_dir)
    if args.resume:
        trainer.resume(args.resume)
    trainer.train()


if __name__ == "__main__":
    main()
