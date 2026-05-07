# 消融实验与基线对比实验指南

## 概述

本文档介绍如何运行消融实验（ablation study）和基线方法对比实验（baseline comparison），以验证两阶段管道泄漏检测与定位方法的各组件有效性。

---

## 一、消融实验

消融实验通过逐一移除或替换模型的关键组件，观察性能变化，从而评估各模块的贡献。

### 1.1 运行命令

```bash
# 对 stage2 运行所有消融实验
leak-ablation --config configs/stage2.yaml --output-dir outputs/ablation --ablation all

# 对 stage1 运行所有消融实验
leak-ablation --config configs/stage1.yaml --output-dir outputs/ablation --ablation all

# 仅运行特定维度
leak-ablation --config configs/stage2.yaml --ablation window channel depth
leak-ablation --config configs/stage1.yaml --ablation loss
```

### 1.2 消融维度

#### (a) 输入信号长度（Window Length）

| 变体 | 采样点数 | 时长（@25600 Hz） |
|------|---------|-----------------|
| win_32000 | 32,000 | 1.25 s |
| win_64000 | 64,000 | 2.5 s |
| win_128000 | 128,000 | 5 s（默认） |
| win_256000 | 256,000 | 10 s |

通过截断信号实现，无需重新准备数据。

#### (b) 输入通道数（Input Channels）

- **Stage2**：单通道（默认）vs 双通道（复制信号为双通道）
- **Stage1**：双通道（默认）vs 单通道（仅用左通道）

检验双传感器信息融合是否带来性能提升。

#### (c) 损失函数（Loss Function，stage1 仅）

- Smooth L1 Loss（默认）
- MSE Loss

比较不同损失函数对回归精度和异常值敏感度的影响。

#### (d) 网络深度（Network Depth）

| 变体 | 通道配置 | 说明 |
|------|---------|------|
| depth_shallow | [16, 32, 64, 128] | 浅层网络 |
| depth_default | [32, 64, 128, 256] | 默认深度 |
| depth_deep | [32, 64, 128, 256, 512] | 深层网络（增加下采样块） |

### 1.3 输出

每个消融变体独立训练并保存到 `outputs/ablation/<task>/<variant>/`，包含：
- `config.yaml`：变体配置
- `checkpoint_best.pth`：最优模型权重
- `logs/`：TensorBoard 日志
- 汇总结果写入 `outputs/ablation/<task>/ablation_results.csv`

### 1.4 结果解读

CSV 文件包含每个变体的测试集指标：
- **Stage2**：test_loss, test_accuracy, test_macro_f1, test_file_accuracy, test_file_macro_f1
- **Stage1**：test_loss, test_mae, test_rmse, test_within_1.0, test_file_mae, test_file_rmse, test_file_within_1.0

对比默认配置与变体配置的指标差异，判断各组件的重要性。

---

## 二、基线方法对比

将传统机器学习方法与本文提出的深度学习方法进行对比。

### 2.1 运行命令

```bash
# Stage2 分类基线
leak-baselines --config configs/stage2.yaml --output-dir outputs/baselines

# Stage1 回归基线
leak-baselines --config configs/stage1.yaml --output-dir outputs/baselines

# 仅运行特定模型
leak-baselines --config configs/stage2.yaml --models svm knn
```

### 2.2 基线方法

| 模型 | Stage2（分类） | Stage1（回归） |
|------|--------------|---------------|
| SVM | SVC (RBF kernel, C=10.0) | SVR (RBF kernel, C=10.0) |
| KNN | KNeighborsClassifier (k=5) | KNeighborsRegressor (k=5) |
| Decision Tree | DecisionTreeClassifier (max_depth=10) | DecisionTreeRegressor (max_depth=10) |

### 2.3 特征提取

对每个段（segment）提取以下特征用于传统模型训练：

**时域特征（11维）：**
- 均值（mean）、标准差（std）、均方根（RMS）
- 峰值（peak）、峰峰值（peak-to-peak）
- 偏度（skewness）、峰度（kurtosis）
- 波峰因子（crest factor）、波形因子（shape factor）、脉冲因子（impulse factor）
- 能量（energy）、过零率（zero-crossing rate）

