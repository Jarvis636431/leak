# Pipeline Leak Detection

Audio recognition system for pipeline leak detection using deep learning.

## Features

- 🔊 Leak detection (binary classification)
- 📏 Distance estimation (regression)
- 🔷 Leak shape classification (multi-class)

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd pipeline-leak-detection

# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -e .
```

## Usage

### Training
```bash
leak-train --config configs/config.yaml
```

### Evaluation
```bash
leak-evaluate --checkpoint outputs/checkpoints/best_model.pth
```

### Inference
```bash
leak-inference --audio path/to/audio.wav --checkpoint outputs/checkpoints/best_model.pth
```

### Dataset Preparation
```bash
leak-prepare-dataset --raw-dir raw --output-dir artifacts/5sdata
```

## Project Structure

```
.
├── configs/              # Configuration files
├── raw/                  # Ignored raw source CSV/audio data
├── artifacts/            # Generated datasets and experiment outputs
├── src/                  # Source root
│   └── leak_detection/   # Installable Python package
│       ├── cli/          # Training / evaluation / inference entry points
│       ├── data/         # Data loading and preprocessing
│       ├── models/       # Model architectures
│       └── utils/        # Utility functions
├── outputs/             # Training outputs
│   ├── checkpoints/     # Model checkpoints
│   ├── logs/           # Training logs
│   └── results/        # Evaluation results
└── notebooks/          # Jupyter notebooks for exploration
```

## Requirements

- Python >= 3.10, < 3.13
- PyTorch >= 2.0.0
- librosa >= 0.10.0

## License

MIT License
