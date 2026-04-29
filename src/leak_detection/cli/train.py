"""Training CLI for segmented signal tasks."""

import argparse
from leak_detection.training import Trainer
from leak_detection.utils import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a model on stage1 or stage2 manifests")
    parser.add_argument(
        "--config", type=str, default="configs/stage2.yaml", help="Path to a task config file"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Override the configured output directory",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default=None,
        help="Override the configured data manifest path",
    )
    parser.add_argument("--resume", type=str, default=None, help="Path to checkpoint to resume from")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.manifest is not None:
        config["data"]["manifest"] = args.manifest

    if args.output_dir is None:
        args.output_dir = Trainer.default_output_dir(config["output"]["base_dir"], config["task"])

    trainer = Trainer(config, args.output_dir)
    if args.resume:
        trainer.resume(args.resume)
    trainer.train()


if __name__ == "__main__":
    main()
