import os
import random
import pandas as pd
import numpy as np

# ===================== 核心配置 =====================
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.environ.get("INTERNOISE_BASE_DIR", os.path.join(REPO_DIR, "internoisedata"))
RAW_FOLDER = os.path.join(BASE_DIR, "raw")

SEGMENT_SECONDS = 5
SAMPLING_RATE = 25600
TRAIN_RATIO = 0.8
VAL_RATIO = 0.1
TEST_RATIO = 0.1
SEED = 42
random.seed(SEED)

# ===================== LABEL_MAP =====================
LABEL_MAP = {
    (301, 306): (3, 1),
    (307, 312): (-2, 1),
    (313, 318): (1, 1),
    (319, 324): (-6, 1),
    (325, 330): (-4, 1),
    (331, 336): (-4, 1),
    (337, 342): (0, 1),
    (343, 348): (-3, 1),
    (349, 354): (-10, 1),
    (355, 360): (0, 1),
    (361,366):(-2,1),
    (367,372):(-5,1),
    (373, 378): (-3, 1),
    (379,384):(3,1),
    (385, 390): (-1, 1),
    (391, 396): (3, 1),
    (397, 402): (6, 1),
    (403, 408): (6, 1),
    (409, 414): (0, 1),
    (415, 420): (-3, 1),
    (421, 426): (-3, 2),
    (427, 432): (0, 2),
    (433, 438): (6, 2),
    (439, 444): (6, 2),
    (445, 450): (3, 2),
    (451, 456): (-1, 2),
    (457, 462): (3, 2),
    (463, 468): (-3, 2),
    (469, 474): (-5, 2),
    (475, 480): (-2, 2),
    (481, 486): (0, 2),

    (487, 551): 0,

    (1, 1): (-3, 1),
    (2, 2): (-2, 1),
    (3, 3): (-1, 1),
    (4, 4): (0, 1),
    (5, 5): (1, 1),
    (6, 6): (2, 1),
    (7, 7): (3, 1),
    (8, 8): (4, 1),
    (9, 9): (5, 1),
    (10, 10): (6, 1),
    (11, 11): (1, 1),
    (12, 12): (0, 1),
    (13, 13): (0, 1),
    (14, 14): (6, 1),
    (15, 15): (8, 1),

    (91, 92): (-3, 3),
    (93, 94): (-3, 3),
    (95, 96): (1, 3),
    (97, 98): (-2, 3),
    (99, 100): (-3, 3),
    (101, 102): (5, 3),
    (103, 104): (2, 3),
    (105, 106): (4, 3),
    (107, 108): (0, 3),
    (109, 110): (-7, 3),
    (111, 112): (-2, 3),
    (113, 114): (-4, 3),
    (115, 116): (0, 3),
    (117, 118): (7, 3),
    (119, 120): (4, 3),
    (121, 122): (2, 3),
    (123, 124): (0, 3),
    (125, 126): (6, 3),
    (127, 128): (8, 3),
    (129, 130): (5, 3),
    (131, 132): (7, 3),
    (133, 134): (9, 3),
    (135, 136): (7, 3),
    (137, 138): (3, 3),
    (139, 140): (-10, 3),


    (141, 142): (-2,4),
    (143, 144): (-1,4),
    (145, 146): (-1,4),
    (147, 148): (0,4),
    (149, 150): (1,4),
    (151, 152): (2,4),
    (153, 154): (2,4),
    (155, 156): (1,4),
    (157, 158): (2,4),
    (159, 160): (5,4),
    (161, 162): (6,4),
    (163, 164): (5,4),
    (165, 166): (6,4),
    (167, 168): (7,4),
    (169, 170): (6,4),
    (171, 172): (4,4),
    (173, 174): (5,4),
    (175, 176): (10,4),
    (177, 178): (11,4),
    (179, 180): (5,4),
    (181, 182): (-4,4),
    (183, 184): (-3,4),
    (185, 186): (-7,4),
    (187, 188): (-4,4),
    (189, 190): (-3,4),


    (16, 90): 0,
}
# ===================== 输出目录 =====================
ROOT_OUT = os.environ.get("INTERNOISE_OUTPUT_DIR", os.path.join("artifacts", "internoise_5sdata"))
STAGE1_DIR = os.path.join(ROOT_OUT, "stage1data")
STAGE2_DIR = os.path.join(ROOT_OUT, "stage2data")

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

def get_group_and_cfg(abc_num):
    for (min_n, max_n), cfg in LABEL_MAP.items():
        if min_n <= abc_num <= max_n:
            return (min_n, max_n), cfg
    return None, None

# ===================== 扫描所有文件 =====================
leak_groups = {}
normal_files = []

for root, dirs, files in os.walk(RAW_FOLDER):
    for fname in files:
        if not fname.endswith(".csv"):
            continue
        fp = os.path.join(root, fname)
        abc_num = get_abc_number(fname)
        gk, cfg = get_group_and_cfg(abc_num)
        if gk is None:
            continue
        item = {"path": fp, "abc": abc_num, "cfg": cfg}
        if cfg == 0:
            normal_files.append(item)
        else:
            if gk not in leak_groups:
                leak_groups[gk] = []
            leak_groups[gk].append(item)

# ===================== 按 label 分组 =====================
from collections import defaultdict
label_groups = defaultdict(list)
for gk, items in leak_groups.items():
    cls = items[0]["cfg"][1]
    label_groups[cls].append(gk)

# ===================== 自动划分：少样本特殊处理 =====================
train_g = set()
val_g = set()
test_g = set()

