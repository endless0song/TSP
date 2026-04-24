import re
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict
from pathlib import Path

# --- 设置中文字体 ---
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def load_line_colors(filename):
    """从 line_color.txt 加载线路颜色"""
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    matches = re.findall(r'#(\d+):#([A-Fa-f0-9]{6})', content)
    return {int(line): '#' + color for line, color in matches}


def load_station_data(filename):
    """从 station_coordinates_complete.txt 加载站点和线路数据"""
    stations = {}  # 站点名 -> (经度, 纬度)
    line_stations = {}  # 线路号 -> [站点列表]

    with open(filename, 'r', encoding='utf-8') as f:
        current_line = None
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            line_match = re.match(r'(\d+)号线:', line)
            if line_match:
                current_line = int(line_match.group(1))
                line_stations[current_line] = []
                continue

            station_match = re.match(r'([^,]+),([\d.]+),([\d.]+)', line)
            if station_match and current_line is not None:
                name, lon, lat = station_match.groups()
                stations[name] = (float(lon), float(lat))
                line_stations[current_line].append(name)

    return stations, line_stations


def build_subway_network(stations, line_stations, line_colors):
    """
    构建 NetworkX 图
    """
    G = nx.Graph()

    # 1. 添加所有站点作为节点
    for station, (lon, lat) in stations.items():
        G.add_node(station, pos=(lon, lat))

    # 2. 为每条线路添加边
    for line_num, station_list in line_stations.items():
        color = line_colors.get(line_num, 'black')
        for i in range(len(station_list) - 1):
            station_a = station_list[i]
            station_b = station_list[i + 1]
            if station_a in G and station_b in G:
                G.add_edge(station_a, station_b, line=line_num, color=color)

    return G


def build_geo_positions(stations):
    """使用站点经纬度作为静态拓扑坐标。"""
    return {station: (pos[0], pos[1]) for station, pos in stations.items()}


def _draw_base_network(ax, G, pos, line_stations, line_colors, alpha=0.9):
    for line_num in sorted(line_stations.keys()):
        line_graph = nx.Graph()
        for u, v in G.edges():
            if G[u][v]['line'] == line_num:
                line_graph.add_edge(u, v)

        color = line_colors.get(line_num, 'black')
        nx.draw_networkx_edges(
            line_graph, pos,
            edge_color=color,
            width=3.2,
            alpha=alpha,
            ax=ax
        )

    all_nodes = list(G.nodes())
    normal_nodes = []
    transfer_nodes = []
    for node in all_nodes:
        lines_here = [line for line, stations_list in line_stations.items() if node in stations_list]
        if len(lines_here) > 1:
            transfer_nodes.append(node)
        else:
            normal_nodes.append(node)

    if normal_nodes:
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=normal_nodes,
            node_color='white',
            node_size=85,
            edgecolors='black',
            linewidths=0.6,
            ax=ax
        )

    if transfer_nodes:
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=transfer_nodes,
            node_color='white',
            node_size=210,
            edgecolors='black',
            linewidths=0.8,
            ax=ax
        )

    # 只给换乘站标注文字，避免全站点标签造成视觉发白和不可读
    for node, (x, y) in pos.items():
        lines_here = [line for line, stations_list in line_stations.items() if node in stations_list]
        if len(lines_here) <= 1:
            continue
        fontsize = 8.0
        offset = 0.005
        ax.text(
            x + offset, y - offset, node,
            fontsize=fontsize,
            ha='left', va='top',
            color='black',
            zorder=10,
            fontfamily='SimHei'
        )

    ax.set_aspect('equal')
    ax.axis('off')
    ax.margins(0.12)


def render_network_topology_image(G, stations, line_stations, line_colors, output_file):
    """生成完整地铁网络拓扑图。"""
    pos = build_geo_positions(stations)
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(1, 1, figsize=(16, 10))
    _draw_base_network(ax, G, pos, line_stations, line_colors, alpha=0.95)
    ax.set_title('合肥地铁完整网络拓扑', fontsize=18, fontfamily='SimHei')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    return str(output_path)


