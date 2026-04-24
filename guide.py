import matplotlib.pyplot as plt
from wordcloud import WordCloud
import numpy as np
from PIL import Image
import io
import os
import platform
import base64
from pathlib import Path

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'PingFang SC', 'Hiragino Sans GB', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


def get_chinese_font_path():
    """获取系统中文字体路径"""
    system = platform.system()

    if system == 'Windows':
        font_paths = ['C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simhei.ttf']
    elif system == 'Darwin':
        font_paths = ['/System/Library/Fonts/PingFang.ttc', '/System/Library/Fonts/STHeiti Light.ttc']
    else:
        font_paths = ['/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf']

    for path in font_paths:
        if os.path.exists(path):
            return path
    return None


def get_keywords_T():
    """T词云：贡献人物名（中英文混合）"""
    return {
        'Hamilton': 18, '哈密顿': 16, 'Kirkman': 14, '柯克曼': 12,
        'Menger': 16, '门格尔': 14, 'Flood': 14, '弗勒德': 12,
        'Robinson': 15, '罗宾逊': 13, 'Dantzig': 18, '丹齐克': 16,
        'Fulkerson': 16, '富尔克森': 14, 'Johnson': 14, '约翰逊': 12,
        'Christofides': 18, '克里斯托菲德斯': 16, 'Euler': 16, '欧拉': 16,
        'Karp': 18, '卡普': 16, 'Grötschel': 14, '格罗切尔': 12,
        'Padberg': 14, '帕德伯格': 12, 'Rinaldi': 14, '里纳尔迪': 12,
        'Dijkstra': 14, '迪杰斯特拉': 12, 'Cook': 18, '库克': 16,
        'Reinelt': 15, '赖内尔特': 13, 'Whitney': 12, '惠特尼': 10,
        'Harry Beck': 12, '哈利·贝克': 10, 'Halton': 12, '霍尔顿': 10,
        'Vignelli': 16,'维格涅里': 12,
    }


def get_keywords_S():
    """S词云：技术词汇、算法名称、判据论断（中英文混合）"""
    return {
        'NP-Complete': 20, 'NP完全': 18, 'NP-Hard': 20, 'NP难': 18,
        'Hamiltonian Cycle': 18, '哈密顿回路': 16, 'Cutting Plane': 18, '割平面法': 16,
        'Branch and Bound': 18, '分支定界': 16, 'Minimum Spanning Tree': 16, '最小生成树': 14,
        'Christofides Algorithm': 18, '克里斯托菲德斯算法': 16, 'Concorde': 16, '协和求解器': 14,
        'Dynamic Programming': 14, '动态规划': 12, 'Approximation Ratio': 15, '近似比': 13,
        'Lower Bound': 14, '下界': 12, 'Upper Bound': 14, '上界': 12,
        'Exact Algorithm': 15, '精确算法': 13, 'Metaheuristic': 12, '元启发式': 10,
        'Simulated Annealing': 12, '模拟退火': 10, 'Genetic Algorithm': 12, '遗传算法': 10,
        'Lin-Kernighan': 14, '林-克尼根算法': 12, 'Integer Programming': 14, '整数规划': 12,
    }


def get_keywords_P():
    """P词云：TSP各种变体、相似原理难题（中英文混合）"""
    return {
        'VRP 车辆路径问题': 12, 'JSP 作业车间调度': 18,
        'Job Shop': 16, 'Protein Folding': 18, '蛋白质折叠': 16, 'Protein Prediction': 16, '蛋白质预测': 14,
        'PCB Etching': 18, '电路板蚀刻': 16, 'Laser Engraving': 18, '激光雕刻': 16,
        'CNC Path': 16, '数控加工路径': 14, 'Metric TSP': 15, '度量TSP': 13,
        'Asymmetric TSP': 14, '非对称TSP': 12, 'mTSP': 14, '多旅行商问题': 12,
        'TSPTW': 13, '带时间窗TSP': 11, 'Orienteering': 13, '定向问题': 11,
        'Logistics': 16, '物流规划': 14, 'Supply Chain': 14, '供应链优化': 12,
        'Last Mile': 13, '最后一公里': 11, 'Drone Delivery': 13, '无人机配送': 11,
        'Robot Planning': 14, '机器人路径规划': 12, '3D Printing': 14, '3D打印路径': 12,
        'DNA Sequencing': 13, 'DNA测序': 11, 'Genome Assembly': 14, '基因组组装': 12,
        'graph theory图论':20,'operational research运筹学':20,'topology拓扑学':18,'combinationtorial optimization组合优化':20
    }


