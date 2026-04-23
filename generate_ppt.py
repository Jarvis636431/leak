"""
生成毕业设计论文答辩 PPT
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
import os

# 创建演示文稿 (16:9 宽屏)
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

# 颜色方案
COLOR_TITLE = RGBColor(0x1F, 0x49, 0x7D)  # 深蓝色
COLOR_ACCENT = RGBColor(0x2E, 0x86, 0xAB)  # 浅蓝色
COLOR_TEXT = RGBColor(0x33, 0x33, 0x33)  # 深灰色
COLOR_BG = RGBColor(0xFF, 0xFF, 0xFF)  # 白色

def add_title_slide(prs, title, subtitle=""):
    """添加标题页"""
    slide_layout = prs.slide_layouts[6]  # 空白布局
    slide = prs.slides.add_slide(slide_layout)

    # 背景色块
    shape = slide.shapes.add_shape(1, Inches(0), Inches(2.5), Inches(13.333), Inches(2.5))
    shape.fill.solid()
    shape.fill.fore_color.rgb = COLOR_TITLE
    shape.line.fill.background()

    # 主标题
    txBox = slide.shapes.add_textbox(Inches(0.5), Inches(2.8), Inches(12.333), Inches(1.2))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(44)
    p.font.bold = True
    p.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    p.alignment = PP_ALIGN.CENTER

    # 副标题
    if subtitle:
        txBox2 = slide.shapes.add_textbox(Inches(0.5), Inches(4.2), Inches(12.333), Inches(0.6))
        tf2 = txBox2.text_frame
        p2 = tf2.paragraphs[0]
        p2.text = subtitle
        p2.font.size = Pt(24)
        p2.font.color.rgb = RGBColor(0xCC, 0xDD, 0xEE)
        p2.alignment = PP_ALIGN.CENTER

    return slide

def add_section_slide(prs, section_num, section_title):
    """添加章节分隔页"""
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    # 左侧色块
    shape = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(4), Inches(7.5))
    shape.fill.solid()
    shape.fill.fore_color.rgb = COLOR_TITLE
    shape.line.fill.background()

    # 章节编号
    txBox = slide.shapes.add_textbox(Inches(0.5), Inches(2.8), Inches(3), Inches(1.5))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = section_num
    p.font.size = Pt(72)
    p.font.bold = True
    p.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    p.alignment = PP_ALIGN.CENTER

    # 章节标题
    txBox2 = slide.shapes.add_textbox(Inches(4.5), Inches(3), Inches(8.333), Inches(1.5))
    tf2 = txBox2.text_frame
    p2 = tf2.paragraphs[0]
    p2.text = section_title
    p2.font.size = Pt(40)
    p2.font.bold = True
    p2.font.color.rgb = COLOR_TITLE
    p2.alignment = PP_ALIGN.LEFT

    return slide

def add_content_slide(prs, title, bullet_points, two_columns=False):
    """添加内容页"""
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    # 顶部标题栏
    shape = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.333), Inches(1.2))
    shape.fill.solid()
    shape.fill.fore_color.rgb = COLOR_TITLE
    shape.line.fill.background()

    # 标题文字
    txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12.333), Inches(0.7))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    if two_columns:
        # 左列
        txBox_left = slide.shapes.add_textbox(Inches(0.5), Inches(1.5), Inches(5.8), Inches(5.5))
        tf_left = txBox_left.text_frame
        tf_left.word_wrap = True
        for i, point in enumerate(bullet_points[0]):
            if i == 0:
                p = tf_left.paragraphs[0]
            else:
                p = tf_left.add_paragraph()
            p.text = "• " + point
            p.font.size = Pt(18)
            p.font.color.rgb = COLOR_TEXT
            p.space_after = Pt(12)

        # 右列
        txBox_right = slide.shapes.add_textbox(Inches(6.8), Inches(1.5), Inches(5.8), Inches(5.5))
        tf_right = txBox_right.text_frame
        tf_right.word_wrap = True
        for i, point in enumerate(bullet_points[1]):
            if i == 0:
                p = tf_right.paragraphs[0]
            else:
                p = tf_right.add_paragraph()
            p.text = "• " + point
            p.font.size = Pt(18)
            p.font.color.rgb = COLOR_TEXT
            p.space_after = Pt(12)
    else:
        # 单列
        txBox = slide.shapes.add_textbox(Inches(0.5), Inches(1.5), Inches(12.333), Inches(5.5))
        tf = txBox.text_frame
        tf.word_wrap = True
        for i, point in enumerate(bullet_points):
            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            p.text = "• " + point
            p.font.size = Pt(20)
            p.font.color.rgb = COLOR_TEXT
            p.space_after = Pt(14)

    return slide

def add_table_slide(prs, title, headers, rows):
    """添加表格页"""
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    # 顶部标题栏
    shape = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.333), Inches(1.2))
    shape.fill.solid()
    shape.fill.fore_color.rgb = COLOR_TITLE
    shape.line.fill.background()

    txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12.333), Inches(0.7))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    # 表格
    num_cols = len(headers)
    num_rows = len(rows) + 1
    table = slide.shapes.add_table(num_rows, num_cols, Inches(1), Inches(1.8), Inches(11.333), Inches(4.5)).table

    # 设置列宽
    col_width = Inches(11.333 / num_cols)
    for i in range(num_cols):
        table.columns[i].width = col_width

    # 表头
    for i, header in enumerate(headers):
        cell = table.cell(0, i)
        cell.text = header
        cell.fill.solid()
        cell.fill.fore_color.rgb = COLOR_TITLE
        p = cell.text_frame.paragraphs[0]
        p.font.size = Pt(16)
        p.font.bold = True
        p.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        p.alignment = PP_ALIGN.CENTER

    # 数据行
    for row_idx, row_data in enumerate(rows):
        for col_idx, cell_text in enumerate(row_data):
            cell = table.cell(row_idx + 1, col_idx)
            cell.text = str(cell_text)
            p = cell.text_frame.paragraphs[0]
            p.font.size = Pt(14)
            p.font.color.rgb = COLOR_TEXT
            p.alignment = PP_ALIGN.CENTER

    return slide

def add_result_slide(prs, title, items):
    """添加结果展示页"""
    slide_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(slide_layout)

    # 顶部标题栏
    shape = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.333), Inches(1.2))
    shape.fill.solid()
    shape.fill.fore_color.rgb = COLOR_TITLE
    shape.line.fill.background()

    txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12.333), Inches(0.7))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    # 结果卡片
    y_pos = 1.6
    for item in items:
        # 卡片背景
        card = slide.shapes.add_shape(1, Inches(0.5), Inches(y_pos), Inches(12.333), Inches(1.1))
        card.fill.solid()
        card.fill.fore_color.rgb = RGBColor(0xF5, 0xF8, 0xFA)
        card.line.color.rgb = COLOR_ACCENT

        # 任务名称
        title_box = slide.shapes.add_textbox(Inches(0.7), Inches(y_pos + 0.15), Inches(4), Inches(0.4))
        p = title_box.text_frame.paragraphs[0]
        p.text = item["task"]
        p.font.size = Pt(18)
        p.font.bold = True
        p.font.color.rgb = COLOR_TITLE

        # 指标
        metrics_box = slide.shapes.add_textbox(Inches(0.7), Inches(y_pos + 0.55), Inches(11.5), Inches(0.4))
        p = metrics_box.text_frame.paragraphs[0]
        p.text = item["metrics"]
        p.font.size = Pt(16)
        p.font.color.rgb = COLOR_TEXT

        y_pos += 1.3

    return slide

# ============================================================
# 开始生成 PPT
# ============================================================

# 1. 封面
add_title_slide(
    prs,
    "基于双通道传感信号的管道泄漏检测与定位",
    "天津大学本科生毕业设计答辩"
)

# 2. 目录页
add_content_slide(prs, "目录", [
    "绪论",
    "数据集构建与任务定义",
    "两阶段泄漏检测模型设计",
    "实验设计与结果分析",
    "结论与展望",
])

# ===== 第一章 绪论 =====
add_section_slide(prs, "01", "绪论")

add_content_slide(prs, "1.1 研究背景与意义", [
    "管道输送系统广泛应用于能源、化工与市政基础设施等场景",
    "泄漏故障隐蔽性强、传播范围广、发现滞后，易造成安全事故",
    "传统方法（人工经验、阈值规则、频域分析）存在局限：",
    "    - 特征设计依赖人工，泛化能力有限",
    "    - 面对复杂工况时，定位精度不足",
    "深度学习为直接从原始信号中学习提供了新的技术路径",
    "本文工作：设计两阶段泄漏检测框架，完成状态识别与距离估计",
])

add_content_slide(prs, "1.2 研究问题与本文工作", [
    "核心问题：如何利用双通道长时序传感信号，实现泄漏状态识别与距离估计",
    "",
    "本文完成的工作：",
    "① 设计自动化数据构建流程：原始 CSV 信号 → 分段训练样本",
    "② 构建两阶段学习任务：分类（Stage2）+ 回归（Stage1）",
    "③ 设计一维卷积神经网络：多层 Conv + BatchNorm + GELU",
    "④ 搭建统一训练框架：片段级 + 文件级评测指标",
])

add_content_slide(prs, "1.3 论文结构安排", [
    "第一章 绪论：介绍研究背景、研究意义、研究问题与主要工作",
    "第二章 数据集构建：说明原始数据组织、标签映射和分段策略",
    "第三章 模型设计：介绍两阶段检测框架的整体结构与网络设计",
    "第四章 实验分析：讨论分类性能、距离估计误差及影响因素",
    "第五章 结论展望：总结全文工作，展望后续改进方向",
])

# ===== 第二章 数据集构建 =====
add_section_slide(prs, "02", "数据集构建与任务定义")

add_content_slide(prs, "2.1 原始数据组织方式", [
    "原始数据以 CSV 文件形式存储：",
    "    • raw/leak/：发生泄漏的实验样本",
    "    • raw/normal/：正常状态样本",
    "文件名采用 ABC 编号形式（如 ABC91.csv）",
    "",
    "每个 CSV 文件包含左右两个传感通道的时序数据",
    "",
    "优点：",
    "    ① 原始信号与实验编号一一对应，便于标签映射",
    "    ② 双通道结构保留泄漏传播在不同位置的响应差异",
])

add_content_slide(prs, "2.2 标签映射与任务拆分", [
    "编号区间同时对应两个标签：泄漏距离 + 泄漏形态类别",
    "",
    "两阶段任务拆分：",
    "Stage2 分类任务",
    "    • 输入：单通道分段信号",
    "    • 输出：三类标签（正常 + 两类泄漏形态）",
    "",
    "Stage1 回归任务",
    "    • 输入：同一时间窗口下的左右双通道信号对",
    "    • 输出：泄漏距离",
    "",
    "优势：将复杂问题拆分为「状态识别」+「位置估计」两个子任务",
])

add_content_slide(prs, "2.3 分段策略与样本生成", [
    "分段参数：",
    "    • 采样率：25600 Hz",
    "    • 分段时长：5 秒",
    "    • 单段样本长度：25600 × 5 = 128000 点",
    "",
    "切分方式：固定窗口不重叠切分",
    "",
    "分类任务：左右通道视为两条独立单通道样本",
    "回归任务：左右通道在相同时刻配对形成双通道输入",
    "",
    "优点：实现简单、样本规模可扩展、便于批量训练",
    "局限：窗口间无显式时序关联，可考虑重叠切窗或序列建模",
])

add_table_slide(
    prs, "2.4 数据集统计",
    ["任务", "总样本数", "训练集", "验证集", "测试集"],
    [
        ["Stage2 分类", "3024", "2112", "600", "312"],
        ["Stage1 回归", "1122", "768", "228", "126"],
    ]
)

add_content_slide(prs, "2.4 数据集分布特点", [
    "Stage2 分类 — 三类样本分布不均衡：",
    "    • 类别 0（正常）：780 条",
    "    • 类别 1（泄漏形态 1）：1440 条",
    "    • 类别 2（泄漏形态 2）：804 条",
    "",
    "Stage1 回归 — 距离标签共 9 个离散取值：",
    "    • 主要集中在 12、14、16 位置附近",
    "    • 样本数分别为：36、108、72、180、72、72、216、222、144",
    "",
    "需关注：分类任务类别偏置问题 / 回归任务不同距离区间预测误差",
])

# ===== 第三章 模型设计 =====
add_section_slide(prs, "03", "两阶段泄漏检测模型设计")

add_content_slide(prs, "3.1 总体框架", [
    "三个核心环节：",
    "    ① 数据切分：原始双通道采样信号 → 固定长度片段",
    "    ② 分类识别：单通道分类模型判断信号状态（正常/泄漏）",
    "    ③ 距离估计：双通道回归模型对泄漏片段估计距离",
    "",
    "代码实现：",
    "    • 统一入口：src/leak_detection/cli/train.py",
    "    • 分类/回归共享训练流程，仅在数据组织、损失函数和指标上区分",
    "    • 有利于对比实验与复现",
])

add_content_slide(prs, "3.2 输入表示与归一化", [
    "输入形式：",
    "    • 分类：$1 \\times 128000$ 单通道张量",
    "    • 回归：$2 \\times 128000$ 双通道张量",
    "",
    "归一化方法 — 逐样本标准化：",
    "",
    "         x̂ = (x - μ) / (σ + 10⁻⁶)",
    "",
    "    • σ 接近零时仅去均值，避免除零",
    "    • 降低量纲差异影响，使网络关注波形形态与通道间相对变化",
])

add_content_slide(prs, "3.3 一维卷积特征提取网络", [
    "网络结构（定义于 src/leak_detection/models/signal_models.py）：",
    "",
    "每级模块：Conv + BatchNorm + GELU + Conv + BatchNorm + GELU",
    "",
    "超参数配置：",
    "    • 通道数：[32, 64, 128, 256]",
    "    • 卷积核：[15, 9, 7, 5]",
    "    • 步长：均为 4",
    "",
    "通过多层降采样，128000 点时序被压缩为全局特征向量",
    "最后经全连接层构建分类头或回归头",
    "",
    "优势：实现简单、参数量可控、适合长序列一维信号",
])

add_content_slide(prs, "3.4 分类头与回归头设计", [
    "Stage2 分类模型：",
    "    • 输入：单通道信号",
    "    • 结构：全局特征 → 两层全连接 → 三维类别输出",
    "    • 损失：交叉熵损失",
    "",
    "Stage1 回归模型：",
    "    • 输入：双通道信号对",
    "    • 输出：单一实数（泄漏距离预测值）",
    "    • 损失：Smooth L1 Loss",
    "        - 误差 < 1：二次惩罚",
    "        - 误差 ≥ 1：线性惩罚，对离群点更鲁棒",
])

add_content_slide(prs, "3.5 训练策略", [
    "训练流程定义于 src/leak_detection/training/trainer.py",
    "",
    "优化器：AdamW",
    "    • 学习率：0.001，权重衰减：0.0001",
    "",
    "学习率调度：余弦退火（Cosine Annealing）",
    "",
    "正则化与稳定化：",
    "    • 梯度裁剪（阈值 1.0），防止梯度爆炸",
    "    • 早停（patience = 8），验证集指标长期未提升则停止",
    "",
    "训练配置：最大 40 epochs，batch size 分类 64 / 回归 32",
])

# ===== 第四章 实验结果 =====
add_section_slide(prs, "04", "实验设计与结果分析")

add_content_slide(prs, "4.1 实验环境与配置", [
    "实验基于 Python + PyTorch 完成",
    "",
    "配置文件：",
    "    • configs/stage2.yaml — 分类实验",
    "    • configs/stage1.yaml — 回归实验",
    "",
    "随机种子：42（保证训练集/验证集/测试集划分一致）",
    "",
    "评测体系：",
    "    • 片段级评测：逐片段预测准确率",
    "    • 文件级评测：同一文件所有片段聚合后评测",
])

add_content_slide(prs, "4.2 评价指标", [
    "分类任务 — Stage2：",
    "    • Accuracy = N_correct / N_total",
    "    • Macro-F1：各类别 F1 等权平均，应对类别不均衡",
    "    • 混淆矩阵：片段级 + 文件级",
    "",
    "回归任务 — Stage1：",
    "    • MAE = (1/N) Σ|d_i - d̂_i|",
    "    • RMSE = √[(1/N) Σ(d_i - d̂_i)²]",
    "",
    "MAE 反映平均偏差，RMSE 对较大误差更敏感，二者结合全面评价",
])

add_result_slide(prs, "4.3 实验结果 — Stage2 分类", [
    {
        "task": "Stage2 片段级",
        "metrics": "Accuracy = 0.9968  |  Macro-F1 = 0.9972",
    },
    {
        "task": "Stage2 文件级",
        "metrics": "Accuracy = 1.0000  |  Macro-F1 = 1.0000",
    },
])

add_result_slide(prs, "4.3 实验结果 — Stage1 回归", [
    {
        "task": "Stage1 验证集最优模型",
        "metrics": "MAE = 0.3148",
    },
    {
        "task": "Stage1 测试集",
        "metrics": "MAE = 0.3703  |  RMSE = 0.5934",
    },
])

add_content_slide(prs, "4.3 混淆矩阵分析", [
    "Stage2 片段级 — 312 个测试样本中仅 1 次误分类：",
    "    • 真实类别 1 中有 1 个片段被误判为类别 2",
    "    • 其余样本全部正确识别",
    "",
    "Stage2 文件级 — 26 个测试文件全部正确分类：",
    "    • 混淆矩阵主对角线全为正",
    "    • 表明各类别识别均稳定，非多数类支撑的虚高",
    "",
    "Stage1 — 明显优于统计基线：",
    "    • 均值/中位数预测基线 MAE 通常 > 3",
    "    • 本文 MAE = 0.3703，说明模型有效捕获了信号与距离的映射关系",
])

add_content_slide(prs, "4.4 结果分析", [
    "Stage2 分类：",
    "    • 一维卷积能有效捕获分段信号中的泄漏形态差异",
    "    • 文件级 1.0 准确率排除片段级虚高，结果具有说服力",
    "",
    "Stage1 回归：",
    "    • 双通道信号为距离估计提供了有效信息",
    "    • 误差控制在相邻距离档位附近，具有较好的估计能力",
    "",
    "局限与展望：",
    "    • 当前随机划分下测试集规模有限",
    "    • 后续需设计更严格的数据切分策略，补充跨工况泛化实验",
])

# ===== 第五章 结论 =====
add_section_slide(prs, "05", "结论与展望")

add_content_slide(prs, "5.1 全文总结", [
    "本文围绕双通道管道传感信号的泄漏检测问题，完成了：",
    "    ① 数据构建：自动化数据处理流程，分段样本生成",
    "    ② 任务拆分：分类任务（状态识别）+ 回归任务（距离估计）",
    "    ③ 模型设计：统一一维卷积神经网络框架",
    "    ④ 训练流程：片段级与文件级评测体系",
    "",
    "实验结果验证了两阶段方案的有效性：",
    "    • Stage2 文件级准确率与 F1 均达到 1.0",
    "    • Stage1 测试集 MAE = 0.3703，RMSE = 0.5934",
    "    • 明显优于统计基线，流程清晰、复现方便",
])

add_content_slide(prs, "5.2 后续工作展望", [
    "数据层面：",
    "    • 扩充不同工况、不同噪声条件、不同距离位置的样本",
    "",
    "模型层面：",
    "    • 引入多尺度卷积、残差结构、注意力机制",
    "    • 探索时频联合建模方法",
    "",
    "任务层面：",
    "    • 设计分类+定位联合学习框架",
    "    • 探索共享特征表示是否进一步提升整体性能",
    "",
    "应用层面：",
    "    • 实时推理、模型轻量化、工程部署适配",
])

# 感谢页
add_title_slide(prs, "谢谢！", "欢迎提问与指正")

# 保存文件
output_path = "outputs/毕业设计答辩PPT.pptx"
os.makedirs("outputs", exist_ok=True)
prs.save(output_path)
print(f"PPT 已生成：{output_path}")
