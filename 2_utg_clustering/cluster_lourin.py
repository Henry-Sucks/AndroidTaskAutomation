import json
import random
import networkx as nx
from typing import Dict, List, Set, Tuple, Optional, Any
from pathlib import Path
from collections import defaultdict
import math

class UTGLouvainClustering:
    """
    基于Louvain算法的UTG聚类系统
    
    用于将UI转换图(UTG)进行社区检测和层次聚类，
    识别功能相关的状态组和导航模式。
    """
    
    def __init__(self, utg_folder: str):
        """
        初始化UTG Louvain聚类器
        
        Args:
            utg_folder: UTG数据文件夹路径，包含states和events子文件夹
        """
        self.utg_folder = Path(utg_folder)
        self.states_folder = self.utg_folder / "states"
        self.events_folder = self.utg_folder / "events"
        
        # UTG图结构
        self.graph = nx.Graph()  # 使用NetworkX图存储UTG
        self.weighted_graph = nx.Graph()  # 带权重的图用于Louvain算法
        
        # 状态和边数据
        self.states_data: Dict[str, Dict[str, Any]] = {}  # state_str -> state_data
        self.events_data: List[Dict[str, Any]] = []  # 所有事件数据
        
        # 聚类结果存储
        self.partitions_history: List[Dict[str, str]] = []  # 每层的分区结果
        self.final_partition: Dict[str, str] = {}  # 最终分区 {state_str -> community_id}
        self.modularity_history: List[float] = []  # 每层的模块度
        
        # 输出相关属性
        self.output_folder = Path(f"{utg_folder}_louvain_clustered")
        self.state_id_to_cluster: Dict[str, str] = {}  # state_id -> cluster_id映射
        
        # 算法参数
        self.resolution = 1.0  # 分辨率参数，控制社区大小
        self.random_seed = 42
        
        # 层次聚类参数
        self.max_clusters = 10  # 最大聚类数阈值
        self.min_cluster_size = 5  # 最小聚类大小
        self.hierarchical_levels = []  # 存储每一层的聚类结果
        
        # 过滤相关
        self.filtered_states: Set[str] = set()  # 被过滤掉的孤立状态
        self.connected_states: Set[str] = set()  # 有连接的状态
        
        # 验证输入结构
        self._validate_input_structure()
    
    def _validate_input_structure(self):
        """
        验证UTG文件夹结构
        
        Raises:
            FileNotFoundError: 如果必要的文件夹不存在
        """
        if not self.utg_folder.exists():
            raise FileNotFoundError(f"UTG文件夹不存在: {self.utg_folder}")
        if not self.states_folder.exists():
            raise FileNotFoundError(f"states文件夹不存在: {self.states_folder}")
        if not self.events_folder.exists():
            raise FileNotFoundError(f"events文件夹不存在: {self.events_folder}")
    
    def load_utg_data(self):
        """
        加载UTG数据，构建图结构
        
        步骤：
        1. 加载所有状态文件
        2. 加载所有事件文件
        3. 构建NetworkX图
        4. 计算边权重
        """
        print("正在加载UTG数据...")
        
        # 加载状态数据
        self._load_states()
        
        # 加载事件数据
        self._load_events()
        
        # 构建图结构
        self._build_graph()
        
        # 计算边权重
        self._calculate_edge_weights()
        
        # 过滤孤立状态
        self.filter_isolated_states()
        
        print(f"UTG加载完成: {len(self.graph.nodes)} 个连通状态, {len(self.graph.edges)} 条转换")
        if self.filtered_states:
            print(f"已过滤掉 {len(self.filtered_states)} 个孤立状态")
    
    def _load_states(self):
        """
        加载所有状态文件
        """
        state_files = list(self.states_folder.glob("state_*.json"))
        for state_file in state_files:
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                    state_str = state_data.get("state_str")
                    if state_str:
                        self.states_data[state_str] = state_data
            except Exception as e:
                print(f"警告: 加载状态文件失败 {state_file}: {e}")
    
    def _load_events(self):
        """
        加载所有事件文件
        """
        event_files = list(self.events_folder.glob("event_*.json"))
        for event_file in event_files:
            try:
                with open(event_file, 'r', encoding='utf-8') as f:
                    event_data = json.load(f)
                    # 验证事件数据完整性
                    if ("start_state" in event_data and 
                        "stop_state" in event_data and 
                        event_data["start_state"] in self.states_data and 
                        event_data["stop_state"] in self.states_data):
                        self.events_data.append(event_data)
            except Exception as e:
                print(f"警告: 加载事件文件失败 {event_file}: {e}")
    
    def _build_graph(self):
        """
        构建NetworkX图结构
        """
        # 添加节点
        for state_str in self.states_data:
            self.graph.add_node(state_str)
            self.weighted_graph.add_node(state_str)
        
        # 添加边
        for event_data in self.events_data:
            start_state = event_data["start_state"]
            stop_state = event_data["stop_state"]
            
            # 添加无权边
            self.graph.add_edge(start_state, stop_state)
            
            # 初始化权重为1，后续会重新计算
            if self.weighted_graph.has_edge(start_state, stop_state):
                self.weighted_graph[start_state][stop_state]['weight'] += 1
            else:
                self.weighted_graph.add_edge(start_state, stop_state, weight=1)
    
    def _calculate_edge_weights(self):
        """
        计算边权重，基于多种因素：
        1. 转换频次 - 同一条边出现的次数
        2. 状态相似度 - 基于state_str_content_free
        3. UI结构相似度 - 基于视图层次结构
        """
        # 计算转换频次权重
        edge_frequency = defaultdict(int)
        for event_data in self.events_data:
            start_state = event_data["start_state"]
            stop_state = event_data["stop_state"]
            edge_frequency[(start_state, stop_state)] += 1
        
        # 更新边权重
        for (start_state, stop_state), frequency in edge_frequency.items():
            if self.weighted_graph.has_edge(start_state, stop_state):
                base_weight = frequency
                
                # 添加状态相似度权重
                similarity_weight = self._calculate_state_similarity(start_state, stop_state)
                
                # 最终权重 = 频次权重 * (1 + 相似度权重)
                final_weight = base_weight * (1 + similarity_weight)
                
                self.weighted_graph[start_state][stop_state]['weight'] = final_weight
    
    def _calculate_state_similarity(self, state1: str, state2: str) -> float:
        """
        计算两个状态之间的相似度
        
        Args:
            state1: 状态1的ID
            state2: 状态2的ID
            
        Returns:
            相似度分数 [0, 1]，1表示完全相似
        """
        if state1 not in self.states_data or state2 not in self.states_data:
            return 0.0
        
        data1 = self.states_data[state1]
        data2 = self.states_data[state2]
        
        similarity_score = 0.0
        
        # 1. 基于content_free状态的相似度
        content_free1 = data1.get("state_str_content_free", "")
        content_free2 = data2.get("state_str_content_free", "")
        if content_free1 == content_free2:
            similarity_score += 0.5
        
        # 2. 基于Activity的相似度
        activity1 = data1.get("foreground_activity", "")
        activity2 = data2.get("foreground_activity", "")
        if activity1 == activity2:
            similarity_score += 0.3
        
        # # 3. 基于视图数量的相似度
        # views1 = len(data1.get("views", []))
        # views2 = len(data2.get("views", []))
        # if views1 > 0 and views2 > 0:
        #     view_similarity = 1.0 - abs(views1 - views2) / max(views1, views2)
        #     similarity_score += 0.2 * view_similarity
        
        return min(similarity_score, 1.0)
    
    def filter_isolated_states(self):
        """
        过滤掉没有任何连接的孤立状态节点
        
        孤立状态定义：
        1. 没有任何边从该状态出发
        2. 没有任何边到达该状态
        3. 即该状态在图中的度为0
        """
        print("正在过滤孤立状态...")
        
        # 找出所有在事件中出现的状态（有连接的状态）
        connected_states = set()
        
        for event_data in self.events_data:
            start_state = event_data.get("start_state")
            stop_state = event_data.get("stop_state")
            
            if start_state:
                connected_states.add(start_state)
            if stop_state:
                connected_states.add(stop_state)
        
        # 找出孤立状态（存在于states_data但不在connected_states中）
        all_states = set(self.states_data.keys())
        isolated_states = all_states - connected_states
        
        # 记录过滤结果
        self.connected_states = connected_states
        self.filtered_states = isolated_states
        
        # 从states_data中移除孤立状态
        for isolated_state in isolated_states:
            if isolated_state in self.states_data:
                del self.states_data[isolated_state]
        
        # 从图中移除孤立节点
        for isolated_state in isolated_states:
            if self.graph.has_node(isolated_state):
                self.graph.remove_node(isolated_state)
            if self.weighted_graph.has_node(isolated_state):
                self.weighted_graph.remove_node(isolated_state)
        
        print(f"过滤完成: 保留 {len(connected_states)} 个连通状态，"
              f"过滤掉 {len(isolated_states)} 个孤立状态")
        
        if isolated_states:
            print(f"被过滤的孤立状态示例: {list(isolated_states)[:5]}")
    
    def run_louvain_clustering(self) -> Dict[str, str]:
        """
        执行层次Louvain算法进行UTG聚类
        
        Returns:
            最终的分区结果 {state_str -> community_id}
        """
        print("开始执行层次Louvain聚类算法...")
        
        # 设置随机种子
        random.seed(self.random_seed)
        
        # 第一层：基础Louvain聚类
        level_0_partition = self._run_single_louvain()
        self.hierarchical_levels.append(level_0_partition)
        
        current_partition = level_0_partition
        level = 0
        
        while True:
            level += 1
            print(f"\n=== 开始第 {level} 层聚类 ===")
            
            # 检查是否满足停止条件
            cluster_count = len(set(current_partition.values()))
            print(f"当前聚类数: {cluster_count}")
            
            if self._should_stop_hierarchical_clustering(current_partition):
                print(f"满足停止条件，层次聚类结束")
                break
            
            # 构建聚类间的图
            cluster_graph = self._build_cluster_graph(current_partition)
            
            if len(cluster_graph.nodes()) <= 1:
                print("聚类图只有一个节点，无法继续聚类")
                break
            
            # 对聚类进行再次聚类
            cluster_partition = self._run_cluster_louvain(cluster_graph)
            
            # 将聚类级别的分区映射回原始状态
            new_partition = self._map_cluster_partition_to_states(current_partition, cluster_partition)
            
            # 检查是否有改进
            if len(set(new_partition.values())) >= len(set(current_partition.values())):
                print(f"聚类数没有减少，停止层次聚类")
                break
            
            # 更新当前分区
            current_partition = new_partition
            self.hierarchical_levels.append(current_partition)
            
            print(f"第 {level} 层完成，聚类数: {len(set(current_partition.values()))}")
        
        self.final_partition = current_partition
        print(f"\n层次聚类完成，最终聚类数: {len(set(self.final_partition.values()))}")
        
        return self.final_partition
    
    def _run_single_louvain(self) -> Dict[str, str]:
        """
        执行单层Louvain算法
        
        Returns:
            分区结果 {state_str -> community_id}
        """
        # 初始化：每个节点为一个社区
        current_partition = {node: str(i) for i, node in enumerate(self.weighted_graph.nodes())}
        current_graph = self.weighted_graph.copy()
        
        # 保存第一轮的分区结果（原始节点）
        first_round_partition = None
        
        iteration = 0
        while True:
            iteration += 1
            print(f"  Louvain第 {iteration} 轮迭代...")
            
            # 阶段1：局部优化
            new_partition = self._phase1_optimize(current_graph, current_partition)
            
            # 计算当前模块度
            current_modularity = self._calculate_modularity(current_graph, new_partition)
            self.modularity_history.append(current_modularity)
            
            # 如果是第一轮，保存结果（这是在原始节点上的聚类）
            if iteration == 1:
                first_round_partition = new_partition.copy()
            
            # 检查收敛条件
            if self._is_converged(current_partition, new_partition):
                print(f"  算法收敛，模块度: {current_modularity:.4f}")
                
                # 如果收敛发生在第一轮，直接使用结果
                if iteration == 1:
                    return new_partition
                else:
                    # 否则使用第一轮的结果作为最终结果
                    if first_round_partition is not None:
                        return first_round_partition
                    else:
                        return new_partition
            
            # 存储分区结果
            if iteration == 1:
                # 第一轮的结果是在原始节点上的，直接保存
                self.partitions_history.append(new_partition.copy())
            
            # 阶段2：网络聚合
            current_graph = self._phase2_aggregate(current_graph, new_partition)
            current_partition = {node: str(i) for i, node in enumerate(current_graph.nodes())}
            
            print(f"  第 {iteration} 轮完成，社区数: {len(set(new_partition.values()))}, 模块度: {current_modularity:.4f}")
        
        return first_round_partition or new_partition
    
    def _should_stop_hierarchical_clustering(self, partition: Dict[str, str]) -> bool:
        """
        判断是否应该停止层次聚类
        
        Args:
            partition: 当前分区
            
        Returns:
            是否应该停止
        """
        cluster_count = len(set(partition.values()))
        
        # 条件1: 聚类数已经达到阈值
        if cluster_count <= self.max_clusters:
            return True
        
        # 条件2: 检查聚类大小分布
        cluster_sizes = defaultdict(int)
        for state in partition.values():
            cluster_sizes[state] += 1
        
        # 如果大部分聚类都很小，继续合并
        small_clusters = sum(1 for size in cluster_sizes.values() if size < self.min_cluster_size)
        total_clusters = len(cluster_sizes)
        
        # 如果小聚类比例低于30%，可以停止
        if small_clusters / total_clusters < 0.3:
            return True
        
        return False
    
    def _build_cluster_graph(self, partition: Dict[str, str]) -> nx.Graph:
        """
        构建聚类间的图
        
        Args:
            partition: 当前分区
            
        Returns:
            聚类间的图
        """
        cluster_graph = nx.Graph()
        
        # 获取所有聚类
        clusters = set(partition.values())
        
        # 添加聚类节点
        for cluster in clusters:
            cluster_graph.add_node(cluster)
        
        # 计算聚类间的连接权重
        cluster_connections = defaultdict(float)
        
        for event_data in self.events_data:
            start_state = event_data.get("start_state")
            stop_state = event_data.get("stop_state")
            
            if start_state in partition and stop_state in partition:
                start_cluster = partition[start_state]
                stop_cluster = partition[stop_state]
                
                # 只考虑跨聚类的连接
                if start_cluster != stop_cluster:
                    edge_key = tuple(sorted([start_cluster, stop_cluster]))
                    cluster_connections[edge_key] += 1
        
        # 添加聚类间的边
        for (cluster1, cluster2), weight in cluster_connections.items():
            cluster_graph.add_edge(cluster1, cluster2, weight=weight)
        
        print(f"  构建聚类图: {len(cluster_graph.nodes())} 个聚类, {len(cluster_graph.edges())} 条连接")
        
        return cluster_graph
    
    def _run_cluster_louvain(self, cluster_graph: nx.Graph) -> Dict[str, str]:
        """
        对聚类图运行Louvain算法
        
        Args:
            cluster_graph: 聚类间的图
            
        Returns:
            聚类的分区结果 {cluster_id -> super_cluster_id}
        """
        if len(cluster_graph.nodes()) == 0:
            return {}
        
        # 初始化分区
        partition = {cluster: str(i) for i, cluster in enumerate(cluster_graph.nodes())}
        
        # 运行单轮优化
        optimized_partition = self._phase1_optimize(cluster_graph, partition)
        
        print(f"  聚类级别Louvain: {len(cluster_graph.nodes())} -> {len(set(optimized_partition.values()))} 个超级聚类")
        
        return optimized_partition
    
    def _map_cluster_partition_to_states(self, state_partition: Dict[str, str], 
                                       cluster_partition: Dict[str, str]) -> Dict[str, str]:
        """
        将聚类级别的分区映射回状态级别
        
        Args:
            state_partition: 状态到聚类的映射 {state -> cluster}
            cluster_partition: 聚类到超级聚类的映射 {cluster -> super_cluster}
            
        Returns:
            状态到超级聚类的映射 {state -> super_cluster}
        """
        new_partition = {}
        
        for state, cluster in state_partition.items():
            super_cluster = cluster_partition.get(cluster, cluster)
            new_partition[state] = super_cluster
        
        return new_partition
    
    def _phase1_optimize(self, graph: nx.Graph, initial_partition: Dict[str, str]) -> Dict[str, str]:
        """
        Louvain算法第一阶段：局部模块度优化
        
        Args:
            graph: 当前图
            initial_partition: 初始分区
            
        Returns:
            优化后的分区
        """
        partition = initial_partition.copy()
        nodes = list(graph.nodes())
        
        improved = True
        while improved:
            improved = False
            random.shuffle(nodes)  # 随机顺序遍历节点
            
            for node in nodes:
                current_community = partition[node]
                best_community = current_community
                max_delta_q = 0.0
                
                # 尝试移动到邻居节点的社区
                neighbor_communities = set()
                for neighbor in graph.neighbors(node):
                    neighbor_communities.add(partition[neighbor])
                
                for community in neighbor_communities:
                    if community != current_community:
                        delta_q = self._calculate_modularity_gain(
                            graph, partition, node, community
                        )
                        
                        if delta_q > max_delta_q:
                            max_delta_q = delta_q
                            best_community = community
                
                # 如果找到更好的社区，移动节点
                if best_community != current_community:
                    partition[node] = best_community
                    improved = True
        
        return partition
    
    def _calculate_modularity_gain(self, graph: nx.Graph, partition: Dict[str, str], 
                                  node: str, target_community: str) -> float:
        """
        计算将节点移动到目标社区的模块度增益
        
        Args:
            graph: 图
            partition: 当前分区
            node: 要移动的节点
            target_community: 目标社区
            
        Returns:
            模块度增益值
        """
        # 计算节点的度和社区内外连接权重
        node_degree = sum(graph[node][neighbor].get('weight', 1) 
                         for neighbor in graph.neighbors(node))
        
        # 计算移动到目标社区的权重增益
        weight_to_target = 0
        weight_from_current = 0
        
        current_community = partition[node]
        
        for neighbor in graph.neighbors(node):
            edge_weight = graph[node][neighbor].get('weight', 1)
            neighbor_community = partition[neighbor]
            
            if neighbor_community == target_community:
                weight_to_target += edge_weight
            elif neighbor_community == current_community:
                weight_from_current += edge_weight
        
        # 计算社区的总权重
        total_weight = sum(graph[u][v].get('weight', 1) for u, v in graph.edges())
        
        if total_weight == 0:
            return 0
        
        # 模块度增益计算（简化版本）
        delta_q = (weight_to_target - weight_from_current) / total_weight
        
        return delta_q
    
    def _phase2_aggregate(self, graph: nx.Graph, partition: Dict[str, str]) -> nx.Graph:
        """
        Louvain算法第二阶段：网络聚合
        
        Args:
            graph: 当前图
            partition: 分区结果
            
        Returns:
            聚合后的新图
        """
        # 创建新图，节点为社区
        new_graph = nx.Graph()
        communities = set(partition.values())
        
        # 添加社区节点
        for community in communities:
            new_graph.add_node(community)
        
        # 计算社区间的边权重
        community_weights = defaultdict(float)
        
        for edge in graph.edges():
            u, v = edge
            community_u = partition[u]
            community_v = partition[v]
            edge_weight = graph[u][v].get('weight', 1)
            
            # 社区间或社区内的连接
            if community_u <= community_v:
                key = (community_u, community_v)
            else:
                key = (community_v, community_u)
            
            community_weights[key] += edge_weight
        
        # 添加聚合后的边
        for (comm_u, comm_v), weight in community_weights.items():
            if comm_u == comm_v:
                # 自环
                new_graph.add_edge(comm_u, comm_v, weight=weight)
            else:
                # 社区间连接
                new_graph.add_edge(comm_u, comm_v, weight=weight)
        
        return new_graph
    
    def _calculate_modularity(self, graph: nx.Graph, partition: Dict[str, str]) -> float:
        """
        计算给定分区的模块度
        
        Args:
            graph: 图
            partition: 分区
            
        Returns:
            模块度值
        """
        if len(graph.edges()) == 0:
            return 0.0
        
        # 使用NetworkX的内置模块度计算
        communities = defaultdict(list)
        for node, community in partition.items():
            communities[community].append(node)
        
        community_list = list(communities.values())
        return nx.algorithms.community.modularity(graph, community_list, weight='weight')
    
    def _is_converged(self, old_partition: Dict[str, str], new_partition: Dict[str, str]) -> bool:
        """
        检查算法是否收敛
        
        Args:
            old_partition: 旧分区
            new_partition: 新分区
            
        Returns:
            是否收敛
        """
        return old_partition == new_partition
    
    def _map_partition_to_original(self, partition: Dict[str, str]) -> Dict[str, str]:
        """
        将聚合图的分区映射回原始节点
        
        Args:
            partition: 聚合图的分区
            
        Returns:
            映射到原始节点的分区
        """
        # 如果已经是原始节点，直接返回
        if all(node in self.states_data for node in partition.keys()):
            return partition
        
        # 这种情况表明发生了聚合，但当前实现没有维护映射关系
        # 作为临时解决方案，我们应该返回第一轮的聚类结果
        # 而不是为每个节点创建独立社区
        
        print("警告: 检测到聚合后的分区，但缺少映射信息")
        
        # 如果有历史分区记录，返回最后一个有效的原始节点分区
        if self.partitions_history:
            last_valid_partition = self.partitions_history[-1]
            if all(node in self.states_data for node in last_valid_partition.keys()):
                return last_valid_partition
        
        # 如果没有历史记录，返回原始分区（但这不应该发生）
        return partition
    
    def _load_state_file(self, state_file_path: Path) -> Optional[Dict[str, Any]]:
        """
        加载state JSON文件
        
        Args:
            state_file_path: state文件路径
            
        Returns:
            解析后的state数据字典，如果文件无效则返回None
        """
        try:
            with open(state_file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return None
                
                data = json.loads(content)
                
                # 验证必要的属性
                if not isinstance(data, dict):
                    return None
                
                # 检查必要的state属性
                if "state_str" not in data:
                    return None
                
                return data
                
        except (json.JSONDecodeError, Exception):
            return None
    
    def _load_event_file(self, event_file_path: Path) -> Optional[Dict[str, Any]]:
        """
        加载event JSON文件
        
        Args:
            event_file_path: event文件路径
            
        Returns:
            解析后的event数据字典，如果文件无效则返回None
        """
        try:
            with open(event_file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return None
                
                data = json.loads(content)
                
                # 验证必要的属性
                if not isinstance(data, dict):
                    return None
                
                # 检查必要的event属性
                required_fields = ['event_str', 'start_state', 'stop_state']
                for field in required_fields:
                    if field not in data:
                        return None
                
                return data
                
        except (json.JSONDecodeError, Exception):
            return None
    
    def state_clustering(self, state_data: Dict[str, Any]) -> str:
        """
        为state分配聚类ID（基于Louvain结果）
        
        Args:
            state_data: state的JSON数据
            
        Returns:
            该state所属的cluster_id
        """
        state_str = state_data.get("state_str", "")
        
        # 检查是否为被过滤的孤立状态
        if state_str in self.filtered_states:
            cluster_id = "filtered_isolated"
        elif state_str in self.final_partition:
            cluster_id = self.final_partition[state_str]
        else:
            cluster_id = "unknown_cluster"
        
        # 更新映射
        self.state_id_to_cluster[state_str] = cluster_id
        
        return cluster_id
    
    def event_clustering(self, event_data: Dict[str, Any]) -> Tuple[str, str]:
        """
        为event获取聚类ID（基于start_state和stop_state的聚类）
        
        Args:
            event_data: event的JSON数据
            
        Returns:
            (start_cluster, stop_cluster)元组
        """
        start_state = event_data.get("start_state", "")
        stop_state = event_data.get("stop_state", "")
        
        # 处理过滤状态
        if start_state in self.filtered_states:
            start_cluster = "filtered_isolated"
        else:
            start_cluster = self.final_partition.get(start_state, "unknown_cluster")
        
        if stop_state in self.filtered_states:
            stop_cluster = "filtered_isolated"
        else:
            stop_cluster = self.final_partition.get(stop_state, "unknown_cluster")
        
        return start_cluster, stop_cluster
    
    def _process_states(self):
        """
        处理所有state文件并生成聚类结果
        """
        state_files = list(self.states_folder.glob("state_*.json"))
        processed_count = 0
        skipped_count = 0
        
        print(f"开始处理 {len(state_files)} 个state文件...")
        
        # 创建输出目录
        (self.output_folder / "states").mkdir(parents=True, exist_ok=True)
        
        for state_file in state_files:
            # 加载state数据
            state_data = self._load_state_file(state_file)
            
            # 跳过无效文件
            if state_data is None:
                skipped_count += 1
                print(f"跳过无效的state文件: {state_file}")
                continue
            
            # 进行聚类
            cluster_id = self.state_clustering(state_data)
            
            # 生成输出数据
            output_data = {
                "state_str": state_data.get("state_str", ""),
                "state_cluster_id": cluster_id
            }
            
            # 保存到输出文件
            output_file = self.output_folder / "states" / state_file.name
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            processed_count += 1
        
        print(f"States处理完成: 成功处理 {processed_count} 个文件，跳过 {skipped_count} 个无效文件")
        print(f"建立了 {len(self.state_id_to_cluster)} 个state_id映射")
    
    def _process_events(self):
        """
        处理所有event文件并生成聚类结果
        """
        event_files = list(self.events_folder.glob("event_*.json"))
        processed_count = 0
        skipped_count = 0
        
        print(f"开始处理 {len(event_files)} 个event文件...")
        
        # 创建输出目录
        (self.output_folder / "events").mkdir(parents=True, exist_ok=True)
        
        for event_file in event_files:
            # 加载event数据
            event_data = self._load_event_file(event_file)
            
            # 跳过无效文件
            if event_data is None:
                skipped_count += 1
                print(f"跳过无效的event文件: {event_file}")
                continue
            
            # 进行聚类
            start_cluster, stop_cluster = self.event_clustering(event_data)
            
            # 生成输出数据
            output_data = {
                "event_str": event_data.get("event_str", ""),
                "start_state": event_data.get("start_state", ""),
                "stop_state": event_data.get("stop_state", ""),
                "start_cluster": start_cluster,
                "stop_cluster": stop_cluster
            }
            
            # 保存到输出文件
            output_file = self.output_folder / "events" / event_file.name
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            processed_count += 1
        
        print(f"Events处理完成: 成功处理 {processed_count} 个文件，跳过 {skipped_count} 个无效文件")
    
    def save_clustering_results(self, output_folder: str):
        """
        保存聚类结果
        
        Args:
            output_folder: 输出文件夹路径
        """
        output_path = Path(output_folder)
        output_path.mkdir(exist_ok=True)
        
        # 保存最终分区结果
        with open(output_path / "final_partition.json", 'w', encoding='utf-8') as f:
            json.dump(self.final_partition, f, indent=2, ensure_ascii=False)
        
        # 保存聚类统计信息
        statistics = self._generate_clustering_statistics()
        with open(output_path / "clustering_statistics.json", 'w', encoding='utf-8') as f:
            json.dump(statistics, f, indent=2, ensure_ascii=False)
        
        # 保存分层聚类结果
        for i, partition in enumerate(self.partitions_history):
            with open(output_path / f"partition_level_{i}.json", 'w', encoding='utf-8') as f:
                json.dump(partition, f, indent=2, ensure_ascii=False)
        
        print(f"聚类结果已保存到: {output_path}")
    
    def _generate_clustering_statistics(self) -> Dict[str, Any]:
        """
        生成聚类统计信息
        
        Returns:
            统计信息字典
        """
        communities = set(self.final_partition.values())
        community_sizes = defaultdict(int)
        
        for community in self.final_partition.values():
            community_sizes[community] += 1
        
        # 计算层次聚类信息
        hierarchical_info = []
        for level, partition in enumerate(self.hierarchical_levels):
            level_communities = set(partition.values())
            level_sizes = defaultdict(int)
            for comm in partition.values():
                level_sizes[comm] += 1
            
            hierarchical_info.append({
                "level": level,
                "num_communities": len(level_communities),
                "largest_community": max(level_sizes.values()) if level_sizes else 0,
                "smallest_community": min(level_sizes.values()) if level_sizes else 0,
                "average_community_size": sum(level_sizes.values()) / len(level_sizes) if level_sizes else 0
            })
        
        statistics = {
            "total_states": len(self.states_data),
            "total_transitions": len(self.events_data),
            "num_communities": len(communities),
            "filtered_isolated_states": len(self.filtered_states),
            "connected_states": len(self.connected_states),
            "final_modularity": self.modularity_history[-1] if self.modularity_history else 0,
            "modularity_history": self.modularity_history,
            "community_sizes": dict(community_sizes),
            "largest_community_size": max(community_sizes.values()) if community_sizes else 0,
            "smallest_community_size": min(community_sizes.values()) if community_sizes else 0,
            "average_community_size": sum(community_sizes.values()) / len(community_sizes) if community_sizes else 0,
            "hierarchical_levels": len(self.hierarchical_levels),
            "hierarchical_info": hierarchical_info,
            "clustering_parameters": {
                "max_clusters": self.max_clusters,
                "min_cluster_size": self.min_cluster_size,
                "resolution": self.resolution
            }
        }
        
        return statistics
    
    def visualize_communities(self, output_file: str = "utg_communities.png"):
        """
        可视化社区结构
        
        Args:
            output_file: 输出图片文件名
        """
        try:
            import matplotlib.pyplot as plt
            import numpy as np
            
            # 创建颜色映射
            communities = list(set(self.final_partition.values()))
            # 生成随机颜色
            colors = []
            for i in range(len(communities)):
                colors.append((np.random.random(), np.random.random(), np.random.random()))
            color_map = dict(zip(communities, colors))
            
            # 设置节点颜色
            node_colors = [color_map[self.final_partition[node]] 
                          for node in self.graph.nodes()]
            
            # 绘制图
            plt.figure(figsize=(12, 8))
            pos = nx.spring_layout(self.graph, k=1, iterations=50)
            
            nx.draw(self.graph, pos, 
                   node_color=node_colors,
                   node_size=50,
                   edge_color='gray',
                   alpha=0.7,
                   with_labels=False)
            
            plt.title(f"UTG Community Structure ({len(communities)} communities)")
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"社区可视化图已保存到: {output_file}")
            
        except ImportError:
            print("警告: matplotlib未安装，无法生成可视化图")


def main():
    """
    主函数：UTG 层次Louvain聚类示例
    """
    # UTG数据文件夹路径
    utg_folder = r"c:\Projects\AndroidTaskAutomation\2_utg_clustering\utg\original_greedy_dfs_20251106_160351"
    
    # 创建聚类器
    clusterer = UTGLouvainClustering(utg_folder)
    
    # 配置层次聚类参数
    clusterer.max_clusters = 8  # 最大聚类数阈值
    clusterer.min_cluster_size = 3  # 最小聚类大小
    clusterer.resolution = 1.2  # 提高分辨率，倾向于更大的聚类
    
    # 加载UTG数据
    clusterer.load_utg_data()
    
    # 执行Louvain聚类
    final_partition = clusterer.run_louvain_clustering()
    
    # 处理状态和事件文件
    clusterer._process_states()
    clusterer._process_events()
    
    # 保存结果
    output_folder = "utg_louvain_results"
    clusterer.save_clustering_results(output_folder)
    
    # 生成可视化（可选）
    clusterer.visualize_communities("utg_communities.png")
    
    # 打印结果摘要
    communities = set(final_partition.values())
    print(f"\n=== UTG 层次Louvain聚类结果 ===")
    print(f"连通状态数: {len(clusterer.states_data)}")
    print(f"过滤孤立状态数: {len(clusterer.filtered_states)}")
    print(f"总转换数: {len(clusterer.events_data)}")
    print(f"层次聚类层数: {len(clusterer.hierarchical_levels)}")
    print(f"最终聚类数: {len(communities)}")
    print(f"最终模块度: {clusterer.modularity_history[-1]:.4f}")
    
    # 显示每层的聚类数变化
    if clusterer.hierarchical_levels:
        print(f"\n层次聚类过程:")
        for i, level_partition in enumerate(clusterer.hierarchical_levels):
            level_communities = len(set(level_partition.values()))
            print(f"  第{i}层: {level_communities} 个聚类")
    
    # 显示最终聚类大小分布
    community_sizes = defaultdict(int)
    for community in final_partition.values():
        community_sizes[community] += 1
    
    sorted_clusters = sorted(community_sizes.items(), key=lambda x: x[1], reverse=True)
    print(f"\n最终聚类大小分布（前10个）:")
    for i, (cluster_id, size) in enumerate(sorted_clusters[:10]):
        print(f"  聚类 {cluster_id}: {size} 个状态")
    
    if clusterer.filtered_states:
        print(f"\n过滤的孤立状态将被标记为 'filtered_isolated' 聚类")


if __name__ == "__main__":
    main()