def create_full_mask(letter, size=800):
    """创建完整字母形状的mask"""
    fig, ax = plt.subplots(figsize=(size / 100, size / 100), dpi=100)
    fig.patch.set_facecolor('black')
    ax.set_facecolor('black')

    ax.text(0.5, 0.5, letter, fontsize=size * 0.7, fontweight='bold',
            fontfamily='DejaVu Sans', ha='center', va='center',
            color='white', transform=ax.transAxes)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')

    fig.canvas.draw()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100, facecolor='black')
    buf.seek(0)
    img = Image.open(buf)
    mask_array = np.array(img)
    plt.close(fig)

    if len(mask_array.shape) == 3:
        mask = (mask_array[:, :, 0] > 200) & (mask_array[:, :, 1] > 200) & (mask_array[:, :, 2] > 200)
    else:
        mask = mask_array > 200

    mask_cloud = np.zeros_like(mask, dtype=np.uint8)
    mask_cloud[mask] = 255
    return mask_cloud


def create_lower_half_placement_mask(letter: str, size: int = 800) -> np.ndarray:
    """创建“下半部分可放词”的字母 mask（整体尺寸不变，用于形成“淹没到腰部”效果）。"""
    full = create_full_mask(letter, size=size)
    h = full.shape[0]
    half = h // 2
    placement = full.copy()
    placement[:half, :] = 0
    return placement


def generate_full_wordcloud(letter, keywords, size=600):
    """生成完整词云"""
    mask = create_full_mask(letter, size)
    chinese_font_path = get_chinese_font_path()

    wordcloud = WordCloud(
        width=size, height=size, background_color='white', colormap='viridis',
        max_words=100, prefer_horizontal=0.65, relative_scaling=0.5,
        min_font_size=6, max_font_size=55, mask=mask, contour_width=3,
        contour_color='#006D6D', font_path=chinese_font_path, collocations=False
    ).generate_from_frequencies(keywords)

    return wordcloud


def generate_submerged_wordcloud(letter, keywords, size=600):
    """生成与 T/S 同风格的字母词云，仅保留字母内部下半高度填充。"""
    placement_mask = create_lower_half_placement_mask(letter, size=size)
    chinese_font_path = get_chinese_font_path()

    wordcloud = WordCloud(
        width=size,
        height=size,
        background_color='white',
        colormap='viridis',
        max_words=max(len(keywords), 120),
        prefer_horizontal=0.65,
        relative_scaling=0.28,
        min_font_size=3,
        max_font_size=24,
        mask=placement_mask,
        contour_width=3,
        contour_color='#006D6D',
        font_path=chinese_font_path,
        collocations=False,
        repeat=False,
    ).generate_from_frequencies(keywords)
    return wordcloud


