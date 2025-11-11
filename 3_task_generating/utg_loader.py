import json
import networkx as nx
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict


class UTGGraph:
    """
    UTG图结构类，用于表示和操作UI转换图
    """
    
    def __init__(self):
        # 创建有向图
        self.state_graph = nx.DiGraph()  # 基于state_str的图
        self.cluster_graph = nx.DiGraph()  # 基于cluster的图
        
        # 数据存储
        self.states: Dict[str, Dict[str, Any]] = {}  # state_str -> state_data
        self.events: Dict[str, Dict[str, Any]] = {}  # event_tag -> event_data
        self.clusters: Dict[str, List[str]] = defaultdict(list)  # cluster_id -> [state_strs]
        self.state_to_cluster: Dict[str, str] = {}  # state_str -> cluster_id
        
        # 统计信息
        self.stats = {
            'total_states': 0,
            'total_events': 0,
            'total_clusters': 0,
            'connected_components': 0
        }
    
    def add_state(self, state_str: str, cluster_id: str, state_data: Optional[Dict[str, Any]] = None):
        """
        添加状态节点
        
        Args:
            state_str: 状态ID
            cluster_id: 聚类ID
            state_data: 状态附加数据
        """
        # 添加到state图
        self.state_graph.add_node(state_str, cluster_id=cluster_id, data=state_data)
        
        # 添加到cluster图
        if not self.cluster_graph.has_node(cluster_id):
            self.cluster_graph.add_node(cluster_id, states=set())
        
        # 更新映射关系
        self.states[state_str] = state_data or {}
        self.state_to_cluster[state_str] = cluster_id
        self.clusters[cluster_id].append(state_str)
        self.cluster_graph.nodes[cluster_id]['states'].add(state_str)
        
        self.stats['total_states'] = len(self.states)
        self.stats['total_clusters'] = len(self.clusters)
    
    def add_event(self, start_state: str, stop_state: str, start_cluster: str, 
                  stop_cluster: str, event_data: Optional[Dict[str, Any]] = None):
        """
        添加事件边
        
        Args:
            start_state: 起始状态
            stop_state: 结束状态  
            start_cluster: 起始聚类
            stop_cluster: 结束聚类
            event_data: 事件附加数据
        """
        event_tag = event_data.get('event_str', f"{start_state}->{stop_state}") if event_data else f"{start_state}->{stop_state}"
        
        # 添加到state图
        if self.state_graph.has_node(start_state) and self.state_graph.has_node(stop_state):
            self.state_graph.add_edge(start_state, stop_state, event_data=event_data, event_tag=event_tag)
        
        # 添加到cluster图（避免自环）
        if start_cluster != stop_cluster:
            if self.cluster_graph.has_node(start_cluster) and self.cluster_graph.has_node(stop_cluster):
                # 如果已存在边，添加到边的事件列表中
                if self.cluster_graph.has_edge(start_cluster, stop_cluster):
                    self.cluster_graph[start_cluster][stop_cluster]['events'].append(event_tag)
                else:
                    self.cluster_graph.add_edge(start_cluster, stop_cluster, events=[event_tag])
        
        self.events[event_tag] = event_data or {}
        self.stats['total_events'] = len(self.events)
    
    def get_shortest_path_states(self, start_state: str, end_state: str) -> Optional[List[str]]:
        """
        计算两个状态之间的最短路径
        
        Args:
            start_state: 起始状态
            end_state: 目标状态
            
        Returns:
            最短路径的状态列表，如果不存在路径则返回None
        """
        try:
            return nx.shortest_path(self.state_graph, start_state, end_state)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
    
    def get_shortest_path_clusters(self, start_cluster: str, end_cluster: str) -> Optional[List[str]]:
        """
        计算两个聚类之间的最短路径
        
        Args:
            start_cluster: 起始聚类
            end_cluster: 目标聚类
            
        Returns:
            最短路径的聚类列表，如果不存在路径则返回None
        """
        try:
            return nx.shortest_path(self.cluster_graph, start_cluster, end_cluster)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
    
    def path_exists_states(self, start_state: str, end_state: str) -> bool:
        """
        检查两个状态之间是否存在路径
        
        Args:
            start_state: 起始状态
            end_state: 目标状态
            
        Returns:
            如果存在路径返回True，否则返回False
        """
        return nx.has_path(self.state_graph, start_state, end_state)
    
    def path_exists_clusters(self, start_cluster: str, end_cluster: str) -> bool:
        """
        检查两个聚类之间是否存在路径
        
        Args:
            start_cluster: 起始聚类
            end_cluster: 目标聚类
            
        Returns:
            如果存在路径返回True，否则返回False
        """
        if start_cluster == end_cluster:
            return True
        return nx.has_path(self.cluster_graph, start_cluster, end_cluster)
    
    def get_all_paths_states(self, start_state: str, end_state: str, cutoff: Optional[int] = None) -> List[List[str]]:
        """
        获取两个状态之间的所有路径
        
        Args:
            start_state: 起始状态
            end_state: 目标状态
            cutoff: 最大路径长度限制
            
        Returns:
            所有路径的列表
        """
        try:
            return list(nx.all_simple_paths(self.state_graph, start_state, end_state, cutoff=cutoff))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []
    
    def get_reachable_states(self, start_state: str) -> Set[str]:
        """
        获取从起始状态可达的所有状态
        
        Args:
            start_state: 起始状态
            
        Returns:
            可达状态的集合
        """
        if start_state not in self.state_graph:
            return set()
        return set(nx.descendants(self.state_graph, start_state)) | {start_state}
    
    def get_reachable_clusters(self, start_cluster: str) -> Set[str]:
        """
        获取从起始聚类可达的所有聚类
        
        Args:
            start_cluster: 起始聚类
            
        Returns:
            可达聚类的集合
        """
        if start_cluster not in self.cluster_graph:
            return set()
        return set(nx.descendants(self.cluster_graph, start_cluster)) | {start_cluster}
    
    def get_connected_components_states(self) -> List[Set[str]]:
        """
        获取状态图的连通分量
        
        Returns:
            连通分量列表，每个分量是状态集合
        """
        return list(nx.weakly_connected_components(self.state_graph))
    
    def get_connected_components_clusters(self) -> List[Set[str]]:
        """
        获取聚类图的连通分量
        
        Returns:
            连通分量列表，每个分量是聚类集合
        """
        return list(nx.weakly_connected_components(self.cluster_graph))
    
    def update_stats(self):
        """
        更新图的统计信息
        """
        self.stats.update({
            'total_states': len(self.states),
            'total_events': len(self.events),
            'total_clusters': len(self.clusters),
            'connected_components': nx.number_weakly_connected_components(self.state_graph),
            'state_edges': self.state_graph.number_of_edges(),
            'cluster_edges': self.cluster_graph.number_of_edges(),
        })
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取图的统计信息
        
        Returns:
            统计信息字典
        """
        self.update_stats()
        return self.stats.copy()
    
    def print_summary(self):
        """
        打印图的摘要信息
        """
        stats = self.get_stats()
        print("=== UTG图摘要 ===")
        print(f"状态数量: {stats['total_states']}")
        print(f"事件数量: {stats['total_events']}")
        print(f"聚类数量: {stats['total_clusters']}")
        print(f"状态边数: {stats['state_edges']}")
        print(f"聚类边数: {stats['cluster_edges']}")
        print(f"连通分量数: {stats['connected_components']}")


class UTGLoader:
    """
    UTG数据加载器，用于从聚类后的文件夹中读取UTG数据并构建图结构
    """
    
    def __init__(self, clustered_folder: str):
        """
        初始化UTG加载器
        
        Args:
            clustered_folder: 聚类后的UTG文件夹路径
        """
        self.clustered_folder = Path(clustered_folder)
        self.states_folder = self.clustered_folder / "states"
        self.events_folder = self.clustered_folder / "events"
        
        # 验证文件夹结构
        self._validate_structure()
        
        # 创建图对象
        self.graph = UTGGraph()
    
    def _validate_structure(self):
        """
        验证输入文件夹结构
        
        Raises:
            FileNotFoundError: 如果必要的文件夹不存在
        """
        if not self.clustered_folder.exists():
            raise FileNotFoundError(f"聚类文件夹不存在: {self.clustered_folder}")
        if not self.states_folder.exists():
            raise FileNotFoundError(f"states文件夹不存在: {self.states_folder}")
        if not self.events_folder.exists():
            raise FileNotFoundError(f"events文件夹不存在: {self.events_folder}")
    
    def _load_json_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        加载JSON文件
        
        Args:
            file_path: JSON文件路径
            
        Returns:
            解析后的数据，如果失败则返回None
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    print(f"警告: 空文件 {file_path}")
                    return None
                return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"错误: JSON解析失败 {file_path}: {e}")
            return None
        except Exception as e:
            print(f"错误: 读取文件失败 {file_path}: {e}")
            return None
    
    def load_states(self) -> int:
        """
        加载所有状态文件
        
        Returns:
            成功加载的状态数量
        """
        state_files = list(self.states_folder.glob("state_*.json"))
        loaded_count = 0
        
        print(f"开始加载 {len(state_files)} 个状态文件...")
        
        for state_file in state_files:
            state_data = self._load_json_file(state_file)
            if state_data is None:
                continue
            
            state_str = state_data.get("state_str", "")
            cluster_id = state_data.get("state_cluster_id", "")
            
            if not state_str or not cluster_id:
                print(f"警告: 状态文件缺少必要字段 {state_file}")
                continue
            
            # 添加到图中
            self.graph.add_state(state_str, cluster_id, state_data)
            loaded_count += 1
        
        print(f"成功加载 {loaded_count} 个状态")
        return loaded_count
    
    def load_events(self) -> int:
        """
        加载所有事件文件
        
        Returns:
            成功加载的事件数量
        """
        event_files = list(self.events_folder.glob("event_*.json"))
        loaded_count = 0
        
        print(f"开始加载 {len(event_files)} 个事件文件...")
        
        for event_file in event_files:
            event_data = self._load_json_file(event_file)
            if event_data is None:
                continue
            
            start_state = event_data.get("start_state", "")
            stop_state = event_data.get("stop_state", "")
            start_cluster = event_data.get("start_cluster", "")
            stop_cluster = event_data.get("stop_cluster", "")
            
            # 跳过unknown_cluster的事件
            if "unknown_cluster" in [start_cluster, stop_cluster]:
                print(f"跳过unknown_cluster事件: {event_file.name}")
                continue
            
            if not all([start_state, stop_state, start_cluster, stop_cluster]):
                print(f"警告: 事件文件缺少必要字段 {event_file}")
                continue
            
            # 添加到图中
            self.graph.add_event(start_state, stop_state, start_cluster, stop_cluster, event_data)
            loaded_count += 1
        
        print(f"成功加载 {loaded_count} 个事件")
        return loaded_count
    
    def load_utg(self) -> UTGGraph:
        """
        加载完整的UTG数据
        
        Returns:
            构建好的UTG图对象
        """
        print(f"开始加载UTG数据: {self.clustered_folder}")
        
        # 先加载状态，再加载事件
        state_count = self.load_states()
        event_count = self.load_events()
        
        # 更新统计信息
        self.graph.update_stats()
        
        print(f"UTG加载完成:")
        print(f"  - 状态: {state_count}")
        print(f"  - 事件: {event_count}")
        print(f"  - 聚类: {len(self.graph.clusters)}")
        
        return self.graph
    
    def find_path_between_states(self, start_state: str, end_state: str) -> Optional[List[str]]:
        """
        查找两个状态之间的路径
        
        Args:
            start_state: 起始状态ID
            end_state: 目标状态ID
            
        Returns:
            路径列表，如果不存在则返回None
        """
        return self.graph.get_shortest_path_states(start_state, end_state)
    
    def find_path_between_clusters(self, start_cluster: str, end_cluster: str) -> Optional[List[str]]:
        """
        查找两个聚类之间的路径
        
        Args:
            start_cluster: 起始聚类ID
            end_cluster: 目标聚类ID
            
        Returns:
            路径列表，如果不存在则返回None
        """
        return self.graph.get_shortest_path_clusters(start_cluster, end_cluster)
    
    def check_connectivity(self) -> Dict[str, Any]:
        """
        检查图的连通性
        
        Returns:
            连通性分析结果
        """
        stats = self.graph.get_stats()
        
        state_components = self.graph.get_connected_components_states()
        cluster_components = self.graph.get_connected_components_clusters()
        
        return {
            'total_states': stats['total_states'],
            'total_clusters': stats['total_clusters'],
            'state_components': len(state_components),
            'cluster_components': len(cluster_components),
            'largest_state_component': max(len(comp) for comp in state_components) if state_components else 0,
            'largest_cluster_component': max(len(comp) for comp in cluster_components) if cluster_components else 0,
            'is_state_graph_connected': len(state_components) == 1,
            'is_cluster_graph_connected': len(cluster_components) == 1,
        }


# 使用示例和测试函数
def test_path_analysis(loader: UTGLoader):
    """
    测试路径分析功能
    """
    print("\n=== 路径分析测试 ===")
    
    graph = loader.graph
    
    # 获取一些示例状态和聚类
    states = list(graph.states.keys())[:5]  # 取前5个状态
    clusters = list(graph.clusters.keys())[:3]  # 取前3个聚类
    
    print(f"\n测试状态: {states}")
    print(f"测试聚类: {clusters}")
    
    # 测试状态间路径
    if len(states) >= 2:
        start_state, end_state = states[0], states[-1]
        path = loader.find_path_between_states(start_state, end_state)
        exists = graph.path_exists_states(start_state, end_state)
        
        print(f"\n状态路径测试: {start_state} -> {end_state}")
        print(f"路径存在: {exists}")
        if path:
            print(f"最短路径长度: {len(path)}")
            print(f"路径: {' -> '.join(path[:3])}{'...' if len(path) > 3 else ''}")
        
    # 测试聚类间路径
    if len(clusters) >= 2:
        start_cluster, end_cluster = clusters[0], clusters[-1]
        path = loader.find_path_between_clusters(start_cluster, end_cluster)
        exists = graph.path_exists_clusters(start_cluster, end_cluster)
        
        print(f"\n聚类路径测试: {start_cluster} -> {end_cluster}")
        print(f"路径存在: {exists}")
        if path:
            print(f"最短路径长度: {len(path)}")
            print(f"路径: {' -> '.join(path)}")


if __name__ == "__main__":
    # 使用示例
    clustered_folder = r"c:\Projects\AndroidTaskAutomation\3_task_generating\utg\original_greedy_dfs_20251106_160351_clustered"
    
    # 创建加载器并加载UTG
    loader = UTGLoader(clustered_folder)
    graph = loader.load_utg()
    
    # 打印摘要
    graph.print_summary()
    
    # 检查连通性
    connectivity = loader.check_connectivity()
    print(f"\n=== 连通性分析 ===")
    for key, value in connectivity.items():
        print(f"{key}: {value}")
    
    # 测试路径分析
    test_path_analysis(loader)
