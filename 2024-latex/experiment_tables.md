# Experiment Tables

This file collects the current paper-ready experiment tables. Stage2 has been
updated with the current classification results; Stage1 values should be filled
after the regression run finishes.

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
  \caption{Stage1 回归任务结果}
  \label{tab:stage1_results_final}
  \vspace{0.5em}
  \begin{tabular}{lcc}
    \toprule
    数据划分 & 指标 & 数值 \\
    \midrule
    验证集最优模型 & MAE & -- \\
    测试集 & MAE & -- \\
    测试集 & RMSE & -- \\
    \bottomrule
  \end{tabular}
\end{table}
```

## 4. Main Results Summary

```tex
\begin{table}[!htbp]
  \centering
  \caption{两阶段任务主要实验结果汇总}
  \label{tab:main_results_summary}
  \vspace{0.5em}
  \begin{tabular}{lccc}
    \toprule
    任务 & 测试指标 1 & 测试指标 2 & 备注 \\
    \midrule
    Stage2 分类 & Accuracy = 0.9415 & Macro-F1 = 0.9180 & 文件级 Accuracy = 0.9783 \\
    Stage1 回归 & -- & -- & 双通道距离估计 \\
    \bottomrule
  \end{tabular}
\end{table}
```
