"""Dataset preparation CLI for converting raw CSV files into training splits."""

import argparse
import random
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

DEFAULT_LABEL_MAP = {
    (1, 6): (11, 1),
    (7, 12): (5, 1),
    (13, 18): (6, 1),
    (19, 24): (6, 1),
    (25, 30): (4, 1),
    (31, 36): (5, 1),
    (37, 42): (5, 1),
    (43, 48): (2, 1),
    (49, 54): (4, 1),
    (55, 72): (14, 1),
    (73, 84): (16, 1),
    (85, 102): (12, 1),
    (103, 108): (11, 1),
    (109, 114): (5, 1),
    (115, 120): (3, 1),
    (121, 126): (3, 2),
    (127, 132): (3, 2),
    (133, 138): (5, 2),
    (139, 156): (12, 2),
    (157, 168): (16, 2),
    (169, 186): (14, 2),
    (187, 9999): 0,
}


def read_csv_safe(path: Path) -> pd.DataFrame:
    """Load a raw CSV with a fallback encoding strategy."""
    try:
        dataframe = pd.read_csv(path, header=None, encoding="gbk", low_memory=False)
    except UnicodeDecodeError:
        dataframe = pd.read_csv(path, header=None, encoding="latin-1", low_memory=False)

    dataframe = dataframe.iloc[1:].reset_index(drop=True)
    return dataframe.apply(pd.to_numeric, errors="coerce").dropna()


def get_abc_number(filename: str) -> int:
    """Extract the numeric ABC id from a filename."""
    number = "".join(filter(str.isdigit, filename))
    return int(number) if number else -1


def get_label(abc_num: int, label_map: dict) -> tuple | int | None:
    """Resolve the label configuration for a given ABC id."""
    for (min_value, max_value), config in label_map.items():
        if min_value <= abc_num <= max_value:
            return config
    return None


def collect_files(raw_dir: Path, label_map: dict) -> list[dict]:
    """Collect every labeled CSV file under the raw directory."""
    files = []
    for filepath in sorted(raw_dir.rglob("*.csv")):
        abc_num = get_abc_number(filepath.name)
        label_cfg = get_label(abc_num, label_map)
        if label_cfg is None:
            continue
        files.append({"path": filepath, "abc": abc_num, "label_cfg": label_cfg})
    return files


def split_files(files: list[dict], train_ratio: float, val_ratio: float, seed: int) -> dict:
    """Split files into train, validation, and test sets."""
    random.Random(seed).shuffle(files)
    total = len(files)
    train_end = int(total * train_ratio)
    val_end = train_end + int(total * val_ratio)
    return {
        "train": files[:train_end],
        "val": files[train_end:val_end],
        "test": files[val_end:],
    }


def get_stratification_label(item: dict) -> str:
    """Build a stable file-level label for stratified k-fold splitting."""
    label_cfg = item["label_cfg"]
    if isinstance(label_cfg, (tuple, list)):
        distance, shape = label_cfg
        return f"leak_d{distance}_s{shape}"
    return f"normal_{label_cfg}"


def split_files_kfold(files: list[dict], k_folds: int, seed: int, val_fold_offset: int) -> list[dict]:
    """Create file-level k-fold split maps without mixing segments from the same raw file."""
    labels = [get_stratification_label(item) for item in files]
    splitter = StratifiedKFold(n_splits=k_folds, shuffle=True, random_state=seed)
    file_indices = np.arange(len(files))
    fold_indices = [test_indices for _, test_indices in splitter.split(file_indices, labels)]

    split_maps = []
    for test_fold_index, test_indices in enumerate(fold_indices):
        val_fold_index = (test_fold_index + val_fold_offset) % k_folds
        val_indices = set(fold_indices[val_fold_index].tolist())
        test_indices_set = set(test_indices.tolist())
        train_indices = [
            index
            for index in file_indices.tolist()
            if index not in val_indices and index not in test_indices_set
        ]
        split_maps.append(
            {
                "train": [files[index] for index in train_indices],
                "val": [files[index] for index in sorted(val_indices)],
                "test": [files[index] for index in sorted(test_indices_set)],
            }
        )
    return split_maps


