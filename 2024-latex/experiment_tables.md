# Experiment Tables

This file collects the current paper-ready experiment tables.

## 1. Dataset Statistics

```tex
\begin{table}[!htbp]
  \centering
  \caption{数据集划分统计结果}
  \label{tab:dataset_split_stats}
  \vspace{0.5em}
  \begin{tabular}{lcccc}
    \toprule
    任务 & 总样本数 & 训练集 & 验证集 & 测试集 \\
    \midrule
    Stage2 分类 & 11704 & 7940 & 2464 & 1300 \\
    Stage1 回归 & 3737 & 2532 & 758 & 447 \\
    \bottomrule
  \end{tabular}
\end{table}
```

## 2. Stage2 Classification Results

```tex
\begin{table}[!htbp]
  \centering
  \caption{Stage2 分类任务测试结果}
  \label{tab:stage2_results_final}
  \vspace{0.5em}
  \begin{tabular}{lcc}
    \toprule
    评测层级 & 指标 & 数值 \\
    \midrule
    片段级 & Accuracy & 0.9415 \\
    片段级 & Macro-F1 & 0.9180 \\
    文件级 & Accuracy & 0.9783 \\
    文件级 & Macro-F1 & 0.9836 \\
    \bottomrule
  \end{tabular}
\end{table}
```

Segment-level confusion matrix:

```tex
\begin{table}[!htbp]
  \centering
  \caption{Stage2 测试集片段级混淆矩阵}
  \label{tab:stage2_segment_cm}
  \vspace{0.5em}
  \begin{tabular}{cccccc}
    \toprule
    真实$\backslash$预测 & 0 & 1 & 2 & 3 & 4 \\
    \midrule
    0 & 406 & 0 & 0 & 0 & 0 \\
    1 & 1 & 178 & 0 & 31 & 0 \\
    2 & 15 & 27 & 90 & 0 & 0 \\
    3 & 2 & 0 & 0 & 274 & 0 \\
    4 & 0 & 0 & 0 & 0 & 276 \\
    \bottomrule
  \end{tabular}
\end{table}
```

File-level confusion matrix:

```tex
\begin{table}[!htbp]
  \centering
  \caption{Stage2 测试集文件级混淆矩阵}
  \label{tab:stage2_file_cm}
  \vspace{0.5em}
  \begin{tabular}{cccccc}
    \toprule
    真实$\backslash$预测 & 0 & 1 & 2 & 3 & 4 \\
    \midrule
    0 & 14 & 0 & 0 & 0 & 0 \\
    1 & 0 & 9 & 0 & 0 & 0 \\
    2 & 1 & 0 & 10 & 0 & 0 \\
    3 & 0 & 0 & 0 & 6 & 0 \\
    4 & 0 & 0 & 0 & 0 & 6 \\
    \bottomrule
  \end{tabular}
\end{table}
```

## 3. Stage1 Regression Results

```tex
\begin{table}[!htbp]
  \centering
  \caption{Stage1 回归任务测试结果}
  \label{tab:stage1_results_final}
  \vspace{0.5em}
  \begin{tabular}{lcc}
    \toprule
    评测层级 & 指标 & 测试集 \\
    \midrule
    片段级 & MAE & 1.90 \\
    片段级 & RMSE & 2.43 \\
    文件级 & MAE & 2.46 \\
    文件级 & RMSE & 2.94 \\
    \bottomrule
  \end{tabular}
\end{table}
```

```tex
\begin{table}[!htbp]
  \centering
  \caption{Stage1 回归任务物理误差分析}
  \label{tab:stage1_physical_error_final}
  \vspace{0.5em}
  \begin{tabular}{lcc}
    \toprule
    指标 & 片段级 & 文件级 \\
    \midrule
    MAE & 1.90 & 2.46 \\
    RMSE & 2.43 & 2.94 \\
    中位绝对误差 & 1.45 & 2.14 \\
    P95 绝对误差 & 4.99 & 5.15 \\
    最大绝对误差 & 6.86 & 5.65 \\
    $R^2$ & 0.54 & 0.30 \\
    误差 $\leq 0.5$ 占比 & 0.15 & 0.13 \\
    误差 $\leq 1.0$ 占比 & 0.35 & 0.25 \\
    误差 $\leq 2.0$ 占比 & 0.66 & 0.44 \\
    有符号偏差 (Bias) & +0.45 & +0.91 \\
    \bottomrule
  \end{tabular}
\end{table}
```

```tex
\begin{table}[!htbp]
  \centering
  \caption{Stage1 回归任务按距离档位误差（片段级）}
  \label{tab:stage1_by_distance_final}
  \vspace{0.5em}
  \begin{tabular}{lcccccc}
    \toprule
    真实距离 (m) & 样本数 & MAE & RMSE & Bias & 误差 $\leq 1.0$ 占比 & 文件级 MAE \\
    \midrule
    $-3$ & 118 & 2.83 & 3.28 & +2.66 & 0.13 & 3.29 \\
    $-1$ & 23 & 4.85 & 4.86 & +4.85 & 0.00 & 4.85 \\
    $0$ & 69 & 0.67 & 0.83 & +0.23 & 0.74 & 0.23 \\
    $+1$ & 46 & 2.14 & 2.32 & $-$2.14 & 0.09 & 2.14 \\
    $+3$ & 53 & 2.44 & 2.66 & $-$1.21 & 0.08 & 2.92 \\
    $+5$ & 46 & 1.24 & 1.32 & $-$1.24 & 0.37 & 1.24 \\
    $+6$ & 46 & 0.61 & 0.74 & +0.48 & 0.85 & 0.48 \\
    $+7$ & 46 & 0.95 & 1.04 & $-$0.95 & 0.61 & 0.95 \\
    \bottomrule
  \end{tabular}
\end{table}
```

