"""
从 stage2inf_test 生成 Stage2 用的「单一路径」索引与切片（仅 5s）。

不再划分验证文件 / 测试文件：每个标签下「排序后的全部」长 CSV 都参与切片。
切片只输出到 val_inf 目录，并写 stage2_val_inf.csv；同一份索引再复制为
stage2_test_inf.csv，便于 config 里 val 与 test 都指向同一份数据而无需改路径。

本目录数据不参与 preparedata 的 stage2 训练。

规则：
  - 文件名形如 A_0.csv，下划线后为标签。
  - 按标签分组，组内按文件名排序，对该标签下所有文件做三通道独立切片。
  - 5s 切片：跳过首行，第 1 列时间不用，第 2/3/4 列为三通道。
"""
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from collections import defaultdict
from pandas.errors import EmptyDataError


REPO_DIR = Path(__file__).resolve().parent
DATA_ROOT = REPO_DIR / "internoisedata"
OUTPUT_ROOT = REPO_DIR / "artifacts" / "internoise_5sdata"
SRC_DIR = DATA_ROOT / "stage2inf_test"
SAMPLE_RATE = 25600
TARGET_SECONDS = [5]


def parse_label_from_name(file_path: Path) -> int:
    match = re.match(r"^.+_(-?\d+)\.csv$", file_path.name)
    if not match:
        raise ValueError(f"文件名不符合 <任意>_<label>.csv: {file_path.name}")
    return int(match.group(1))


def load_wave(csv_path: Path):
    # low_memory=False：大文件分块推断类型时会触发 DtypeWarning；一次性读入可避免混类型告警
    df = pd.read_csv(
        csv_path,
        header=None,
        skiprows=1,
        low_memory=False,
    )
    if df.shape[1] < 4:
        raise ValueError(f"文件列数不足4列（时间+3通道）: {csv_path.name}")
    ch_list = []
    for col_idx in [1, 2, 3]:
        wave = pd.to_numeric(df.iloc[:, col_idx], errors="coerce").dropna().to_numpy(dtype=np.float32)
        ch_list.append(wave)
    return ch_list


def assign_all_files(files_by_label: dict):
    """每个 label -> 该标签下全部文件路径（已排序）。"""
    out = {}
    for label, paths in sorted(files_by_label.items(), key=lambda x: x[0]):
        out[label] = sorted(paths, key=lambda p: p.name)
    return out


def slice_and_write(
    csv_path: Path,
    label: int,
    split: str,
    seg_points: int,
    out_dir: Path,
    rows: list,
):
    stem = csv_path.stem
    try:
        waves = load_wave(csv_path)
    except EmptyDataError:
        print(f"⚠️ 跳过空文件：{csv_path.name}")
        return
    except ValueError as e:
        print(f"⚠️ 跳过：{csv_path.name} | {e}")
        return

    for ch_idx, wave in enumerate(waves, start=1):
        if len(wave) < seg_points:
            print(
                f"⚠️ 跳过短通道：{csv_path.name} ch{ch_idx}，长度 {len(wave)} < {seg_points}"
            )
            continue
        n_seg = len(wave) // seg_points
        for i in range(n_seg):
            st = i * seg_points
            ed = (i + 1) * seg_points
            seg = wave[st:ed]
            out_name = f"{split}_{stem}_ch{ch_idx}_seg{i}.csv"
            out_path = out_dir / out_name
            pd.DataFrame(seg).to_csv(out_path, index=False, header=False)
            rows.append(
                {
                    "path": str(out_path.relative_to(REPO_DIR)),
                    "label": label,
                    "src_file": csv_path.name,
                    "channel": ch_idx,
                    "split": split,
                }
            )


def save_segments(seconds: int, all_map: dict):
    seg_points = SAMPLE_RATE * seconds
    root_out = OUTPUT_ROOT
    val_dir = root_out / "stage2data" / "val_inf"
    val_dir.mkdir(parents=True, exist_ok=True)

    val_rows = []
    seg_counts = defaultdict(int)

    for label, paths in sorted(all_map.items(), key=lambda x: x[0]):
        for p in paths:
            slice_and_write(p, label, "val", seg_points, val_dir, val_rows)

    for r in val_rows:
        seg_counts[r["label"]] += 1

    val_csv = root_out / "stage2_val_inf.csv"
    test_csv = root_out / "stage2_test_inf.csv"
    df_val = pd.DataFrame(val_rows)
    df_val.to_csv(val_csv, index=False)
    shutil.copyfile(val_csv, test_csv)

    print(f"\n✅ {seconds}s | 单集样本数（val_inf，验证与测试共用同一索引）: {len(val_rows)}")
    print(f"   索引（主）: {val_csv}")
    print(f"   索引（与上面内容相同，便于 test 配置）: {test_csv}")
    print("📊 各标签切片条数:")
    for label in sorted(seg_counts.keys()):
        print(f"   label={label}: {seg_counts[label]}")


def main():
    if not SRC_DIR.exists():
        raise FileNotFoundError(f"未找到输入目录: {SRC_DIR}")

    files_by_label = defaultdict(list)
    for csv_path in sorted(SRC_DIR.glob("*.csv")):
        try:
            label = parse_label_from_name(csv_path)
        except ValueError as e:
            print(f"⚠️ 跳过：{e}")
            continue
        files_by_label[label].append(csv_path)

    print("📊 stage2inf_test 各标签原始文件数:")
    for label in sorted(files_by_label.keys()):
        print(f"   label={label}: {len(files_by_label[label])} 个文件（将全部用于切片）")

    all_map = assign_all_files(files_by_label)

    print("\n📊 参与切片的文件（每标签全部文件，已排序）:")
    for label in sorted(all_map.keys()):
        names = [p.name for p in all_map[label]]
        print(f"   label={label} | {len(names)} 个: {names}")

    for sec in TARGET_SECONDS:
        save_segments(sec, all_map)

    print("\n🎉 全部完成：仅 5s 切片已写入 5sdata/stage2data/val_inf/。")
    print("   stage2_val_inf.csv 与 stage2_test_inf.csv 内容相同，训练 val 与 teststage2 可共用。")


if __name__ == "__main__":
    main()