def render_planned_path_image(
    G, stations, line_stations, line_colors, path, segments, start_station, end_station, output_file
):
    """生成路径规划图：完整网络为底图，规划结果按分段高亮。"""
    pos = build_geo_positions(stations)
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(1, 1, figsize=(16, 10))
    _draw_base_network(ax, G, pos, line_stations, line_colors, alpha=0.18)

    for seg in segments:
        seg_edges = list(zip(seg['stations'][:-1], seg['stations'][1:]))
        nx.draw_networkx_edges(
            G, pos,
            edgelist=seg_edges,
            edge_color=seg['color'],
            width=6.0,
            alpha=0.95,
            ax=ax
        )
        mid_index = max(0, (len(seg['stations']) - 1) // 2)
        label_station = seg['stations'][mid_index]
        x, y = pos[label_station]
        ax.text(
            x, y + 0.006, f"第{seg['id']}段",
            fontsize=9,
            ha='center',
            va='bottom',
            color=seg['color'],
            bbox={'facecolor': 'white', 'edgecolor': seg['color'], 'boxstyle': 'round,pad=0.2'},
            zorder=20,
            fontfamily='SimHei'
        )

    path_set = set(path)
    interior_nodes = [node for node in path_set if node not in {start_station, end_station}]
    if interior_nodes:
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=interior_nodes,
            node_color='#ffd166',
            node_size=85,
            edgecolors='#333333',
            linewidths=0.6,
            ax=ax
        )

    if start_station:
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=[start_station],
            node_color='#2e7d32',
            node_size=180,
            edgecolors='white',
            linewidths=1.2,
            ax=ax
        )
        x, y = pos[start_station]
        ax.text(x, y + 0.01, '起点', fontsize=10, color='#2e7d32', ha='center', fontfamily='SimHei')

    if end_station:
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=[end_station],
            node_color='#c62828',
            node_size=180,
            edgecolors='white',
            linewidths=1.2,
            ax=ax
        )
        x, y = pos[end_station]
        ax.text(x, y + 0.01, '终点', fontsize=10, color='#c62828', ha='center', fontfamily='SimHei')

    ax.set_title('合肥地铁线路规划图', fontsize=18, fontfamily='SimHei')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    return str(output_path)


def build_network1_layout(G):
    """与 network1.py 一致的拓扑布局。"""
    return nx.kamada_kawai_layout(G, weight=None, scale=1.0, center=(0.5, 0.5))


def _primary_line_for_station(station, line_stations):
    """站点在数据中的首条所属线路（排序与绘图一致）。"""
    if not station:
        return None
    for line_num in sorted(line_stations.keys()):
        if station in line_stations[line_num]:
            return line_num
    return None


