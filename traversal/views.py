# traversal/views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.http import FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import os
import sys
import time
import hashlib
import math
import statistics
from datetime import datetime
from pathlib import Path
import zipfile
import folium

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from network import (
        load_line_colors,
        load_station_data,
        build_subway_network,
        render_network_topology_image,
        render_planned_path_image,
        render_network1_topology_image,
        render_network1_planned_image,
        build_network1_layout,
    )

    print("[OK] network 模块导入成功")
except ImportError as e:
    print(f"[ERR] network 模块导入失败: {e}")
    # 尝试其他路径
    alt_path = os.path.join(BASE_DIR, '..')
    if alt_path not in sys.path:
        sys.path.insert(0, alt_path)
    try:
        from network import (
            load_line_colors,
            load_station_data,
            build_subway_network,
            render_network_topology_image,
            render_planned_path_image,
            render_network1_topology_image,
            render_network1_planned_image,
            build_network1_layout,
        )

        print("[OK] 从备用路径导入成功")
    except ImportError:
        print("[ERR] 无法导入 network 模块")

from .algorithm import SubwayAlgorithm

# 全局实例
_algorithm = None
_topology_pos = None

OUTPUT_DIR = Path(BASE_DIR) / "outputs"
ALGORITHM_LABELS = {
    'greedy': '启发式优化算法：贪心算法',
    'dynamic_programming': '动态规划算法',
    'dijkstra': '最短路启发：Dijkstra',
    'bfs': '图遍历算法：广度优先（BFS）',
    'dfs': '图遍历算法：深度优先（DFS）',
    'genetic': '群体搜索元启发式：遗传算法',
    'ant_colony': '仿生优化算法：蚁群算法',
}


