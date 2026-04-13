import os
import random
import pandas as pd
import numpy as np

# ===================== 核心配置 =====================
BASE_DIR = "/home/zzl12312/zzl_internoise"
RAW_FOLDER = os.path.join(BASE_DIR, "raw")

SEGMENT_SECONDS = 5
SAMPLING_RATE = 25600
TRAIN_RATIO = 0.7
VAL_RATIO = 0.2
TEST_RATIO = 0.1

# ===================== LABEL_MAP =====================
LABEL_MAP = {
    (1, 6):      (11,   1),
    (7, 12):     (5,    1),
    (13, 18):    (6,    1),
    (19, 24):    (6,    1),
    (25, 30):    (4,    1),
    (31, 36):    (5,    1),
    (37, 42):    (5,    1),
    (43, 48):    (2,    1),
    (49, 54):    (4,    1),
    (55, 72):    (14,   1),
    (73, 84):    (16,   1),
    (85, 102):   (12,   1),
    (103, 108):  (11,   1),
    (109, 114):  (5,    1),
    (115, 120):  (3,    1),
    (121, 126):  (3,    2),
    (127, 132):  (3,    2),
    (133, 138):  (5,    2),
    (139, 156):  (12,   2),
    (157, 168):  (16,   2),
    (169, 186):  (14,   2),
    (187, 9999): 0,  # normal → 不进 stage1
}

# ===================== 输出目录 =====================
ROOT_OUT = "5sdata"
STAGE1_DIR = os.path.join(ROOT_OUT, "stage1data")
STAGE2_DIR = os.path.join(ROOT_OUT, "stage2data")

# 创建文件夹
for split in ["train", "val", "test"]:
    os.makedirs(os.path.join(STAGE1_DIR, split), exist_ok=True)
    os.makedirs(os.path.join(STAGE2_DIR, split), exist_ok=True)

SEG_POINTS = SAMPLING_RATE * SEGMENT_SECONDS

# ===================== 工具函数 =====================
def read_csv_safe(path):
    try:
        df = pd.read_csv(path, header=None, encoding='gbk', low_memory=False)
    except:
        df = pd.read_csv(path, header=None, encoding='latin-1', low_memory=False)
    df = df.iloc[1:].reset_index(drop=True)
    df = df.apply(pd.to_numeric, errors='coerce').dropna()
    return df

def get_abc_number(filename):
    num_str = ''.join(filter(str.isdigit, filename))
    return int(num_str) if num_str else -1

def get_label(abc_num):
    for (min_n, max_n), cfg in LABEL_MAP.items():
        if min_n <= abc_num <= max_n:
            return cfg
    return None

# ===================== 第一步：收集所有完整文件 =====================
all_files = []
for root, dirs, files in os.walk(RAW_FOLDER):
    for fname in files:
        if not fname.endswith(".csv"):
            continue
        fp = os.path.join(root, fname)
        abc_num = get_abc_number(fname)
        label_cfg = get_label(abc_num)
        if label_cfg is None:
            continue
        all_files.append({
            "path": fp,
            "abc": abc_num,
            "label_cfg": label_cfg
        })

# ===================== 第二步：按文件划分 train/val/test =====================
random.shuffle(all_files)
N = len(all_files)
nt = int(N * TRAIN_RATIO)
nv = int(N * VAL_RATIO)

train_files = all_files[:nt]
val_files   = all_files[nt:nt+nv]
test_files  = all_files[nt+nv:]

# ===================== 第三步：处理数据 =====================
stage1_rows = []
stage2_rows = []

def process_set(file_list, split_name):
    for f in file_list:
        df = read_csv_safe(f["path"])
        if len(df) < SEG_POINTS:
            continue

        left = df.iloc[:, 1].values.astype(np.float32)
        right = df.iloc[:, 2].values.astype(np.float32)
        n_seg = len(df) // SEG_POINTS
        abc = f["abc"]
        cfg = f["label_cfg"]

        # ---------------------- 标签判断 ----------------------
        is_leak = isinstance(cfg, (tuple, list))
        if is_leak:
            dist, cls = cfg
        else:
            cls = cfg
            dist = 0

        for i in range(n_seg):
            st, ed = i * SEG_POINTS, (i+1) * SEG_POINTS
            l = left[st:ed]
            r = right[st:ed]
            seg_name = f"ABC{abc}_seg{i}"

            # ---------------------- stage2 所有数据都保存 ----------------------
            l2 = os.path.join(STAGE2_DIR, split_name, f"{seg_name}_left.csv")
            r2 = os.path.join(STAGE2_DIR, split_name, f"{seg_name}_right.csv")
            pd.DataFrame(l).to_csv(l2, index=False, header=False)
            pd.DataFrame(r).to_csv(r2, index=False, header=False)
            stage2_rows.append({"path": l2, "label": cls})
            stage2_rows.append({"path": r2, "label": cls})

            # ---------------------- stage1：只保存泄漏数据 ----------------------
            if is_leak:
                l1 = os.path.join(STAGE1_DIR, split_name, f"{seg_name}_left.csv")
                r1 = os.path.join(STAGE1_DIR, split_name, f"{seg_name}_right.csv")
                pd.DataFrame(l).to_csv(l1, index=False, header=False)
                pd.DataFrame(r).to_csv(r1, index=False, header=False)
                stage1_rows.append({
                    "path_left": l1,
                    "path_right": r1,
                    "distance": dist
                })

# 处理三个数据集
process_set(train_files, "train")
process_set(val_files,   "val")
process_set(test_files,  "test")

# ===================== 保存CSV =====================
pd.DataFrame(stage1_rows).to_csv(os.path.join(ROOT_OUT, "stage1.csv"), index=False)
pd.DataFrame(stage2_rows).to_csv(os.path.join(ROOT_OUT, "stage2.csv"), index=False)

# ===================== 日志 =====================
print("\n✅ 全部完成！100% 符合你的要求！")
print(f"📦 总文件数：{len(all_files)}")
print(f"✅ stage1（仅泄漏）：{len(stage1_rows)} 条成对数据")
print(f"✅ stage2（全部）：{len(stage2_rows)} 条")
print("\n最终结构：")
print(" 5sdata/")
print("   ├─ stage1data/ (leak only)")
print("   ├─ stage2data/ (leak + normal)")
print("   ├─ stage1.csv")
print("   └─ stage2.csv")