def _draw_network1_style(
    ax,
    G,
    pos,
    line_stations,
    line_colors,
    gray=False,
    d_start_line=None,
    d_start_station=None,
    d_end_line=None,
    d_end_station=None,
    mark_start=None,
    mark_end=None,
    show_legend=True,
):
    """
    交互高亮：
    - 下拉选定站点（d_*_station）时：所属线路灰暗，其余更淡。
    - 仅下拉线路未选站时：对应线路彩色，其余暗淡。
    - 仅输入框站点（mark_*）而无下拉站点：保持全路网彩色（与旧版一致），仅绘起终点标记。
    """
    station_ctx = set()
    for st in (d_start_station, d_end_station):
        ln = _primary_line_for_station(st, line_stations)
        if ln is not None:
            station_ctx.add(ln)

    line_only = set()
    if not d_start_station and d_start_line is not None:
        line_only.add(int(d_start_line))
    if not d_end_station and d_end_line is not None:
        line_only.add(int(d_end_line))

    interactive = bool(station_ctx or line_only)
    text_dim = interactive or gray

    # 3. 绘制所有线路（边）
    for line_num in sorted(line_stations.keys()):
        line_graph = nx.Graph()
        for u, v in G.edges():
            if G[u][v]['line'] == line_num:
                line_graph.add_edge(u, v)

        if line_num in station_ctx:
            color, alpha = '#8d8d8d', 0.72
        elif line_num in line_only:
            color = line_colors.get(line_num, 'black')
            alpha = 0.95
        elif station_ctx or line_only:
            color, alpha = '#d3d3d3', 0.32
        else:
            color = '#b8b8b8' if gray else line_colors.get(line_num, 'black')
            alpha = 0.9 if not gray else 0.55

        nx.draw_networkx_edges(
            line_graph, pos,
            edge_color=color,
            width=2.0,
            alpha=alpha,
            ax=ax
        )

    # 4. 换乘站彩环
    all_nodes = list(G.nodes())
    for node in all_nodes:
        lines_here = [line for line, stations_list in line_stations.items() if node in stations_list]
        if len(lines_here) > 1:
            x, y = pos[node]
            num_lines = len(lines_here)
            angles = np.linspace(0, 2 * np.pi, num_lines + 1)
            for i, line_num in enumerate(lines_here):
                if line_num in station_ctx:
                    wcolor = '#8d8d8d'
                elif line_num in line_only:
                    wcolor = line_colors.get(line_num, 'gray')
                elif station_ctx or line_only:
                    wcolor = '#d6d6d6'
                else:
                    wcolor = '#cccccc' if gray else line_colors.get(line_num, 'gray')
                wedge = plt.matplotlib.patches.Wedge(
                    (x, y), 0.025,
                    np.degrees(angles[i]), np.degrees(angles[i + 1]),
                    width=0.008,
                    facecolor=wcolor,
                    edgecolor='none',
                    alpha=0.85
                )
                ax.add_patch(wedge)

    # 5. 站点
    normal_nodes = []
    transfer_nodes = []
    for node in all_nodes:
        lines_here = [line for line, stations_list in line_stations.items() if node in stations_list]
        if len(lines_here) == 1:
            normal_nodes.append(node)
        else:
            transfer_nodes.append(node)

    if normal_nodes:
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=normal_nodes,
            node_color='white' if not gray else '#f5f5f5',
            node_size=35,
            edgecolors='black' if not gray else '#9e9e9e',
            linewidths=0.3,
            ax=ax
        )

    if transfer_nodes:
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=transfer_nodes,
            node_color='white' if not gray else '#f5f5f5',
            node_size=120,
            edgecolors='black' if not gray else '#9e9e9e',
            linewidths=0.3,
            ax=ax
        )

    # 6. 全量站名标注（与 network1.py 风格一致）
    for node, (x, y) in pos.items():
        lines_here = [line for line, stations_list in line_stations.items() if node in stations_list]
        if len(lines_here) == 1:
            text_fontsize = 3.5
            offset_x, offset_y = 0.004, -0.004
        else:
            text_fontsize = 4.5
            offset_x, offset_y = 0.006, -0.006
        ax.text(
            x + offset_x, y + offset_y, node,
            fontsize=text_fontsize,
            ha='left', va='top',
            color='black' if not text_dim else '#7f7f7f',
            zorder=10,
            fontfamily='SimHei'
        )

    # 下拉选定站：在标记层再强调一次（与灰暗线路一致）；已有绿/红输入标记时不再叠画
    for st, size in ((d_start_station, 220), (d_end_station, 220)):
        if st and st in pos:
            if st == mark_start or st == mark_end:
                continue
            nx.draw_networkx_nodes(
                G, pos,
                nodelist=[st],
                node_color='#ff7043',
                node_size=size,
                edgecolors='white',
                linewidths=1.2,
                ax=ax
            )

    # 输入框/同步后的起终点标记（绿/红）
    if mark_start and mark_start in pos:
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=[mark_start],
            node_color='#2e7d32',
            node_size=250,
            edgecolors='white',
            linewidths=1.4,
            ax=ax
        )
    if mark_end and mark_end in pos and mark_end != mark_start:
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=[mark_end],
            node_color='#c62828',
            node_size=250,
            edgecolors='white',
            linewidths=1.4,
            ax=ax
        )

    if show_legend:
        legend_lines = []
        legend_labels = []
        for line_num in sorted(line_stations.keys()):
            # 图例始终彩色显示
            color = line_colors.get(line_num, 'gray')
            line_label = f'{line_num}号线'
            legend_line, = ax.plot([], [], color=color, linewidth=3, label=line_label)
            legend_lines.append(legend_line)
            legend_labels.append(line_label)

        ax.legend(
            legend_lines, legend_labels,
            loc='center left',
            bbox_to_anchor=(1.01, 0.5),
            fontsize=12,
            title='合肥地铁线路',
            title_fontsize=14,
            frameon=True,
            shadow=True
        )
    ax.margins(0.12)
    ax.set_aspect('equal')
    ax.axis('off')


def render_network1_topology_image(
    G,
    stations,
    line_stations,
    line_colors,
    output_file,
    pos=None,
    d_start_line=None,
    d_start_station=None,
    d_end_line=None,
    d_end_station=None,
    mark_start=None,
    mark_end=None,
    show_legend=True,
    dpi=300,
):
    """直接输出 network1.py 风格完整拓扑图。"""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if pos is None:
        pos = build_network1_layout(G)

    fig, ax = plt.subplots(1, 1, figsize=(24, 18))
    _draw_network1_style(
        ax, G, pos, line_stations, line_colors, gray=False,
        d_start_line=d_start_line,
        d_start_station=d_start_station,
        d_end_line=d_end_line,
        d_end_station=d_end_station,
        mark_start=mark_start,
        mark_end=mark_end,
        show_legend=show_legend,
    )
    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi, bbox_inches='tight')
    plt.close(fig)
    return str(output_path)