for cls, groups in label_groups.items():
    random.shuffle(groups)
    total = len(groups)

    if total < 10:
        # 少样本：强制 1 val + 1 test，其余 train
        if total >= 1:
            val_g.add(groups[0])
        if total >= 2:
            test_g.add(groups[1])
        for g in groups[2:]:
            train_g.add(g)
        print(f"📦 类别 {cls} 共 {total} 组 → 少样本模式：1val 1test")
    else:
        # 多样本：正常 7:2:1
        nt = int(total * 0.7)
        nv = int(total * 0.2)
        for g in groups[:nt]: train_g.add(g)
        for g in groups[nt:nt+nv]: val_g.add(g)
        for g in groups[nt+nv:]: test_g.add(g)
        print(f"📦 类别 {cls} 共 {total} 组 → 正常比例划分")

# 正常数据随机划分
random.shuffle(normal_files)
n_norm = len(normal_files)
nt_norm = int(n_norm * 0.7)
nv_norm = int(n_norm * 0.2)

def get_split_group(gk):
    if gk in train_g: return "train"
    if gk in val_g: return "val"
    if gk in test_g: return "test"
    return "train"

def get_split_normal(idx):
    if idx < nt_norm: return "train"
    if idx < nt_norm + nv_norm: return "val"
    return "test"

# ===================== 处理数据 =====================
s1_train, s1_val, s1_test = [], [], []
# Stage2：与 Stage1 同一划分；每段写左/右各一条 CSV，标签为 0–4（泄漏 cfg[1]，正常为 0）
s2_train, s2_val, s2_test = [], [], []

def process_item(item, split_name):
    df = read_csv_safe(item["path"])
    if len(df) < SEG_POINTS:
        return
    l_sig = df.iloc[:,1].values.astype(np.float32)
    r_sig = df.iloc[:,2].values.astype(np.float32)
    n_seg = len(df) // SEG_POINTS
    abc = item["abc"]
    cfg = item["cfg"]
    is_leak = isinstance(cfg, tuple)
    cls = cfg[1] if is_leak else 0
    dist = cfg[0] if is_leak else 0

    for i in range(n_seg):
        st, ed = i*SEG_POINTS, (i+1)*SEG_POINTS
        l = l_sig[st:ed]
        r = r_sig[st:ed]
        seg = f"ABC{abc}_seg{i}"

        l2 = os.path.join(STAGE2_DIR, split_name, f"{seg}_left.csv")
        r2 = os.path.join(STAGE2_DIR, split_name, f"{seg}_right.csv")
        pd.DataFrame(l).to_csv(l2, index=False, header=False)
        pd.DataFrame(r).to_csv(r2, index=False, header=False)
        r2l = {"path": l2, "label": cls, "split": split_name}
        r2r = {"path": r2, "label": cls, "split": split_name}

        r1 = None
        if is_leak:
            l1 = os.path.join(STAGE1_DIR, split_name, f"{seg}_left.csv")
            r1 = os.path.join(STAGE1_DIR, split_name, f"{seg}_right.csv")
            pd.DataFrame(l).to_csv(l1, index=False, header=False)
            pd.DataFrame(r).to_csv(r1, index=False, header=False)
            r1 = {"path_left": l1, "path_right": r1, "distance": dist, "split": split_name}

        if split_name == "train":
            s2_train.append(r2l)
            s2_train.append(r2r)
            if r1:
                s1_train.append(r1)
        elif split_name == "val":
            s2_val.append(r2l)
            s2_val.append(r2r)
            if r1:
                s1_val.append(r1)
        else:
            s2_test.append(r2l)
            s2_test.append(r2r)
            if r1:
                s1_test.append(r1)

# 执行处理
for gk, items in leak_groups.items():
    sp = get_split_group(gk)
    for it in items:
        process_item(it, sp)

for idx, it in enumerate(normal_files):
    process_item(it, get_split_normal(idx))

# ===================== 保存 =====================
def save_list(data, path):
    if data:
        pd.DataFrame(data).to_csv(path, index=False)

save_list(s1_train, f"{ROOT_OUT}/stage1_train.csv")
save_list(s1_val, f"{ROOT_OUT}/stage1_val.csv")
save_list(s1_test, f"{ROOT_OUT}/stage1_test.csv")
save_list(s2_train, f"{ROOT_OUT}/stage2_train.csv")
save_list(s2_val, f"{ROOT_OUT}/stage2_val.csv")
save_list(s2_test, f"{ROOT_OUT}/stage2_test.csv")
save_list(s1_train + s1_val + s1_test, f"{ROOT_OUT}/stage1.csv")
save_list(s2_train + s2_val + s2_test, f"{ROOT_OUT}/stage2.csv")

# ===================== 日志 =====================
print("\n" + "="*60)
print("✅ 数据集生成完成！所有类别已确保 val / test 各至少1条！")
print(f"训练集 stage1：{len(s1_train)}")
print(f"验证集 stage1：{len(s1_val)}")
print(f"测试集 stage1：{len(s1_test)}")
print(f"训练集 stage2（左+右各一条）：{len(s2_train)}")
print(f"验证集 stage2：{len(s2_val)}")
print(f"测试集 stage2：{len(s2_test)}")
print("ℹ️  Stage2 使用 5 分类时：config 设 num_classes=5，train.val_csv 可用本目录下 stage2_val.csv；")
print("    若仍要用长音频 inf 验证集，可另运行 data/build_stage2inf_testsets.py 并改 val_csv。")
print("="*60)