def create_timeline(ax_timeline):
    """创建时间轴：节点均匀分布，间距紧凑"""

    events = [
        (1736, "1736", "Eluer", "欧拉", "konisberg seven bridges\n七桥问题"),
        (1850, "1850", "Hamilton", "哈密顿", "Hamiltonian circuit\n哈密顿通路"),
        (1930, "1930", "Menger &\nFlood", "门格尔\n&弗勒德", "TSP\ndefinition"),
        (1933,"1933","HarryBeck","哈利·贝克","London Underground Map"),
        (1949, "1949", "Julia\nRobinson", "朱莉娅\n罗宾逊", "First\n'TSP' usage"),
        (1954, "1954", "Dantzig,\nFulkerson,\nJohnson", "丹齐克,\n富尔克森,\n约翰逊", "49-city\nsolved"),
        (1959,"1959","Dijkstra","迪杰斯特拉","dijkstra算法"),
        (1972, "1972", "Karp,Vignelli", "卡普，维格涅里", "NP-complete proof,NY transit map"),
        (1976, "1976", "Christofides", "克里斯托菲德斯", "1.5×\nalgorithm"),
        (1989,"1989","goldberg","古登伯格","genetic algorithm遗传算法"),
        (1991, "1991", "Gerhard\nReinelt", "格哈德\n赖内尔特", "TSPLIB"),
        (2002,"2002","Fischetti","菲谢蒂","对称广义TSP"),
        (2006, "2006", "Cook,Gutin", "库克,古丁", "85,900-city solved,TSP&variation"),
        (2020, "2020", "Karlin\net al.", "卡林\n等人", "Metric TSP\nimproved")
    ]

    years_num = [e[0] for e in events]
    years_label = [e[1] for e in events]
    en_names = [e[2] for e in events]
    cn_names = [e[3] for e in events]
    contributions = [e[4] for e in events]

    # 计算均匀分布的X坐标
    n_nodes = len(years_num)
    x_min = min(years_num) - 8
    x_max = max(years_num) + 8
    x_positions = np.linspace(x_min, x_max, n_nodes)

    # 绘制水平时间轴
    ax_timeline.hlines(y=0, xmin=x_min, xmax=x_max,
                       color='#006D6D', linewidth=2.5, alpha=0.7)

    # 绘制节点（均匀分布）
    ax_timeline.scatter(x_positions, [0] * n_nodes, color='#008B8B',
                        s=120, zorder=5, edgecolors='#004C4C', linewidth=2.5)

    # 标注事件
    for x_pos, year_label, en_name, cn_name, contribution in zip(x_positions, years_label, en_names, cn_names,
                                                                 contributions):
        # 贡献描述（节点上方，斜向45度）
        ax_timeline.text(x_pos, 0.25, contribution, ha='center', va='bottom',
                         fontsize=7, color='#006D6D', weight='bold',
                         rotation=45, linespacing=1.0)

        # 时间标签（节点下方，紧贴节点）
        ax_timeline.text(x_pos, -0.08, year_label, ha='center', va='top',
                         fontsize=9, fontweight='bold', color='#004C4C')

        # 人物姓名（紧挨时间下方）
        name_text = f"{en_name}\n{cn_name}"
        ax_timeline.text(x_pos, -0.28, name_text, ha='center', va='top',
                         fontsize=6.5, color='navy', style='italic',
                         linespacing=0.9)

    ax_timeline.set_ylim(-0.5, 0.55)
    ax_timeline.set_xlim(x_min, x_max)
    ax_timeline.set_yticks([])
    ax_timeline.set_xticks([])

    for spine in ax_timeline.spines.values():
        spine.set_visible(False)

    # 时间箭头
    ax_timeline.annotate('', xy=(x_max - 2, 0), xytext=(x_max - 5, 0),
                         arrowprops=dict(arrowstyle='->', color='#006D6D', lw=2.5, alpha=0.7))
    ax_timeline.text(x_max - 0.5, 0, 'Time →', ha='center', va='center',
                     fontsize=11, fontweight='bold', color='#006D6D')

    return ax_timeline


def create_timeline_with_tsp_wordcloud():
    """创建带有 TSP 字母词云的时间轴（返回 Matplotlib Figure）。"""

    # 获取三类关键词
    keywords_T = get_keywords_T()
    keywords_S = get_keywords_S()
    keywords_P = get_keywords_P()

    # 创建大图
    fig = plt.figure(figsize=(22, 9))

    # 创建网格布局：2行4列
    gs = fig.add_gridspec(2, 4, height_ratios=[0.65, 0.35],
                          hspace=0.08, top=0.96, bottom=0.08)

    # ===== 第一行：GRAPH 和 T、S、P 并排 =====
    # GRAPH 单词（第1列）
    ax_graph = fig.add_subplot(gs[0, 0])
    ax_graph.axis('off')
    # 让 GRAPH 底部与右侧词云底部对齐：贴近坐标系底部绘制
    graph_text = ax_graph.text(0.5, 0.0, 'GRAPH', fontsize=68, fontweight='bold',
                               color='#006D6D', ha='center', va='bottom',
                               fontfamily='DejaVu Sans', transform=ax_graph.transAxes)
    ax_graph.set_xlim(0, 1)
    ax_graph.set_ylim(0, 1)

    # T词云（第2列）- 人物名，完整填充
    print("正在生成 T 词云（贡献人物名）- 完整填充...")
    ax_T = fig.add_subplot(gs[0, 1])
    wc_T = generate_full_wordcloud('T', keywords_T, size=600)
    ax_T.imshow(wc_T.to_array(), interpolation='bilinear')
    ax_T.axis('off')

    # S词云（第3列）- 技术词汇/算法，完整填充
    print("正在生成 S 词云（技术词汇/算法）- 完整填充...")
    ax_S = fig.add_subplot(gs[0, 2])
    wc_S = generate_full_wordcloud('S', keywords_S, size=600)
    ax_S.imshow(wc_S.to_array(), interpolation='bilinear')
    ax_S.axis('off')

    # P词云（第4列）- 与 T/S 同风格，仅下半高度填充
    print("正在生成 P 词云（TSP变体/相似难题）- 淹没到腰部...")
    ax_P = fig.add_subplot(gs[0, 3])
    wc_P = generate_submerged_wordcloud('P', keywords_P, size=600)
    ax_P.imshow(wc_P.to_array(), interpolation='bilinear')
    ax_P.axis('off')

    # ===== 第二行：时间轴 =====
    ax_timeline = fig.add_subplot(gs[1, :])
    create_timeline(ax_timeline)

    # 精确把 GRAPH 字形底边对齐到轴底部（与词云底部水平一致）
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    bbox = graph_text.get_window_extent(renderer=renderer)
    y0_axes = ax_graph.transAxes.inverted().transform((bbox.x0, bbox.y0))[1]
    graph_text.set_position((0.5, -y0_axes))

    return fig