**频域特征（11维）：**
- 频谱质心（spectral centroid）
- 主频（dominant frequency）
- 频谱滚降点（spectral roll-off 85%）
- 8 个子带能量占比（band energy 0-7）

**双通道：** Stage1 回归任务将左右通道的特征拼接，共 44 维特征。

### 2.4 评估方式

每个模型按两种粒度评估：
- **Segment-level**：直接在段级别预测上计算指标
- **File-level**：段预测聚合成文件级预测（分类：多数投票；回归：均值），再计算指标

### 2.5 输出

- `outputs/baselines/<task>/baseline_results.csv`：所有模型的测试指标
- 可直接与深度神经网络结果对比（在同等测试集上）

---

## 三、可视化脚本

### 3.1 混淆矩阵热力图

```bash
# 从 checkpoint 生成混淆矩阵
leak-plot-cm --checkpoint outputs/stage2/<run>/checkpoint_best.pth \
              --config configs/stage2.yaml

# 指定输出路径和类名
leak-plot-cm --checkpoint outputs/stage2/<run>/checkpoint_best.pth \
              --config configs/stage2.yaml \
              --output figures/cm.png \
              --class-names "正常" "微小泄漏" "严重泄漏" \
              --segment
```

参数说明：
- `--segment`：显示段级（而非文件级）混淆矩阵
- `--no-normalize`：显示原始计数而非归一化比例

### 3.2 训练曲线

```python
# 从 TensorBoard 日志生成训练曲线
leak-plot-curves --log-dir outputs/stage2/<run>/logs \
                  --task stage2

# 自动检测任务类型
leak-plot-curves --log-dir outputs/stage1/<run>/logs
```

生成以下图像：
- **Stage2**：loss_curves.png, accuracy_curves.png, f1_curves.png, lr_curve.png
- **Stage1**：loss_curves.png, mae_curves.png, rmse_within_curves.png, lr_curve.png

### 3.3 误差分布图（Stage1 仅）

```bash
# 从预测 CSV 文件绘制
leak-plot-errors --csv outputs/stage1/<run>/test_stage1_predictions.csv

# 从 checkpoint 重新计算
leak-plot-errors --checkpoint outputs/stage1/<run>/checkpoint_best.pth \
                  --config configs/stage1.yaml
```

生成以下图像：
- `error_histogram.png`：预测误差直方图（含零误差线和平均偏差线）
- `pred_vs_target_scatter.png`：预测值 vs 真实值散点图（含理想线）
- `error_by_distance_boxplot.png`：按距离分组的绝对误差箱线图

---

## 四、完整实验流程建议

```bash
# 1. 训练基线模型
leak-baselines --config configs/stage2.yaml
leak-baselines --config configs/stage1.yaml

# 2. 训练主模型（已在原始流程中完成）
leak-train --config configs/stage2.yaml
leak-train --config configs/stage1.yaml

# 3. 运行消融实验（可能需要较长时间）
leak-ablation --config configs/stage2.yaml --ablation window channel depth
leak-ablation --config configs/stage1.yaml --ablation window channel loss depth

# 4. 生成可视化
leak-plot-cm --checkpoint outputs/stage2/<best_run>/checkpoint_best.pth --config configs/stage2.yaml
leak-plot-curves --log-dir outputs/stage2/<best_run>/logs
leak-plot-errors --checkpoint outputs/stage1/<best_run>/checkpoint_best.pth --config configs/stage1.yaml
```

---

## 五、常见问题

### 训练时间过长

- 消融实验中每个变体独立训练，可在多台机器上并行运行不同的 ablation 维度
- 使用 `--ablation` 参数分批运行，如先运行 `window` 再运行 `depth`

### 基线模型准确率低

- 传统 ML 模型依赖手工特征的质量，可尝试调整特征集
- SVM 的 C 和 gamma 参数、KNN 的 k 值可通过交叉验证调优
- 在 `run_baselines.py` 中修改 `BASELINE_MODELS` 字典中的参数

### 可视化中文显示

如果 matplotlib 图表中的中文显示为方框，需要安装中文字体：

```python
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei', 'Noto Sans CJK SC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
```