def _append_change_log(entry: dict):
    """将每次路径计算变更记录追加到日志文档。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log_path = OUTPUT_DIR / "change_log.txt"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "=" * 80,
        f"时间: {ts}",
        f"模式: {entry.get('mode', '')}",
        f"算法: {entry.get('algorithm', '')}",
        f"起点: {entry.get('start_station', '')}",
        f"终点: {entry.get('end_station', '')}",
        f"访问站点数: {entry.get('unique_stations', '')}",
        f"路径总站点: {entry.get('total_stations', '')}",
        f"换乘段数: {entry.get('segments_count', '')}",
        f"耗时(秒): {entry.get('time', '')}",
        "产物文件:",
        f"  - 报告: {entry.get('report_file', '')}",
        f"  - 完整拓扑: {entry.get('full_topology_file', '')}",
        f"  - 规划拓扑: {entry.get('planned_topology_file', '')}",
        f"  - 打包文件: {entry.get('bundle_file', '')}",
        "",
    ]
    with log_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _build_run_readme(result: dict, zip_filename: str) -> str:
    """为每次计算生成 README 文档。"""
    lines = [
        "合肥地铁路径规划结果说明",
        "=" * 30,
        "",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"任务模式: {'全站遍历' if result.get('mode') == 'traversal' else '任意两站最短路径'}",
        f"算法名称: {result.get('algorithm_label', result.get('algorithm', ''))}",
        f"起点站点: {result.get('start_station', '')}",
        f"终点站点: {result.get('end_station', '')}",
        "",
        "文件说明:",
        "- *.txt: 详细路径与换乘分段报告",
        "- *_full_topology.png: 全网络拓扑图",
        "- *_planned_topology.png: 本次规划高亮图",
        f"- {zip_filename}: 当前文件打包结果",
        "",
        "指标说明:",
        "- 访问站点: 去重后到达过的站点数",
        "- 路径长度: 路径序列中的总站点数（可包含重复站）",
        "- 换乘次数: 分段数 - 1",
        "- 计算耗时: 后端单次算法计算时间",
        "",
        "备注:",
        "- 线路/站点高亮与悬停信息在页面中为实时交互展示。",
    ]
    return "\n".join(lines)


def get_algorithm():
    global _algorithm, _topology_pos
    if _algorithm is None:
        print("正在加载地铁数据...")
        stations_file = os.path.join(BASE_DIR, 'station_coordinates_complete.txt')
        colors_file = os.path.join(BASE_DIR, 'line_color.txt')

        print(f"站点文件: {stations_file}")
        print(f"颜色文件: {colors_file}")

        if not os.path.exists(stations_file):
            print(f"[ERR] 文件不存在: {stations_file}")
            return None

        stations, line_stations = load_station_data(stations_file)
        line_colors = load_line_colors(colors_file)
        G = build_subway_network(stations, line_stations, line_colors)
        _algorithm = SubwayAlgorithm(G, stations, line_stations, line_colors)
        # 与 network1.py 保持一致：使用 Kamada-Kawai 作为前端拓扑坐标源
        _topology_pos = build_network1_layout(G)
        print("加载完成!")
    return _algorithm


def _haversine_km(lon1, lat1, lon2, lat2):
    """按经纬度计算两点球面距离（公里）。"""
    r = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = p2 - p1
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * (math.sin(dlon / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


def _build_guide_context():
    """构建引导大屏地图与统计数据。"""
    stations_file = os.path.join(BASE_DIR, 'station_coordinates_complete.txt')
    colors_file = os.path.join(BASE_DIR, 'line_color.txt')
    stations, line_stations = load_station_data(stations_file)
    line_colors = load_line_colors(colors_file)

    all_lats = [v[1] for v in stations.values()]
    all_lons = [v[0] for v in stations.values()]
    center_lat = sum(all_lats) / len(all_lats)
    center_lon = sum(all_lons) / len(all_lons)

    station_to_lines = {}
    for line_num, line_nodes in line_stations.items():
        for st in line_nodes:
            station_to_lines.setdefault(st, []).append(line_num)

    two_transfer = sum(1 for lines in station_to_lines.values() if len(lines) == 2)
    three_transfer = sum(1 for lines in station_to_lines.values() if len(lines) == 3)
    normal_count = sum(1 for lines in station_to_lines.values() if len(lines) == 1)

    total_length = 0.0
    line_lengths = {}
    for line_num, line_nodes in line_stations.items():
        length = 0.0
        for i in range(len(line_nodes) - 1):
            a = stations.get(line_nodes[i])
            b = stations.get(line_nodes[i + 1])
            if not a or not b:
                continue
            length += _haversine_km(a[0], a[1], b[0], b[1])
        line_lengths[line_num] = length
        total_length += length
    avg_line_length = total_length / max(len(line_stations), 1)

    fmap = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11.7,
        tiles="cartodb dark_matter",
        control_scale=True,
        prefer_canvas=True,
    )

    for line_num, line_nodes in line_stations.items():
        path_points = []
        for st in line_nodes:
            if st in stations:
                lon, lat = stations[st]
                path_points.append([lat, lon])
        if len(path_points) > 1:
            folium.PolyLine(
                locations=path_points,
                color=line_colors.get(line_num, "#bfbfbf"),
                weight=5,
                opacity=0.9,
                tooltip=f"{line_num}号线"
            ).add_to(fmap)

    for station_name, (lon, lat) in stations.items():
        lines = sorted(station_to_lines.get(station_name, []))
        if len(lines) <= 1:
            line_num = lines[0] if lines else None
            color = line_colors.get(line_num, "#6ee7ff")
            folium.CircleMarker(
                location=[lat, lon],
                radius=5,
                color="#ffffff",
                weight=1,
                fill=True,
                fill_color=color,
                fill_opacity=0.95,
                tooltip=f"{station_name} · {line_num}号线" if line_num else station_name,
            ).add_to(fmap)
            continue

        ring_colors = [line_colors.get(line_num, "#bfbfbf") for line_num in lines]
        deg = 360 / max(len(ring_colors), 1)
        segments = []
        start_deg = 0
        for c in ring_colors:
            end_deg = start_deg + deg
            segments.append(f"{c} {start_deg:.2f}deg {end_deg:.2f}deg")
            start_deg = end_deg
        gradient = ", ".join(segments)
        line_text = " / ".join([f"{x}号线" for x in lines])
        html = f"""
        <div style="width:18px;height:18px;border-radius:50%;
                    border:1px solid #ffffff;
                    background: conic-gradient({gradient});
                    box-shadow: 0 0 8px rgba(255,255,255,.55);">
        </div>
        """
        folium.Marker(
            location=[lat, lon],
            icon=folium.DivIcon(html=html),
            tooltip=f"{station_name} · 换乘站 ({line_text})",
        ).add_to(fmap)

        folium.map.Marker(
            [lat, lon],
            icon=folium.DivIcon(
                html=f'<div style="color:#dbeafe;font-size:10px;font-weight:600;text-shadow:0 0 4px #000;">{station_name}</div>'
            )
        ).add_to(fmap)

    legend_rows = []
    for line_num in sorted(line_stations.keys()):
        color = line_colors.get(line_num, "#bfbfbf")
        legend_rows.append(
            f'<div style="display:flex;align-items:center;margin:4px 0;">'
            f'<span style="display:inline-block;width:14px;height:14px;border-radius:3px;background:{color};margin-right:8px;"></span>'
            f'<span style="color:#e2e8f0;">{line_num}号线</span>'
            f'</div>'
        )
    legend_html = (
        '<div style="position: fixed; bottom: 22px; left: 22px; z-index: 9999;'
        'background: rgba(2, 6, 23, 0.88); border: 1px solid rgba(148,163,184,.35);'
        'border-radius: 10px; padding: 10px 12px; min-width: 120px;">'
        '<div style="color:#67e8f9;font-weight:700;margin-bottom:6px;">线路图例</div>'
        + "".join(legend_rows)
        + '</div>'
    )
    fmap.get_root().html.add_child(folium.Element(legend_html))

    return {
        "map_html": fmap._repr_html_(),
        "line_count": len(line_stations),
        "station_count": len(stations),
        "normal_station_count": normal_count,
        "transfer_2_count": two_transfer,
        "transfer_3_count": three_transfer,
        "single_line_km": round(avg_line_length, 2),
        "total_line_km": round(total_length, 2),
    }


def guide(request):
    """项目启动引导页。"""
    return render(request, 'traversal/guide.html')


def index(request):
    """原主页面（保留算法与对比完整功能）。"""
    return render(request, 'traversal/index.html')


def _build_real_network_map_html(stations, line_stations, line_colors):
    """构建浅色真实坐标地铁网络图（用于 graph 页面缩略图）。"""
    all_lats = [v[1] for v in stations.values()]
    all_lons = [v[0] for v in stations.values()]
    center_lat = sum(all_lats) / len(all_lats)
    center_lon = sum(all_lons) / len(all_lons)

    station_to_lines = {}
    for line_num, line_nodes in line_stations.items():
        for st in line_nodes:
            station_to_lines.setdefault(st, []).append(line_num)

    fmap = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11.4,
        tiles="cartodb positron",
        control_scale=True,
        prefer_canvas=True,
    )

    for line_num, line_nodes in line_stations.items():
        points = []
        for st in line_nodes:
            if st in stations:
                lon, lat = stations[st]
                points.append([lat, lon])
        if len(points) > 1:
            folium.PolyLine(
                locations=points,
                color=line_colors.get(line_num, "#9ca3af"),
                weight=4,
                opacity=0.95,
                tooltip=f"{line_num}号线",
            ).add_to(fmap)

    for station_name, (lon, lat) in stations.items():
        lines = sorted(station_to_lines.get(station_name, []))
        if len(lines) <= 1:
            color = line_colors.get(lines[0], "#2563eb") if lines else "#2563eb"
            folium.CircleMarker(
                location=[lat, lon],
                radius=4,
                color="#ffffff",
                weight=1,
                fill=True,
                fill_color=color,
                fill_opacity=0.95,
                tooltip=station_name,
            ).add_to(fmap)
            continue

        ring_colors = [line_colors.get(line_num, "#9ca3af") for line_num in lines]
        deg = 360 / max(len(ring_colors), 1)
        parts = []
        start_deg = 0
        for c in ring_colors:
            end_deg = start_deg + deg
            parts.append(f"{c} {start_deg:.2f}deg {end_deg:.2f}deg")
            start_deg = end_deg
        gradient = ", ".join(parts)
        folium.Marker(
            location=[lat, lon],
            icon=folium.DivIcon(
                html=(
                    "<div style='width:12px;height:12px;border-radius:50%;"
                    "border:1px solid #fff;"
                    f"background:conic-gradient({gradient});'></div>"
                )
            ),
            tooltip=f"{station_name}（换乘）",
        ).add_to(fmap)
    return fmap._repr_html_()


def graph(request):
    """图拓扑展示页。"""
    global _topology_pos
    algo = get_algorithm()
    if not algo:
        return render(request, 'traversal/graph.html', {'error': '算法未初始化'})
    if _topology_pos is None:
        _topology_pos = build_network1_layout(algo.G)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    topology_file = "graph_topology_main.png"
    render_network1_topology_image(
        algo.G,
        algo.stations,
        algo.line_stations,
        algo.line_colors,
        OUTPUT_DIR / topology_file,
        pos=_topology_pos,
        show_legend=True,
        dpi=200,
    )

    line_station_dict = {f"{k}号线": v for k, v in sorted(algo.line_stations.items(), key=lambda x: x[0])}
    adjacency = {}
    for node in sorted(algo.G.nodes()):
        neighbors = sorted(list(algo.G.neighbors(node)))
        adjacency[node] = neighbors
    adjacency_preview = dict(list(adjacency.items())[:35])

    context = {
        "topology_file": topology_file,
        "mini_map_html": _build_real_network_map_html(algo.stations, algo.line_stations, algo.line_colors),
        "node_count": algo.G.number_of_nodes(),
        "edge_count": algo.G.number_of_edges(),
        "line_count": len(algo.line_stations),
        "line_station_json": json.dumps(line_station_dict, ensure_ascii=False, indent=2),
        "adjacency_json": json.dumps(adjacency_preview, ensure_ascii=False, indent=2),
    }
    return render(request, 'traversal/graph.html', context)


def algorithm_page(request):
    """算法页面：直接复用原功能页，避免 iframe 连接问题。"""
    return render(request, 'traversal/index.html')


def get_stations(request):
    """获取所有站点列表"""
    algo = get_algorithm()
    if not algo:
        return JsonResponse({'stations': [], 'error': '算法未初始化'}, status=500)

    keyword = request.GET.get('keyword', '')
    if keyword:
        stations = algo.search_station(keyword)
    else:
        stations = algo.all_stations[:100]
    return JsonResponse({'stations': stations})


def get_network(request):
    """获取网络拓扑数据"""
    global _topology_pos
    algo = get_algorithm()
    if not algo:
        return JsonResponse({'error': '算法未初始化'}, status=500)
    if _topology_pos is None:
        _topology_pos = build_network1_layout(algo.G)

    nodes = []
    xs = [float(p[0]) for p in _topology_pos.values()] if _topology_pos else [0.0]
    ys = [float(p[1]) for p in _topology_pos.values()] if _topology_pos else [0.0]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)
    for station in algo.stations.keys():
        pos = _topology_pos.get(station, (0.0, 0.0))
        x = float(pos[0])
        y = float(pos[1])
        nodes.append({
            'name': station,
            'x': x,
            'y': y,
            'x_norm': (x - min_x) / span_x,
            'y_norm': (y - min_y) / span_y,
            'lines': algo.get_station_lines(station),
            'is_transfer': len(algo.get_station_lines(station)) > 1
        })

    edges = []
    for u, v in algo.G.edges():
        edges.append({
            'from': u,
            'to': v,
            'line': algo.G[u][v]['line']
        })

    # 左图：直接使用 network1.py 风格输出
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_filename = "network1_thumb_topology.png"
    main_filename = "network1_main_topology.png"
    base_path = OUTPUT_DIR / base_filename
    main_path = OUTPUT_DIR / main_filename
    render_network1_topology_image(
        algo.G, algo.stations, algo.line_stations, algo.line_colors,
        base_path, pos=_topology_pos, show_legend=False
    )
    render_network1_topology_image(
        algo.G, algo.stations, algo.line_stations, algo.line_colors,
        main_path, pos=_topology_pos, show_legend=True
    )

    return JsonResponse({
        'nodes': nodes,
        'edges': edges,
        'line_colors': algo.line_colors,
        'line_stations': {str(k): v for k, v in algo.line_stations.items()},
        'total_stations': algo.total_stations,
        'base_topology_file': base_filename,
        'main_topology_file': main_filename,
    })


def _resolve_station_for_highlight(algo, raw: str):
    """将输入解析为图中精确站名；无法解析则返回 None。"""
    raw = (raw or "").strip()
    if not raw:
        return None
    matches = algo.search_station(raw)
    return matches[0] if matches else None


@require_http_methods(["GET"])
def get_network_highlight(request):
    """根据下拉线路/站点与输入框标记，生成主拓扑高亮预览（较低 dpi 以加快响应）。"""
    global _topology_pos
    algo = get_algorithm()
    if not algo:
        return JsonResponse({'error': '算法未初始化'}, status=500)
    if _topology_pos is None:
        _topology_pos = build_network1_layout(algo.G)

    d_sl = request.GET.get("d_sl", "").strip()
    d_ss = request.GET.get("d_ss", "").strip()
    d_el = request.GET.get("d_el", "").strip()
    d_es = request.GET.get("d_es", "").strip()
    m_s = request.GET.get("m_s", "").strip()
    m_e = request.GET.get("m_e", "").strip()

    d_start_line = int(d_sl) if d_sl.isdigit() else None
    d_end_line = int(d_el) if d_el.isdigit() else None
    d_start_station = d_ss or None
    d_end_station = d_es or None
    mark_start = _resolve_station_for_highlight(algo, m_s)
    mark_end = _resolve_station_for_highlight(algo, m_e)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cache_key = "|".join(
        [
            str(d_start_line or ""),
            d_start_station or "",
            str(d_end_line or ""),
            d_end_station or "",
            mark_start or "",
            mark_end or "",
        ]
    )
    h = hashlib.md5(cache_key.encode("utf-8")).hexdigest()[:20]
    filename = f"network1_highlight_{h}.png"
    render_network1_topology_image(
        algo.G,
        algo.stations,
        algo.line_stations,
        algo.line_colors,
        OUTPUT_DIR / filename,
        pos=_topology_pos,
        d_start_line=d_start_line,
        d_start_station=d_start_station,
        d_end_line=d_end_line,
        d_end_station=d_end_station,
        mark_start=mark_start,
        mark_end=mark_end,
        show_legend=True,
        dpi=140,
    )
    return JsonResponse({'file': filename})


@csrf_exempt
@require_http_methods(["POST"])
def calculate_path(request):
    """计算遍历路径"""
    try:
        data = json.loads(request.body)
        start = data.get('start', '')
        end = data.get('end', '')
        mode = (data.get('mode') or 'traversal').strip()
        algo_name = (data.get('algorithm') or 'greedy').strip()

        algo = get_algorithm()
        if not algo:
            return JsonResponse({'error': '算法未初始化'}, status=500)

        if algo_name not in ALGORITHM_LABELS:
            return JsonResponse({'error': f'暂不支持算法: {algo_name}'}, status=400)

        # 验证起点
        start_matches = algo.search_station(start)
        if not start_matches:
            return JsonResponse({'error': f'未找到站点: {start}'}, status=400)

        start_station = start_matches[0]
        end_station = ''
        if end:
            end_matches = algo.search_station(end)
            if not end_matches:
                return JsonResponse({'error': f'未找到站点: {end}'}, status=400)
            end_station = end_matches[0]

        if mode == 'shortest_path':
            if not end_station:
                return JsonResponse({'error': '最短路径模式必须填写终点站'}, status=400)
            result = algo.find_shortest_path(start_station, end_station)
            result['algorithm_label'] = '最短路径算法：Dijkstra'
        else:
            result = algo.find_path(
                start_station,
                end=end_station or None,
                algorithm_name=algo_name,
                return_to_start=not end_station,
            )
            result['algorithm_label'] = ALGORITHM_LABELS[algo_name]

        # 生成报告与两张图，并打包为 zip 文件
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        safe_start = "".join(ch for ch in start_station if ch.isalnum() or ch in ("-", "_", "·"))
        safe_end = "".join(ch for ch in result['end_station'] if ch.isalnum() or ch in ("-", "_", "·"))
        artifact_stem = f"hefei_subway_plan_{algo_name}_{safe_start}_{safe_end}_{ts}"

        report_filename = f"{artifact_stem}.txt"
        readme_filename = f"{artifact_stem}_readme.txt"
        full_topology_filename = f"{artifact_stem}_full_topology.png"
        planned_topology_filename = f"{artifact_stem}_planned_topology.png"
        zip_filename = f"{artifact_stem}.zip"

        report_path = OUTPUT_DIR / report_filename
        readme_path = OUTPUT_DIR / readme_filename
        full_topology_path = OUTPUT_DIR / full_topology_filename
        planned_topology_path = OUTPUT_DIR / planned_topology_filename
        zip_path = OUTPUT_DIR / zip_filename

        report_text = algo.build_report_text(result, result['algorithm_label'])
        report_path.write_text(report_text, encoding="utf-8")
        readme_path.write_text(_build_run_readme(result, zip_filename), encoding="utf-8")
        render_network1_topology_image(
            algo.G, algo.stations, algo.line_stations, algo.line_colors,
            full_topology_path, pos=_topology_pos
        )
        render_network1_planned_image(
            algo.G,
            algo.stations,
            algo.line_stations,
            algo.line_colors,
            result['path'],
            result['segments'],
            result['start_station'],
            result['end_station'],
            planned_topology_path,
            pos=_topology_pos,
        )

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(report_path, arcname=report_filename)
            archive.write(readme_path, arcname=readme_filename)
            archive.write(full_topology_path, arcname=full_topology_filename)
            archive.write(planned_topology_path, arcname=planned_topology_filename)

        result['report_file'] = report_filename
        result['readme_file'] = readme_filename
        result['full_topology_file'] = full_topology_filename
        result['planned_topology_file'] = planned_topology_filename
        result['bundle_file'] = zip_filename
        _append_change_log({
            "mode": result.get("mode", mode),
            "algorithm": result.get("algorithm_label", algo_name),
            "start_station": result.get("start_station", start_station),
            "end_station": result.get("end_station", end_station),
            "unique_stations": result.get("unique_stations", ""),
            "total_stations": result.get("total_stations", ""),
            "segments_count": len(result.get("segments", []) or []),
            "time": result.get("time", ""),
            "report_file": report_filename,
            "readme_file": readme_filename,
            "full_topology_file": full_topology_filename,
            "planned_topology_file": planned_topology_filename,
            "bundle_file": zip_filename,
        })

        return JsonResponse(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def compare_algorithms(request):
    """对比四种遍历算法性能（统一起终点）。"""
    try:
        data = json.loads(request.body)
        start = (data.get('start') or '').strip()
        end = (data.get('end') or '').strip()
        mode = (data.get('mode') or 'traversal').strip()
        rounds = int(data.get('rounds', 5))
        rounds = max(3, min(rounds, 12))

        if mode != 'traversal':
            return JsonResponse({'error': '算法性能对比仅支持“全站遍历”模式'}, status=400)

        algo = get_algorithm()
        if not algo:
            return JsonResponse({'error': '算法未初始化'}, status=500)

        start_matches = algo.search_station(start)
        if not start_matches:
            return JsonResponse({'error': f'未找到站点: {start}'}, status=400)
        start_station = start_matches[0]

        end_station = ''
        if end:
            end_matches = algo.search_station(end)
            if not end_matches:
                return JsonResponse({'error': f'未找到站点: {end}'}, status=400)
            end_station = end_matches[0]

        compare_rows = []
        for algo_name, algo_label in ALGORITHM_LABELS.items():
            elapsed_samples = []
            result = None
            for _ in range(rounds):
                t0 = time.perf_counter()
                result = algo.find_path(
                    start_station,
                    end=end_station or None,
                    algorithm_name=algo_name,
                    return_to_start=not end_station,
                )
                elapsed_samples.append(time.perf_counter() - t0)

            avg_elapsed = sum(elapsed_samples) / len(elapsed_samples)
            std_elapsed = statistics.pstdev(elapsed_samples) if len(elapsed_samples) > 1 else 0.0
            compare_rows.append({
                'algorithm': algo_name,
                'algorithm_label': algo_label,
                'time_avg': round(avg_elapsed, 5),
                'time_min': round(min(elapsed_samples), 5),
                'time_max': round(max(elapsed_samples), 5),
                'time_std': round(std_elapsed, 5),
                'total_stations': result.get('total_stations'),
                'unique_stations': result.get('unique_stations'),
                'total_distance': result.get('total_distance'),
                'transfer_count': max(len(result.get('segments', []) or []) - 1, 0),
                'is_complete': bool(result.get('is_complete')),
                'samples': rounds,
            })

        compare_rows.sort(key=lambda row: (row['time_avg'], row['time_std']))
        _append_change_log({
            "mode": "algorithm_compare",
            "algorithm": f"对比{len(compare_rows)}种算法",
            "start_station": start_station,
            "end_station": end_station or start_station,
            "unique_stations": "",
            "total_stations": "",
            "segments_count": "",
            "time": f"rounds={rounds}",
            "report_file": "",
            "full_topology_file": "",
            "planned_topology_file": "",
            "bundle_file": "",
        })
        return JsonResponse({
            'start_station': start_station,
            'end_station': end_station or start_station,
            'rounds': rounds,
            'rows': compare_rows,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def download_report(request, filename: str):
    """下载服务端生成的报告文件"""
    # 基础的路径穿越防护：只允许文件名，不允许子路径
    if "/" in filename or "\\" in filename or ".." in filename:
        raise Http404("Invalid filename")

    path = OUTPUT_DIR / filename
    if not path.exists() or not path.is_file():
        raise Http404("File not found")

    return FileResponse(open(path, "rb"), as_attachment=True, filename=filename)


@require_http_methods(["GET"])
def view_output_file(request, filename: str):
    """页面内预览输出文件（图片）"""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise Http404("Invalid filename")
    path = OUTPUT_DIR / filename
    if not path.exists() or not path.is_file():
        raise Http404("File not found")
    return FileResponse(open(path, "rb"), as_attachment=False, filename=filename)