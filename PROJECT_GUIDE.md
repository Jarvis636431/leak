# 管道泄漏音频识别系统

基于 Conformer 模型的多任务音频识别系统，用于检测管道泄漏、估计泄漏距离和识别泄漏形状。

## 项目结构

```
.
├── configs/
│   └── config.yaml          # 配置文件
├── data/
│   ├── audio/               # 音频文件
│   │   ├── train/
│   │   ├── val/
│   │   └── test/
│   └── annotations/         # 标注文件
│       ├── train.csv
│       ├── val.csv
│       └── test.csv
├── src/
│   └── leak_detection/
│       ├── cli/
│       │   ├── train.py             # 训练入口
│       │   ├── evaluate.py          # 评估入口
│       │   ├── inference.py         # 推理入口
│       │   └── prepare_dataset.py   # 数据切分与标注生成
│       ├── models/
│       │   └── conformer.py         # Conformer 模型实现
│       ├── data/
│       │   └── dataset.py           # 数据集和数据加载
│       └── utils/
│           ├── helpers.py           # 工具函数
│           └── runtime.py           # 配置和设备解析
├── notebooks/
│   └── quickstart.ipynb     # 快速入门教程
├── outputs/
│   ├── checkpoints/         # 模型检查点
│   ├── logs/                # 训练日志
│   └── results/             # 评估结果
├── pyproject.toml           # 项目配置
└── README.md                # 项目说明

```

## 环境配置

### 1. 创建虚拟环境

```bash
# 使用 uv（推荐）
uv venv --python 3.12
source .venv/bin/activate

# 或使用 conda
conda create -n leak python=3.12
conda activate leak
```

### 2. 安装依赖

```bash
# 使用 uv
uv pip install -e .

# 或使用 pip
pip install -e .
```

### 3. 安装 PyTorch

```bash
# Mac M1/M2/M3 (MPS 加速)
uv pip install torch torchvision torchaudio

# Linux/Windows (CUDA)
uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

## 数据准备

### 数据格式

#### 音频文件
- 格式：`.wav`, `.mp3`, `.flac`
- 建议采样率：16kHz
- 建议时长：3-5 秒

#### 标注文件 (CSV)

```csv
filename,has_leak,distance,shape
audio_001.wav,1,25.5,0
audio_002.wav,0,0.0,0
audio_003.wav,1,42.0,2
...
```

字段说明：
- `filename`: 音频文件名
- `has_leak`: 是否有泄漏（0=无，1=有）
- `distance`: 泄漏距离（米）
- `shape`: 泄漏形状类别（0-4）

### 数据目录结构

```bash
mkdir -p data/audio/{train,val,test}
mkdir -p data/annotations

# 放置你的音频文件
cp your_audio_files/*.wav data/audio/train/
cp your_audio_files/*.wav data/audio/val/
cp your_audio_files/*.wav data/audio/test/

# 放置标注文件
cp train.csv data/annotations/
cp val.csv data/annotations/
cp test.csv data/annotations/
```

## 训练模型

### 基本用法

```bash
leak-train --config configs/config.yaml
```

### 高级选项

```bash
# 指定输出目录
leak-train --config configs/config.yaml --output-dir outputs/experiment_1

# 从检查点恢复训练
leak-train --config configs/config.yaml --resume outputs/checkpoint_last.pth
```

### 监控训练

```bash
# 启动 TensorBoard
tensorboard --logdir outputs/logs

# 在浏览器中打开 http://localhost:6006
```

## 评估模型

```bash
leak-evaluate \
    --config configs/config.yaml \
    --checkpoint outputs/checkpoint_best.pth \
    --output-dir outputs/evaluation
```

评估结果将包括：
- 混淆矩阵
- 准确率、精确率、召回率、F1 分数
- 距离估计的 MAE、RMSE、MAPE
- 预测结果 CSV 文件

## 推理

### 单文件推理

```bash
leak-inference \
    --audio path/to/audio.wav \
    --checkpoint outputs/checkpoint_best.pth \
    --shape-labels Circle Crack Corrosion Hole Other
```

输出示例：
```
==================================================
PREDICTION RESULTS
==================================================

1. Leak Detection:
   Status: LEAK DETECTED
   Confidence: 95.23%

2. Distance Estimation:
   Estimated Distance: 32.45 meters

3. Leak Shape Classification:
   Predicted Shape: Crack

   Shape Probabilities:
      Circle: 2.14%
      Crack: 87.35%
      Corrosion: 5.21%
      Hole: 3.45%
      Other: 1.85%
```

## 模型配置

编辑 `configs/config.yaml` 来调整模型和训练参数：

### Conformer 模型参数

```yaml
model:
  d_model: 256        # 模型维度（128, 256, 512）
  num_layers: 4       # Conformer block 层数
  num_heads: 8        # 注意力头数
  d_ff: 1024          # Feed-forward 维度
  kernel_size: 31     # 卷积核大小
  dropout: 0.1        # Dropout 率
```

### 训练参数

```yaml
training:
  epochs: 100
  batch_size: 16
  learning_rate: 0.0001
  scheduler: "cosine"  # 学习率调度器
```

## 性能优化建议

1. **数据增强**：使用 SpecAugment（已在代码中实现）
2. **学习率**：Conformer 通常需要较小的学习率（1e-4 到 5e-4）
3. **Batch Size**：根据 GPU 内存调整，建议 8-32
4. **模型大小**：
   - 小模型：`d_model=128, num_layers=4` (~3M 参数)
   - 中模型：`d_model=256, num_layers=6` (~9M 参数)
   - 大模型：`d_model=512, num_layers=12` (~35M 参数)

## 常见问题

### Q: 显存不足怎么办？
A: 减小 `batch_size` 或 `d_model`

### Q: 训练 loss 不下降？
A: 
- 检查学习率是否过大
- 检查数据是否正确加载
- 尝试预训练权重

### Q: 如何调整多任务权重？
A: 修改 `config.yaml` 中的 `loss_weights`：
```yaml
loss_weights:
  detection: 1.0    # 泄漏检测权重
  distance: 0.5     # 距离估计权重
  shape: 0.8        # 形状分类权重
```

## 引用

如果使用了本项目，请引用 Conformer 论文：

```bibtex
@article{gulati2020conformer,
  title={Conformer: Convolution-augmented Transformer for Speech Recognition},
  author={Gulati, Anmol and Qin, James and Chiu, Chung-Cheng and Parmar, Niki and Yu, Jiahui and Zhang, Wei and Han, Khe and Wang, Shibo and Zhang, Zhengdong and Wu, Yonghui and Pang, Ruoming},
  journal={arXiv preprint arXiv:2005.08100},
  year={2020}
}
```

## License

MIT License
