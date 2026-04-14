# 管道泄漏训练指南

这个项目当前采用两阶段训练流程，直接消费 `prepare_dataset` 生成的分段 CSV 数据。

## 当前任务定义

### Stage2

- 输入：`artifacts/5sdata/stage2.csv`
- 单条样本：一个单通道分段 CSV
- 标签：`label`
- 任务：3 分类

### Stage1

- 输入：`artifacts/5sdata/stage1.csv`
- 单条样本：一对左右通道分段 CSV
- 标签：`distance`
- 任务：距离回归

## 项目结构

```text
.
├── configs/
│   ├── stage1.yaml
│   └── stage2.yaml
├── raw/
│   ├── leak/
│   └── normal/
├── artifacts/5sdata/
│   ├── stage1.csv
│   ├── stage2.csv
│   ├── stage1data/
│   └── stage2data/
├── src/leak_detection/
│   ├── cli/
│   │   ├── prepare_dataset.py
│   │   └── train.py
│   ├── data/
│   │   └── segmented.py
│   ├── models/
│   │   └── signal_models.py
│   ├── training/
│   │   └── trainer.py
│   └── utils/
└── outputs/
```

## 环境配置

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install .
```

## 数据准备

原始数据目录约定：

```text
raw/
├── leak/
│   ├── ABC1.csv
│   ├── ABC2.csv
│   └── ...
└── normal/
    ├── ABC187.csv
    └── ...
```

执行数据切分：

```bash
leak-prepare-dataset --raw-dir raw --output-dir artifacts/5sdata
```

完成后会生成：

```text
artifacts/5sdata/
├── stage1.csv
├── stage2.csv
├── stage1data/{train,val,test}/*.csv
└── stage2data/{train,val,test}/*.csv
```

## 训练

### Stage2 分类

```bash
leak-train --config configs/stage2.yaml
```

### Stage1 回归

```bash
leak-train --config configs/stage1.yaml
```

### 指定输出目录

```bash
leak-train --config configs/stage2.yaml --output-dir outputs/custom_stage2_run
```

### 从 checkpoint 恢复

```bash
leak-train --config configs/stage1.yaml --resume outputs/stage1/YYYYMMDD_HHMMSS/checkpoint_last.pth
```

## 配置说明

### `configs/stage2.yaml`

- `data.manifest`: `stage2.csv` 路径
- `model.num_classes`: 分类类别数
- `training.batch_size`: 分类任务 batch size

### `configs/stage1.yaml`

- `data.manifest`: `stage1.csv` 路径
- `training.regression_loss`: 回归损失，当前支持 `smooth_l1` 或 `mse`
- `training.batch_size`: 回归任务 batch size

## 输出内容

每次训练会生成：

- `checkpoint_last.pth`
- `checkpoint_best.pth`
- `logs/` TensorBoard 日志

训练结束后会自动加载最佳 checkpoint，并在 test split 上输出最终指标。

## 当前实现说明

- 旧的音频推理、Conformer、多任务联合训练已经移除
- 训练模型现在是面向长序列分段 CSV 的 1D CNN
- 如果修改了 `pyproject.toml` 或 CLI 脚本入口，需要重新执行：

```bash
uv pip install .
```
