# traversal/algorithm.py
import networkx as nx
from collections import defaultdict
import time
import colorsys
from datetime import datetime
import random
from functools import lru_cache


class SubwayAlgorithm:
    """地铁算法核心类"""

    def __init__(self, G, stations, line_stations, line_colors):
        self.G = G
        self.stations = stations
        self.line_stations = line_stations
        self.line_colors = line_colors

        self.all_stations = list(stations.keys())
        self.total_stations = len(self.all_stations)

        # 站点到线路映射
        self.station_to_lines = defaultdict(list)
        for line_num, stations_list in line_stations.items():
            for station in stations_list:
                self.station_to_lines[station].append(line_num)

        # 预计算最短路径
        self.shortest_paths = {}
        self.shortest_distances = {}
        self.random_seed = 20260414
        self._precompute_paths()

    def _segment_color(self, idx: int) -> str:
        """
        为“第 idx 段”生成稳定且彼此区分的颜色。
        idx 从 1 开始。
        """
        # 用黄金比例共轭分布 hue，避免相邻段颜色过近
        h = (0.61803398875 * (idx - 1)) % 1.0
        s = 0.72
        v = 0.92
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"

    def _rainbow_segment_color(self, idx: int, total: int) -> str:
        """按彩虹顺序分配分段颜色（红->紫）。"""
        if total <= 1:
            h = 0.0
        else:
            h = (idx - 1) / max(total - 1, 1) * 0.82
        s = 0.78
        v = 0.95
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"

    def _precompute_paths(self):
        """预计算所有站点间的最短路径"""
        print(f"预计算 {self.total_stations} 个站点间的最短路径...")
        for i, start in enumerate(self.all_stations):
            try:
                lengths, paths = nx.single_source_dijkstra(self.G, start, weight=None)
                for end, length in lengths.items():
                    if start != end:
                        self.shortest_distances[(start, end)] = length
                        self.shortest_paths[(start, end)] = paths[end]
            except Exception as e:
                print(f"警告: 计算 {start} 时出错: {e}")
                continue
            if (i + 1) % 50 == 0:
                print(f"进度: {i + 1}/{self.total_stations}")
        print(f"预计算完成! 共 {len(self.shortest_distances)} 条路径")

    def search_station(self, keyword):
        """搜索站点"""
        keyword_lower = keyword.lower()
        return [s for s in self.all_stations if keyword_lower in s.lower()][:10]

    def get_station_lines(self, station):
        return self.station_to_lines.get(station, [])

    def _candidate_pool(self, current, visited, limit=8):
        candidates = []
        for station in self.all_stations:
            if station in visited:
                continue
            dist = self.shortest_distances.get((current, station), float('inf'))
            if dist != float('inf'):
                candidates.append((station, dist))
        candidates.sort(key=lambda item: (item[1], item[0]))
        return candidates[:limit]

    def _select_next_greedy(self, current, visited):
        candidates = self._candidate_pool(current, visited, limit=max(1, self.total_stations))
        if not candidates:
            return None, float('inf'), None
        station, dist = candidates[0]
        return station, dist, self.shortest_paths.get((current, station))

    def _select_next_dynamic(self, current, visited):
        candidates = self._candidate_pool(current, visited, limit=8)
        if not candidates:
            return None, float('inf'), None

        names = tuple(station for station, _ in candidates)

        @lru_cache(maxsize=None)
        def lookahead(curr, remaining, depth):
            remaining_list = [s for s in names if s in remaining]
            if depth == 0 or not remaining_list:
                return 0.0

            best = float('inf')
            next_remaining = set(remaining)
            for station in remaining_list:
                dist = self.shortest_distances.get((curr, station), float('inf'))
                if dist == float('inf'):
                    continue
                next_remaining.discard(station)
                score = dist + lookahead(station, frozenset(next_remaining), depth - 1)
                next_remaining.add(station)
                best = min(best, score)
            return best if best != float('inf') else 0.0

        best_station = None
        best_score = float('inf')
        for station, dist in candidates:
            remaining = frozenset(s for s in names if s != station)
            score = dist + lookahead(station, remaining, 2)
            if score < best_score:
                best_score = score
                best_station = station

        if best_station is None:
            best_station, dist = candidates[0]
        else:
            dist = self.shortest_distances.get((current, best_station), float('inf'))
        return best_station, dist, self.shortest_paths.get((current, best_station))

    def _select_next_dijkstra(self, current, visited):
        """显式使用 Dijkstra 预计算结果选择下一站。"""
        best_station = None
        best_dist = float('inf')
        for station in self.all_stations:
            if station in visited:
                continue
            dist = self.shortest_distances.get((current, station), float('inf'))
            if dist < best_dist:
                best_dist = dist
                best_station = station
        if best_station is None:
            return None, float('inf'), None
        return best_station, best_dist, self.shortest_paths.get((current, best_station))

    def _select_next_bfs(self, current, visited):
        """按广度优先层次选下一站（同层按站名稳定排序）。"""
        try:
            lengths = nx.single_source_shortest_path_length(self.G, current)
        except Exception:
            lengths = {}
        candidates = []
        for station, dist in lengths.items():
            if station in visited or station == current:
                continue
            candidates.append((station, dist))
        if not candidates:
            return None, float('inf'), None
        candidates.sort(key=lambda item: (item[1], item[0]))
        best_station, best_dist = candidates[0]
        return best_station, float(best_dist), self.shortest_paths.get((current, best_station))

    def _select_next_dfs(self, current, visited):
        """优先沿当前站未访问邻居前进；无邻居时回退到最近未访问站。"""
        neighbors = sorted(self.G.neighbors(current))
        for nxt in neighbors:
            if nxt not in visited:
                return nxt, 1.0, self.shortest_paths.get((current, nxt), [current, nxt])
        return self._select_next_greedy(current, visited)

    def _select_next_genetic(self, current, visited):
        candidates = self._candidate_pool(current, visited, limit=8)
        if not candidates:
            return None, float('inf'), None

        rng = random.Random(self.random_seed + len(visited))
        population_size = min(12, max(6, len(candidates)))
        population = []
        base_names = [station for station, _ in candidates]

        for _ in range(population_size):
            chromosome = base_names[:]
            rng.shuffle(chromosome)
            population.append(chromosome)

        def fitness(order):
            score = 0.0
            curr = current
            for station in order[:4]:
                score += self.shortest_distances.get((curr, station), 9999)
                curr = station
            return score

        for _ in range(8):
            population.sort(key=fitness)
            elites = population[: max(2, population_size // 3)]
            new_population = elites[:]
            while len(new_population) < population_size:
                p1 = rng.choice(elites)
                p2 = rng.choice(elites)
                cut = rng.randint(1, max(1, len(base_names) - 1))
                child = p1[:cut] + [gene for gene in p2 if gene not in p1[:cut]]
                if len(child) >= 2 and rng.random() < 0.35:
                    i, j = sorted(rng.sample(range(len(child)), 2))
                    child[i], child[j] = child[j], child[i]
                new_population.append(child)
            population = new_population

        best_order = min(population, key=fitness)
        best_station = best_order[0]
        dist = self.shortest_distances.get((current, best_station), float('inf'))
        return best_station, dist, self.shortest_paths.get((current, best_station))

    def _select_next_ant_colony(self, current, visited):
        candidates = self._candidate_pool(current, visited, limit=8)
        if not candidates:
            return None, float('inf'), None

        pheromone = {station: 1.0 for station, _ in candidates}
        rng = random.Random(self.random_seed * 3 + len(visited))
        ant_count = min(10, len(candidates) * 2)
        alpha = 1.2
        beta = 2.0

        for _ in range(6):
            scores = []
            for _ in range(ant_count):
                total_weight = 0.0
                weights = []
                for station, dist in candidates:
                    heuristic = 1.0 / max(dist, 1e-6)
                    weight = (pheromone[station] ** alpha) * (heuristic ** beta)
                    weights.append((station, dist, weight))
                    total_weight += weight

                pick = rng.random() * total_weight if total_weight else 0.0
                cursor = 0.0
                chosen_station, chosen_dist = candidates[0]
                for station, dist, weight in weights:
                    cursor += weight
                    if cursor >= pick:
                        chosen_station, chosen_dist = station, dist
                        break
                scores.append((chosen_station, chosen_dist))

            for station in pheromone:
                pheromone[station] *= 0.85
            for station, dist in scores:
                pheromone[station] += 1.0 / max(dist, 1.0)

        best_station = max(pheromone.items(), key=lambda item: item[1])[0]
        dist = self.shortest_distances.get((current, best_station), float('inf'))
        return best_station, dist, self.shortest_paths.get((current, best_station))

    def _select_next_station(self, current, visited, algorithm_name):
        handlers = {
            'greedy': self._select_next_greedy,
            'dynamic_programming': self._select_next_dynamic,
            'dijkstra': self._select_next_dijkstra,
            'bfs': self._select_next_bfs,
            'dfs': self._select_next_dfs,
            'genetic': self._select_next_genetic,
            'ant_colony': self._select_next_ant_colony,
        }
        handler = handlers.get(algorithm_name, self._select_next_greedy)
        return handler(current, visited)

    def find_path(self, start, end=None, algorithm_name='greedy', return_to_start=False):
        """查找遍历路径，支持多种启发式/元启发式策略。"""
        start_time = time.time()

        visited = set()
        path = [start]
        visited.add(start)
        current = start
        total_distance = 0

        while len(visited) < self.total_stations:
            best_station, best_distance, best_path = self._select_next_station(current, visited, algorithm_name)

            if best_station is None:
                break

            if best_path and len(best_path) > 1:
                # 注意：这里必须追加最短路径上的全部站点，保证 path 中相邻站点在图中有边。
                # 仅按“未访问”过滤会导致路径断裂（相邻两点不连边），后续分段解析会 KeyError。
                for station in best_path[1:]:
                    path.append(station)
                    if station not in visited:
                        visited.add(station)

            total_distance += best_distance
            current = best_station

        final_station = end or (start if return_to_start else None)
        if final_station and current != final_station:
            return_dist = self.shortest_distances.get((current, final_station), 0)
            return_path = self.shortest_paths.get((current, final_station), [])
            if return_path and len(return_path) > 1:
                for station in return_path[1:]:
                    path.append(station)
            total_distance += return_dist

        # 解析路径为换乘段
        segments = self._parse_path_to_segments(path)
        # 全站遍历按彩虹色阶分配
        for i, seg in enumerate(segments, start=1):
            seg['color'] = self._rainbow_segment_color(i, len(segments))

        return {
            'algorithm': algorithm_name,
            'mode': 'traversal',
            'path': path,
            'segments': segments,
            'total_stations': len(path),
            'unique_stations': len(set(path)),
            'total_distance': round(total_distance, 2),
            'time': round(time.time() - start_time, 2),
            'is_complete': len(set(path)) == self.total_stations,
            'start_station': start,
            'end_station': path[-1] if path else end
        }

    def find_shortest_path(self, start, end):
        """任意两站点最短路径。"""
        start_time = time.time()
        if start not in self.G or end not in self.G:
            raise ValueError("起点或终点不存在")

        path = nx.shortest_path(self.G, source=start, target=end)
        distance = nx.shortest_path_length(self.G, source=start, target=end)
        segments = self._parse_path_to_segments(path)
        return {
            'algorithm': 'dijkstra_shortest_path',
            'mode': 'shortest_path',
            'path': path,
            'segments': segments,
            'total_stations': len(path),
            'unique_stations': len(set(path)),
            'total_distance': round(float(distance), 2),
            'time': round(time.time() - start_time, 2),
            'is_complete': False,
            'start_station': start,
            'end_station': end,
        }

    def _parse_path_to_segments(self, path):
        """将路径解析为换乘段"""
        if not path or len(path) < 2:
            return []

        segments = []
        current_line = None
        segment_start = path[0]
        segment_stations = [path[0]]

        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            # 兜底保护：理论上 path 应连续；若意外断裂则跳过该对，避免接口 500。
            if not self.G.has_edge(u, v):
                continue
            edge_line = self.G[u][v]['line']

            if current_line is None:
                current_line = edge_line
                segment_stations.append(v)
            elif edge_line == current_line:
                segment_stations.append(v)
            else:
                # 保存当前段
                seg_id = len(segments) + 1
                segments.append({
                    'id': seg_id,
                    'line': current_line,
                    'line_name': f'{current_line}号线',
                    # 按“段”而非“线路”着色，保证每段颜色不同
                    'color': self._segment_color(seg_id),
                    # 线路的真实颜色保留给需要时显示
                    'line_color': self.line_colors.get(current_line, '#888888'),
                    'start': segment_start,
                    'end': path[i],
                    'stations': segment_stations.copy(),
                    'station_count': len(segment_stations) - 1
                })
                # 开始新段
                current_line = edge_line
                segment_start = path[i]
                segment_stations = [path[i], v]

        # 添加最后一段
        seg_id = len(segments) + 1
        segments.append({
            'id': seg_id,
            'line': current_line,
            'line_name': f'{current_line}号线',
            'color': self._segment_color(seg_id),
            'line_color': self.line_colors.get(current_line, '#888888'),
            'start': segment_start,
            'end': path[-1],
            'stations': segment_stations.copy(),
            'station_count': len(segment_stations) - 1
        })

        return segments

    def build_report_text(self, result: dict, algorithm_label: str) -> str:
        """生成“换乘分段 + 完整路径”的文本报告。"""
        now = datetime.now()
        path = result.get('path') or []
        segments = result.get('segments') or []

        lines = []
        lines.append("=" * 70)
        lines.append("合肥地铁全站点遍历路径报告")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"生成时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"算法名称: {algorithm_label}")
        lines.append(f"任务模式: {'全站遍历' if result.get('mode') == 'traversal' else '任意两站最短路径'}")
        lines.append(f"起点站点: {path[0] if path else ''}")
        lines.append(f"终点站点: {result.get('end_station', '')}")
        lines.append(f"总站点数: {len(path)}")
        lines.append(f"独立站点数: {len(set(path))}")
        lines.append(f"换乘次数: {max(len(segments) - 1, 0)}")
        lines.append(f"计算耗时(秒): {result.get('time')}")
        lines.append("")
        lines.append("=" * 70)
        lines.append("换乘分段详情（以换乘站为节点）")
        lines.append("=" * 70)
        lines.append("")

        for seg in segments:
            lines.append(f"【第{seg.get('id')}段】{seg.get('line_name')}")
            lines.append(f"  段颜色: {seg.get('color')}")
            if seg.get('line_color'):
                lines.append(f"  线路颜色: {seg.get('line_color')}")
            lines.append(f"  起点: {seg.get('start')}")
            lines.append(f"  终点: {seg.get('end')}")
            lines.append(f"  经过站点数: {seg.get('station_count')}")
            stations = seg.get('stations') or []
            lines.append(f"  站点列表: {' → '.join(stations)}")
            lines.append("")

        lines.append("=" * 70)
        lines.append("完整路径")
        lines.append("=" * 70)
        lines.append("")
        for i, station in enumerate(path, start=1):
            lines.append(f"  {str(i).rjust(3, ' ')}. {station}")

        lines.append("")
        lines.append("=" * 70)
        lines.append("报告结束")
        lines.append("=" * 70)
        return "\n".join(lines)