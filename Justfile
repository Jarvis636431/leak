set shell := ["zsh", "-cu"]

default:
    @just --list

install:
    uv venv --python 3.12
    source .venv/bin/activate
    uv pip install .

prepare:
    source .venv/bin/activate
    leak-prepare-dataset --raw-dir raw --output-dir artifacts/5sdata

train-stage2:
    source .venv/bin/activate
    leak-train --config configs/stage2.yaml

train-stage1:
    source .venv/bin/activate
    leak-train --config configs/stage1.yaml

train-stage2-out output_dir:
    source .venv/bin/activate
    leak-train --config configs/stage2.yaml --output-dir {{output_dir}}

train-stage1-out output_dir:
    source .venv/bin/activate
    leak-train --config configs/stage1.yaml --output-dir {{output_dir}}

resume-stage2 checkpoint:
    source .venv/bin/activate
    leak-train --config configs/stage2.yaml --resume {{checkpoint}}

resume-stage1 checkpoint:
    source .venv/bin/activate
    leak-train --config configs/stage1.yaml --resume {{checkpoint}}

smoke-stage2:
    source .venv/bin/activate
    PYTHONPATH=src python - <<'PY'
    from leak_detection.utils import load_config
    from leak_detection.data import build_dataloaders
    from leak_detection.models import build_model

    config = load_config("configs/stage2.yaml")
    loaders = build_dataloaders(config)
    batch = next(iter(loaders["train"]))
    model = build_model(config)
    output = model(batch["signal"])

    print("stage2 signal:", tuple(batch["signal"].shape))
    print("stage2 target:", tuple(batch["target"].shape))
    print("stage2 output:", tuple(output.shape))
    PY

smoke-stage1:
    source .venv/bin/activate
    PYTHONPATH=src python - <<'PY'
    from leak_detection.utils import load_config
    from leak_detection.data import build_dataloaders
    from leak_detection.models import build_model

    config = load_config("configs/stage1.yaml")
    loaders = build_dataloaders(config)
    batch = next(iter(loaders["train"]))
    model = build_model(config)
    output = model(batch["signal"])

    print("stage1 signal:", tuple(batch["signal"].shape))
    print("stage1 target:", tuple(batch["target"].shape))
    print("stage1 output:", tuple(output.shape))
    PY

show-stage1:
    python - <<'PY'
    import pandas as pd

    manifest = pd.read_csv("artifacts/5sdata/stage1.csv")
    print(manifest.head().to_string(index=False))
    PY

show-stage2:
    python - <<'PY'
    import pandas as pd

    manifest = pd.read_csv("artifacts/5sdata/stage2.csv")
    print(manifest.head().to_string(index=False))
    print()
    print(manifest["label"].value_counts().sort_index().to_string())
    PY

thesis-build:
    cd 2024-latex && latexmk -xelatex main.tex

thesis-clean:
    cd 2024-latex && latexmk -c

thesis-rebuild:
    cd 2024-latex && latexmk -C && latexmk -xelatex main.tex