def render_network1_planned_image(
    G, stations, line_stations, line_colors, path, segments, start_station, end_station, output_file, pos=None
):
    """左图灰度底图 + 高亮规划路径。"""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if pos is None:
        pos = build_network1_layout(G)

    fig, ax = plt.subplots(1, 1, figsize=(24, 18))
    _draw_network1_style(ax, G, pos, line_stations, line_colors, gray=True)

    for seg in segments:
        seg_edges = list(zip(seg['stations'][:-1], seg['stations'][1:]))
        nx.draw_networkx_edges(
            G, pos,
            edgelist=seg_edges,
            edge_color=seg['color'],
            width=4.5,
            alpha=0.98,
            ax=ax
        )
        mid_index = max(0, (len(seg['stations']) - 1) // 2)
        mid_station = seg['stations'][mid_index]
        mx, my = pos[mid_station]
        ax.text(
            mx, my + 0.015, f"第{seg['id']}段",
            fontsize=10,
            color=seg['color'],
            ha='center',
            va='bottom',
            bbox={'facecolor': 'white', 'edgecolor': seg['color'], 'boxstyle': 'round,pad=0.2'},
            fontfamily='SimHei'
        )

    # 高亮起终点
    if start_station in pos:
        nx.draw_networkx_nodes(
            G, pos, nodelist=[start_station],
            node_color='#2e7d32', node_size=220,
            edgecolors='white', linewidths=1.2, ax=ax
        )
    if end_station in pos:
        nx.draw_networkx_nodes(
            G, pos, nodelist=[end_station],
            node_color='#c62828', node_size=220,
            edgecolors='white', linewidths=1.2, ax=ax
        )

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    return str(output_path)


def visualize_network_with_force_layout(G, stations, line_stations, line_colors, output_file='hefei_subway_clear.png'):
    """
    使用力导向布局绘制地铁网络图
    """
    # 1. 使用 Kamada-Kawai 布局算法
    pos = nx.kamada_kawai_layout(G, weight=None, scale=1.0, center=(0.5, 0.5))

    # 2. 创建画布
    fig, ax = plt.subplots(1, 1, figsize=(24, 18))
    ax.margins(0.12)
    ax.set_aspect('equal')
    ax.axis('off')

    # 3. 绘制所有线路（边）- 使用真实颜色
    for line_num in sorted(line_stations.keys()):
        line_graph = nx.Graph()
        for u, v in G.edges():
            if G[u][v]['line'] == line_num:
                line_graph.add_edge(u, v)

        color = line_colors.get(line_num, 'black')
        nx.draw_networkx_edges(
            line_graph, pos,
            edge_color=color,
            width=2.0,
            alpha=0.9,
            ax=ax
        )

    # 4. 【优化】绘制站点 - 分离普通站和换乘站
    all_nodes = list(G.nodes())

    # 4.1 先绘制换乘站的彩色环（最底层）
    for node in all_nodes:
        lines_here = [line for line, stations_list in line_stations.items() if node in stations_list]
        if len(lines_here) > 1:  # 换乘站
            x, y = pos[node]
            # 按线路数量绘制彩色环（扇形）
            num_lines = len(lines_here)
            angles = np.linspace(0, 2 * np.pi, num_lines + 1)

            for i, line_num in enumerate(lines_here):
                color = line_colors.get(line_num, 'gray')
                # 绘制扇形
                theta1 = angles[i]
                theta2 = angles[i + 1]
                # 创建扇形路径
                wedge = plt.matplotlib.patches.Wedge(
                    (x, y), 0.025,  # 外半径
                    np.degrees(theta1), np.degrees(theta2),
                    width=0.008,  # 环的宽度
                    facecolor=color,
                    edgecolor='none',
                    alpha=0.9
                )
                ax.add_patch(wedge)

    # 4.2 绘制所有站点的白色圆圈（覆盖在色环上）
    # 分两次绘制：先普通站，再换乘站（换乘站在上层）

    # 普通站
    normal_nodes = []
    normal_pos = {}
    for node in all_nodes:
        lines_here = [line for line, stations_list in line_stations.items() if node in stations_list]
        if len(lines_here) == 1:
            normal_nodes.append(node)
            normal_pos[node] = pos[node]

    if normal_nodes:
        nx.draw_networkx_nodes(
            G, normal_pos,
            nodelist=normal_nodes,
            node_color='white',
            node_size=35,  # 大幅缩小普通站
            edgecolors='black',
            linewidths=0.3,
            ax=ax
        )

    # 换乘站（后绘制，在上层）
    transfer_nodes = []
    transfer_pos = {}
    for node in all_nodes:
        lines_here = [line for line, stations_list in line_stations.items() if node in stations_list]
        if len(lines_here) > 1:
            transfer_nodes.append(node)
            transfer_pos[node] = pos[node]

    if transfer_nodes:
        nx.draw_networkx_nodes(
            G, transfer_pos,
            nodelist=transfer_nodes,
            node_color='white',
            node_size=120,  # 增大换乘站
            edgecolors='black',
            linewidths=0.3,
            ax=ax
        )

    # 5. 【紧贴】文字标注：极小偏移量，紧贴站点
    for node, (x, y) in pos.items():
        lines_here = [line for line, stations_list in line_stations.items() if node in stations_list]
        if len(lines_here) == 1:
            # 普通站：小字体 + 极小偏移（紧贴！）
            text_fontsize = 3.5
            offset_x, offset_y = 0.004, -0.004  # 大幅缩小到0.004！
        else:
            # 换乘站：稍大字体 + 极小偏移（紧贴！）
            text_fontsize = 4.5
            offset_x, offset_y = 0.006, -0.006  # 大幅缩小到0.006！

        ax.text(
            x + offset_x, y + offset_y, node,
            fontsize=text_fontsize,
            ha='left', va='top',
            color='black',
            zorder=10,
            fontfamily='SimHei'
        )

    # 6. 创建图例
    legend_lines = []
    legend_labels = []

    for line_num in sorted(line_stations.keys()):
        color = line_colors.get(line_num, 'gray')
        line_label = f'{line_num}号线'

        legend_line, = ax.plot([], [], color=color, linewidth=3, label=line_label)
        legend_lines.append(legend_line)
        legend_labels.append(line_label)

    # 添加图例到右侧
    ax.legend(
        legend_lines, legend_labels,
        loc='center left',
        bbox_to_anchor=(1.01, 0.5),
        fontsize=12,
        title='合肥地铁线路',
        title_fontsize=14,
        frameon=True,
        shadow=True
    )

    # 7. 保存图像
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f" 力导向布局拓扑图已保存至: {output_file}")
    print(f"   - 普通站半径: 35 (大幅缩小)")
    print(f"   - 换乘站半径: 120 (增大对比)")
    print(f"   - 换乘站彩色环: 有 (扇形色环)")
    print(f"   - 文字偏移: 普通站0.004, 换乘站0.006 (紧贴!)")
    plt.show()


