# Experiment Tables

This file collects the current paper-ready tables in LaTeX form so they can be pasted into `include/body.tex` or migrated later into the 2026 Word template.

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
    Stage2 分类 & 3024 & 2112 & 600 & 312 \\
    Stage1 回归 & 1122 & 768 & 228 & 126 \\
    \bottomrule
  \end{tabular}
\end{table}
```

Optional class-distribution table for Stage2:

```tex
\begin{table}[!htbp]
  \centering
  \caption{Stage2 分类任务类别分布}
  \label{tab:stage2_label_dist}
  \vspace{0.5em}
  \begin{tabular}{lccc}
    \toprule
    类别 0 & 类别 1 & 类别 2 & 总计 \\
    \midrule
    780 & 1440 & 804 & 3024 \\
    \bottomrule
  \end{tabular}
\end{table}
```

Optional distance-distribution table for Stage1:

```tex
\begin{table}[!htbp]
  \centering
  \caption{Stage1 回归任务距离分布}
  \label{tab:stage1_distance_dist}
  \vspace{0.5em}
  \begin{tabular}{lccccccccc}
    \toprule
    距离 & 2 & 3 & 4 & 5 & 6 & 11 & 12 & 14 & 16 \\
    \midrule
    样本数 & 36 & 108 & 72 & 180 & 72 & 72 & 216 & 222 & 144 \\
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
    片段级 & Accuracy & 0.9968 \\
    片段级 & Macro-F1 & 0.9972 \\
    文件级 & Accuracy & 1.0000 \\
    文件级 & Macro-F1 & 1.0000 \\
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
  \begin{tabular}{cccc}
    \toprule
    真实$\backslash$预测 & 0 & 1 & 2 \\
    \midrule
    0 & 60 & 0 & 0 \\
    1 & 0 & 155 & 1 \\
    2 & 0 & 0 & 96 \\
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
  \begin{tabular}{cccc}
    \toprule
    真实$\backslash$预测 & 0 & 1 & 2 \\
    \midrule
    0 & 5 & 0 & 0 \\
    1 & 0 & 13 & 0 \\
    2 & 0 & 0 & 8 \\
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
    验证集最优模型 & MAE & 0.3148 \\
    测试集 & MAE & 0.3703 \\
    测试集 & RMSE & 0.5934 \\
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
    Stage2 分类 & Accuracy = 0.9968 & Macro-F1 = 0.9972 & 文件级 Accuracy = 1.0000 \\
    Stage1 回归 & MAE = 0.3703 & RMSE = 0.5934 & 双通道距离估计 \\
    \bottomrule
  \end{tabular}
\end{table}
```