def process_split(
    file_list: list[dict],
    split_name: str,
    stage1_dir: Path,
    stage2_dir: Path,
    segment_points: int,
) -> tuple[list[dict], list[dict]]:
    """Convert one split into segmented stage1/stage2 outputs."""
    stage1_rows = []
    stage2_rows = []

    for item in file_list:
        dataframe = read_csv_safe(item["path"])
        if len(dataframe) < segment_points:
            continue

        left = dataframe.iloc[:, 1].values.astype(np.float32)
        right = dataframe.iloc[:, 2].values.astype(np.float32)
        num_segments = len(dataframe) // segment_points
        abc_num = item["abc"]
        label_cfg = item["label_cfg"]

        is_leak = isinstance(label_cfg, (tuple, list))
        if is_leak:
            distance, shape = label_cfg
        else:
            distance = 0
            shape = label_cfg

        for index in range(num_segments):
            start = index * segment_points
            end = (index + 1) * segment_points
            segment_name = f"ABC{abc_num}_seg{index}"

            left_stage2 = stage2_dir / split_name / f"{segment_name}_left.csv"
            right_stage2 = stage2_dir / split_name / f"{segment_name}_right.csv"
            pd.DataFrame(left[start:end]).to_csv(left_stage2, index=False, header=False)
            pd.DataFrame(right[start:end]).to_csv(right_stage2, index=False, header=False)
            stage2_rows.append({"path": str(left_stage2), "label": shape})
            stage2_rows.append({"path": str(right_stage2), "label": shape})

            if not is_leak:
                continue

            left_stage1 = stage1_dir / split_name / f"{segment_name}_left.csv"
            right_stage1 = stage1_dir / split_name / f"{segment_name}_right.csv"
            pd.DataFrame(left[start:end]).to_csv(left_stage1, index=False, header=False)
            pd.DataFrame(right[start:end]).to_csv(right_stage1, index=False, header=False)
            stage1_rows.append(
                {
                    "path_left": str(left_stage1),
                    "path_right": str(right_stage1),
                    "distance": distance,
                }
            )

    return stage1_rows, stage2_rows


def process_kfold_segments(
    files: list[dict],
    stage1_dir: Path,
    stage2_dir: Path,
    segment_points: int,
) -> tuple[list[dict], list[dict]]:
    """Write each segment once and return fold-ready manifests with raw ids."""
    stage1_rows = []
    stage2_rows = []

    stage1_dir.mkdir(parents=True, exist_ok=True)
    stage2_dir.mkdir(parents=True, exist_ok=True)

    for item in files:
        dataframe = read_csv_safe(item["path"])
        if len(dataframe) < segment_points:
            continue

        left = dataframe.iloc[:, 1].values.astype(np.float32)
        right = dataframe.iloc[:, 2].values.astype(np.float32)
        num_segments = len(dataframe) // segment_points
        abc_num = item["abc"]
        raw_id = f"ABC{abc_num}"
        label_cfg = item["label_cfg"]

        is_leak = isinstance(label_cfg, (tuple, list))
        if is_leak:
            distance, shape = label_cfg
        else:
            distance = 0
            shape = label_cfg

        for index in range(num_segments):
            start = index * segment_points
            end = (index + 1) * segment_points
            segment_name = f"{raw_id}_seg{index}"

            left_stage2 = stage2_dir / f"{segment_name}_left.csv"
            right_stage2 = stage2_dir / f"{segment_name}_right.csv"
            pd.DataFrame(left[start:end]).to_csv(left_stage2, index=False, header=False)
            pd.DataFrame(right[start:end]).to_csv(right_stage2, index=False, header=False)
            stage2_rows.append({"path": str(left_stage2), "label": shape, "raw_id": raw_id})
            stage2_rows.append({"path": str(right_stage2), "label": shape, "raw_id": raw_id})

            if not is_leak:
                continue

            left_stage1 = stage1_dir / f"{segment_name}_left.csv"
            right_stage1 = stage1_dir / f"{segment_name}_right.csv"
            pd.DataFrame(left[start:end]).to_csv(left_stage1, index=False, header=False)
            pd.DataFrame(right[start:end]).to_csv(right_stage1, index=False, header=False)
            stage1_rows.append(
                {
                    "path_left": str(left_stage1),
                    "path_right": str(right_stage1),
                    "distance": distance,
                    "raw_id": raw_id,
                }
            )

    return stage1_rows, stage2_rows


