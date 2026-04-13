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
    (187, 9999): 0,  # normal
}

# ===================== 创建目录 =====================
os.makedirs("data_stage1/train", exist_ok=True)
os.makedirs("data_stage1/val", exist_ok=True)
os.makedirs("data_stage1/test", exist_ok=True)

os.makedirs("data_stage2/train", exist_ok=True)
os.makedirs("data_stage2/val", exist_ok=True)
os.makedirs("data_stage2/test", exist_ok=True)

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
            return
