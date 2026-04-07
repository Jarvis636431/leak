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
python src/train.py --config configs/config.yaml
```

### Evaluation
```bash
python src/evaluate.py --checkpoint outputs/checkpoints/best_model.pth
```

### Inference
```bash
python src/inference.py --audio path/to/audio.wav
```

## Project Structure

```
.
├── configs/              # Configuration files
├── data/                 # Data directory
│   ├── raw/             # Raw audio files
│   ├── processed/       # Processed features
│   └── annotations/     # Labels and annotations
├── src/                  # Source code
│   ├── data/            # Data loading and preprocessing
│   ├── models/          # Model architectures
│   └── utils/           # Utility functions
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