def attach_split_column(rows: list[dict], split_map: dict) -> list[dict]:
    """Add train/val/test split labels to manifest rows for one fold."""
    raw_to_split = {}
    for split_name, files in split_map.items():
        for item in files:
            raw_to_split[f"ABC{item['abc']}"] = split_name

    fold_rows = []
    for row in rows:
        split_name = raw_to_split.get(row["raw_id"])
        if split_name is None:
            continue
        fold_row = dict(row)
        fold_row["split"] = split_name
        fold_rows.append(fold_row)
    return fold_rows


def ensure_split_dirs(*base_dirs: Path) -> None:
    """Create per-split output directories."""
    for base_dir in base_dirs:
        for split in ("train", "val", "test"):
            (base_dir / split).mkdir(parents=True, exist_ok=True)


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    parser = argparse.ArgumentParser(description="Prepare segmented leak-detection datasets")
    parser.add_argument("--raw-dir", default="raw", help="Directory containing raw CSV files")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory for generated stage datasets",
    )
    parser.add_argument("--segment-seconds", type=int, default=5, help="Segment length in seconds")
    parser.add_argument("--sampling-rate", type=int, default=25600, help="Sample rate of the raw CSV signal")
    parser.add_argument("--train-ratio", type=float, default=0.7, help="Train split ratio")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="Validation split ratio")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for split shuffling")
    parser.add_argument(
        "--k-folds",
        type=int,
        default=0,
        help="Generate file-level stratified k-fold manifests in a separate output tree",
    )
    parser.add_argument(
        "--val-fold-offset",
        type=int,
        default=1,
        help="For k-fold output, use fold (test_fold + offset) as validation",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    raw_dir = Path(args.raw_dir)
    output_dir = Path(
        args.output_dir
        or ("artifacts/5sdata_kfold" if args.k_folds else "artifacts/5sdata")
    )
    stage1_dir = output_dir / "stage1data"
    stage2_dir = output_dir / "stage2data"
    segment_points = args.sampling_rate * args.segment_seconds

    all_files = collect_files(raw_dir, DEFAULT_LABEL_MAP)

    if args.k_folds:
        if args.k_folds < 3:
            raise ValueError("--k-folds must be at least 3 when one fold is reserved for validation")

        segments_dir = output_dir / "segments"
        stage1_rows, stage2_rows = process_kfold_segments(
            files=all_files,
            stage1_dir=segments_dir / "stage1data",
            stage2_dir=segments_dir / "stage2data",
            segment_points=segment_points,
        )
        split_maps = split_files_kfold(
            files=all_files,
            k_folds=args.k_folds,
            seed=args.seed,
            val_fold_offset=args.val_fold_offset,
        )

        for fold_index, split_map in enumerate(split_maps):
            fold_dir = output_dir / f"fold_{fold_index}"
            fold_dir.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(attach_split_column(stage1_rows, split_map)).to_csv(
                fold_dir / "stage1.csv",
                index=False,
            )
            pd.DataFrame(attach_split_column(stage2_rows, split_map)).to_csv(
                fold_dir / "stage2.csv",
                index=False,
            )

        print("\nK-fold dataset preparation completed.")
        print(f"Raw files scanned: {len(all_files)}")
        print(f"K folds: {args.k_folds}")
        print(f"Stage1 leak pairs per full fold manifest: {len(stage1_rows)}")
        print(f"Stage2 labeled segments per full fold manifest: {len(stage2_rows)}")
        print(f"Artifacts written to: {output_dir}")
        return

    ensure_split_dirs(stage1_dir, stage2_dir)
    split_map = split_files(all_files, args.train_ratio, args.val_ratio, args.seed)

    stage1_rows: list[dict] = []
    stage2_rows: list[dict] = []
    for split_name, file_list in split_map.items():
        split_stage1_rows, split_stage2_rows = process_split(
            file_list=file_list,
            split_name=split_name,
            stage1_dir=stage1_dir,
            stage2_dir=stage2_dir,
            segment_points=segment_points,
        )
        stage1_rows.extend(split_stage1_rows)
        stage2_rows.extend(split_stage2_rows)

    pd.DataFrame(stage1_rows).to_csv(output_dir / "stage1.csv", index=False)
    pd.DataFrame(stage2_rows).to_csv(output_dir / "stage2.csv", index=False)

    print("\nDataset preparation completed.")
    print(f"Raw files scanned: {len(all_files)}")
    print(f"Stage1 leak pairs: {len(stage1_rows)}")
    print(f"Stage2 labeled segments: {len(stage2_rows)}")
    print(f"Artifacts written to: {output_dir}")


if __name__ == "__main__":
    main()