def _fig_to_data_uri(fig) -> str:
    """将 figure 导出为 PNG base64 data URI。"""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight", facecolor="white")
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def build_guide_template(banner_data_uri: str) -> str:
    """生成极简 Django 模板版 guide.html（仅 Banner + 两按钮）。"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>地铁网络引导页</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{ width: 100%; height: 100%; font-family: "Microsoft YaHei", "Segoe UI", sans-serif; background: #ffffff; color: #0f172a; }}
    body {{ background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%); }}

    .page {{
      width: 100vw;
      height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 14px;
    }}
    .wrap {{
      width: 100%;
      height: 100%;
      max-width: 1600px;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .hero {{
      width: 100%;
      height: 100%;
      border: 1px solid #e2e8f0;
      border-radius: 18px;
      background: #ffffff;
      box-shadow: 0 22px 56px rgba(15, 23, 42, 0.08);
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }}
    .hero img {{
      flex: 1;
      width: 100%;
      min-height: 0;
      object-fit: contain;
      display: block;
      background: #ffffff;
    }}

    .actions {{
      display: flex;
      justify-content: center;
      gap: 14px;
      flex-wrap: wrap;
      padding: 14px 18px 18px;
      border-top: 1px solid #eef2ff;
      background: #f8fafc;
    }}
    .btn {{
      min-width: 170px;
      padding: 13px 20px;
      font-size: 16px;
      font-weight: 800;
      border-radius: 12px;
      cursor: pointer;
      border: 1px solid #cbd5e1;
      background: #ffffff;
      color: #0f172a;
      transition: all .2s ease;
    }}
    .btn:hover {{
      transform: translateY(-1px);
      box-shadow: 0 10px 24px rgba(37, 99, 235, 0.13);
      border-color: #93c5fd;
    }}
    .btn.primary {{ background: #2563eb; color: #ffffff; border-color: #2563eb; }}
  </style>
</head>
<body>
  <div class="page">
    <div class="wrap">
      <section class="hero">
        <img src="{banner_data_uri}" alt="TSP Timeline Banner" />
        <div class="actions">
          <button class="btn" id="btn-graph">拓扑结构</button>
          <button class="btn primary" id="btn-alg">TSP算法</button>
        </div>
      </section>
    </div>
  </div>

  <script>
    // 保留原 guide.html 文件跳转逻辑
    document.getElementById('btn-graph').addEventListener('click', () => {{
      window.location.href = '/graph/';
    }});
    document.getElementById('btn-alg').addEventListener('click', () => {{
      window.location.href = '/algorithm/';
    }});
  </script>
</body>
</html>
"""


def write_guide_template(target_path: Path) -> Path:
    """生成并写入 `guide.html` 模板文件到指定路径。"""
    fig = create_timeline_with_tsp_wordcloud()
    banner_uri = _fig_to_data_uri(fig)
    plt.close(fig)

    html = build_guide_template(banner_uri)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(html, encoding="utf-8")
    return target_path


if __name__ == "__main__":
    print("正在生成 guide.html（含 TSP 时间轴 Banner）...")
    font_path = get_chinese_font_path()
    if font_path:
        print(f"找到中文字体: {font_path}")

    project_root = Path(__file__).resolve().parent
    template_path = project_root / "traversal" / "templates" / "traversal" / "guide.html"
    out = write_guide_template(template_path)
    print(f"已生成: {out}")
    print("完成！")