def main():
    # --- 第一步：加载数据 ---
    print(" 正在加载站点坐标...")
    stations, line_stations = load_station_data('station_coordinates_complete.txt')

    print(" 正在加载线路颜色...")
    line_colors = load_line_colors('line_color.txt')

    print(f" 共加载 {len(stations)} 个站点，{len(line_stations)} 条线路。")
    print(f"   线路列表: {sorted(line_stations.keys())}")

    # --- 第二步：构建网络图 ---
    print(" 正在构建地铁网络图...")
    G = build_subway_network(stations, line_stations, line_colors)
    print(f" 网络图构建完成！节点数: {G.number_of_nodes()}, 边数: {G.number_of_edges()}")

    # --- 第三步：可视化 ---
    print(" 正在生成力导向布局图...")
    visualize_network_with_force_layout(G, stations, line_stations, line_colors, 'hefei_subway_clear.png')

    # --- 第四步：进行遍历操作（示例）---
    print("\n" + "=" * 50)
    print("🔍 拓扑验证示例")
    print("=" * 50)

    try:
        path = nx.shortest_path(G, '洪岗', '市第三医院')
        print(f" 从 '洪岗' 到 '市第三医院' 的最短路径:")
        print(f"   {' -> '.join(path)}")
        print(f"   共 {len(path)} 个站点，{len(path) - 1} 段")
    except Exception as e:
        print(f" 路径查询出错: {e}")

    print("\n 所有操作完成！")
    return G


if __name__ == '__main__':
    subway_graph = main()