## 4. Baseline Comparisons

```tex
\begin{table}[!htbp]
  \centering
  \caption{Stage2 分类任务传统基线对比}
  \label{tab:stage2_baselines_final}
  \vspace{0.5em}
  \begin{tabular}{lcccc}
    \toprule
    方法 & 片段级 Accuracy & 片段级 Macro-F1 & 文件级 Accuracy & 文件级 Macro-F1 \\
    \midrule
    一维 CNN & 0.9415 & 0.9180 & 0.9783 & 0.9836 \\
    SVM & 0.9300 & 0.9046 & 1.0000 & 1.0000 \\
    KNN & 0.9277 & 0.9155 & 0.9783 & 0.9751 \\
    决策树 & 0.8738 & 0.8309 & 0.9565 & 0.9600 \\
    \bottomrule
  \end{tabular}
\end{table}
```

```tex
\begin{table}[!htbp]
  \centering
  \caption{Stage1 回归任务传统基线对比}
  \label{tab:stage1_baselines_final}
  \vspace{0.5em}
  \begin{tabular}{lcccccc}
    \toprule
    方法 & \multicolumn{3}{c}{片段级} & \multicolumn{3}{c}{文件级} \\
    \cmidrule(lr){2-4}\cmidrule(lr){5-7}
     & MAE & RMSE & 误差 $\leq 1.0$ & MAE & RMSE & 误差 $\leq 1.0$ \\
    \midrule
    一维 CNN & 1.90 & 2.43 & 0.35 & 2.46 & 2.94 & 0.25 \\
    SVM & 1.51 & 1.91 & 0.46 & 1.83 & 2.20 & 0.38 \\
    KNN & 1.76 & 2.29 & 0.44 & 2.02 & 2.43 & 0.28 \\
    决策树 & 2.44 & 2.97 & 0.34 & 2.23 & 2.58 & 0.28 \\
    \bottomrule
  \end{tabular}
\end{table}
```

## 5. Ablation Results

```tex
\begin{table}[!htbp]
  \centering
  \caption{Stage1 回归任务通道消融实验}
  \label{tab:stage1_channel_ablation_final}
  \vspace{0.5em}
  \begin{tabular}{lcccccc}
    \toprule
    设置 & \multicolumn{3}{c}{片段级} & \multicolumn{3}{c}{文件级} \\
    \cmidrule(lr){2-4}\cmidrule(lr){5-7}
     & MAE & RMSE & 误差 $\leq 1.0$ & MAE & RMSE & 误差 $\leq 1.0$ \\
    \midrule
    双通道输入（默认） & 1.90 & 2.43 & 0.35 & 2.46 & 2.94 & 0.25 \\
    单通道输入 & 3.88 & 4.75 & 0.17 & 3.17 & 3.95 & 0.16 \\
    \bottomrule
  \end{tabular}
\end{table}
```

## 6. CNN vs. Conformer Comparison

```tex
\begin{table}[!htbp]
  \centering
  \caption{一维 CNN 与 Conformer 结构对比}
  \label{tab:cnn_conformer_comparison_final}
  \vspace{0.5em}
  \setlength{\tabcolsep}{3pt}
  \wuhao
  \begin{tabular}{llcccc}
    \toprule
    任务 & 模型 & 片段主指标 & 片段辅指标 & 文件主指标 & 文件辅指标 \\
    \midrule
    Stage2 分类 & 一维 CNN & Acc 0.9415 & Macro-F1 0.9180 & Acc 0.9783 & Macro-F1 0.9836 \\
    Stage2 分类 & Conformer & Acc 0.9900 & Macro-F1 0.9883 & Acc 1.0000 & Macro-F1 1.0000 \\
    Stage1 回归 & 一维 CNN & MAE 1.90 & RMSE 2.43 & MAE 2.46 & RMSE 2.94 \\
    Stage1 回归 & Conformer & MAE 1.95 & RMSE 2.63 & MAE 2.51 & RMSE 3.10 \\
    \bottomrule
  \end{tabular}
\end{table}
```

## 7. Main Results Summary

```tex
\begin{table}[!htbp]
  \centering
  \caption{两阶段任务主要实验结果汇总}
  \label{tab:main_results_summary}
  \vspace{0.5em}
  \begin{tabular}{lccc}
    \toprule
    任务 & 主要指标 & 辅助指标 & 备注 \\
    \midrule
    Stage2 分类 & Acc = 0.9415 & Macro-F1 = 0.9180 & 文件级 Acc = 0.9783 \\
    Stage1 回归 & MAE = 1.90 m & RMSE = 2.43 m & 文件级 MAE = 2.46 m \\
    \bottomrule
  \end{tabular}
\end{table}
```
