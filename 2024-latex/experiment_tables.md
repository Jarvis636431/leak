# Experiment Tables

This file intentionally contains placeholders after switching to the Internoise
dataset. Replace these tables after the new Stage2 and Stage1 training runs
finish.

## 1. Dataset Statistics

```tex
\begin{table}[!htbp]
  \centering
  \caption{Internoise 数据集划分统计结果（待更新）}
  \label{tab:dataset_split_stats}
  \vspace{0.5em}
  \begin{tabular}{lcccc}
    \toprule
    任务 & 总样本数 & 训练集 & 验证集 & 测试集 \\
    \midrule
    Stage2 分类 & 待填 & 待填 & 待填 & 待填 \\
    Stage1 回归 & 待填 & 待填 & 待填 & 待填 \\
    \bottomrule
  \end{tabular}
\end{table}
```

## 2. Stage2 Classification Results

```tex
\begin{table}[!htbp]
  \centering
  \caption{Stage2 分类任务测试结果（待更新）}
  \label{tab:stage2_results_final}
  \vspace{0.5em}
  \begin{tabular}{lcc}
    \toprule
    评测层级 & 指标 & 数值 \\
    \midrule
    片段级 & Accuracy & 待填 \\
    片段级 & Macro-F1 & 待填 \\
    文件级 & Accuracy & 待填 \\
    文件级 & Macro-F1 & 待填 \\
    \bottomrule
  \end{tabular}
\end{table}
```

## 3. Stage1 Regression Results

```tex
\begin{table}[!htbp]
  \centering
  \caption{Stage1 回归任务结果（待更新）}
  \label{tab:stage1_results_final}
  \vspace{0.5em}
  \begin{tabular}{lcc}
    \toprule
    数据划分 & 指标 & 数值 \\
    \midrule
    验证集最优模型 & MAE & 待填 \\
    测试集 & MAE & 待填 \\
    测试集 & RMSE & 待填 \\
    \bottomrule
  \end{tabular}
\end{table}
```

## 4. Main Results Summary

```tex
\begin{table}[!htbp]
  \centering
  \caption{两阶段任务主要实验结果汇总（待更新）}
  \label{tab:main_results_summary}
  \vspace{0.5em}
  \begin{tabular}{lccc}
    \toprule
    任务 & 测试指标 1 & 测试指标 2 & 备注 \\
    \midrule
    Stage2 分类 & 待填 & 待填 & 五分类 \\
    Stage1 回归 & 待填 & 待填 & 双通道距离估计 \\
    \bottomrule
  \end{tabular}
\end{table}
```
