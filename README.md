# Pipeline Leak Detection

Training pipeline for segmented CSV signals generated from raw pipeline sensor data.

## Current Workflow

1. Prepare raw data under `raw/`
2. Generate segmented datasets with:

```bash
leak-prepare-dataset --raw-dir raw --output-dir artifacts/5sdata
```

3. Train a task-specific model directly on the generated manifests:

```bash
# Stage2: single-channel classification on stage2.csv
PYTHONPATH=src python -m leak_detection.cli.train --config configs/stage2.yaml

# Stage1: dual-channel distance regression on stage1.csv
PYTHONPATH=src python -m leak_detection.cli.train --config configs/stage1.yaml
```

## Using just

If you have `just` installed, the common workflows are wrapped in the project `Justfile`:

```bash
just install
just prepare
just train-stage2
just train-stage1
just smoke-stage2
just smoke-stage1
```

## Dataset Contracts

### Stage2

- Manifest: `artifacts/5sdata/stage2.csv`
- Input: one segmented CSV path per row
- Target: `label`
- Task: classification

### Stage1

- Manifest: `artifacts/5sdata/stage1.csv`
- Input: `path_left` + `path_right`
- Target: `distance`
- Task: regression

## Project Structure

```text
.
├── configs/                # Task configs for stage1/stage2 training
├── raw/                    # Raw source CSV data
├── artifacts/5sdata/       # Generated segmented datasets
├── src/leak_detection/
│   ├── cli/                # Dataset preparation and training entry points
│   ├── data/               # Segmented CSV datasets and dataloaders
│   ├── models/             # Task-specific 1D CNN models
│   ├── training/           # Unified trainer
│   └── utils/              # Shared config/runtime helpers
└── outputs/                # Training runs and checkpoints
```

## Notes

- The old audio-based Conformer pipeline has been removed.
- `leak-train` still exists as a package entry point, but if your editable install is stale, use `PYTHONPATH=src python -m leak_detection.cli.train ...`.
- If you change `pyproject.toml` scripts or dependencies, reinstall the package:

```bash
uv pip install .
```
