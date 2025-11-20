import json
import random
import networkx as nx
from typing import Dict, List, Set, Tuple, Optional, Any
from pathlib import Path
from collections import defaultdict
import math
import re
import hashlib

class UTGLouvainClustering:
    """
    基于Louvain算法的UTG聚类系统 - 从utg.js文件读取数据
    
    用于将UI转换图(UTG)进行社区检测和层次聚类，
    识别功能相关的状态组和导航模式。
    """
    
    def __init__(self, utg_js_path: str):
        """
        初始化UTG Louvain聚类器
        
        Args:
            utg_js_path: UTG JavaScript文件路径 (utg.js)
        """
        self.utg_js_path = Path(utg_js_path)
        self.utg_folder = self.utg_js_path.parent
        
        if not self.utg_js_path.exists():
            raise FileNotFoundError(f"UTG file not found: {self.utg_js_path}")
        
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
        self.output_folder = self.utg_folder / f"{self.utg_js_path.stem}_louvain_clustered"
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
        
        print(f"初始化UTG Louvain聚类器: {self.utg_js_path}")
    
    def load_utg_data(self):
        """
        从utg.js文件加载UTG数据，构建图结构
        
        步骤：
        1. 解析utg.js文件中的nodes和edges数据
        2. 构建NetworkX图
        3. 计算边权重
        """
        print(f"正在加载UTG数据: {self.utg_js_path}")
        
        # 从utg.js文件加载数据
        self._load_from_utg_js()
        
        # 构建图结构
        self._build_graph()
        
        # 计算边权重
        self._calculate_edge_weights()
        
        # 过滤孤立状态
        self.filter_isolated_states()
        
        print(f"UTG加载完成: {len(self.graph.nodes)} 个连通状态, {len(self.graph.edges)} 条转换")
        if self.filtered_states:
            print(f"过滤了 {len(self.filtered_states)} 个孤立状态")
    
    def _load_from_utg_js(self):
        """
        从utg.js文件加载nodes和edges数据
        """
        with open(self.utg_js_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 解析nodes数据
        nodes_match = re.search(r'var\s+nodes\s*=\s*(\[.*?\]);', content, re.DOTALL)
        if nodes_match:
            nodes_str = nodes_match.group(1)
            # 将JavaScript对象转换为Python可解析的格式
            nodes_str = self._js_to_python_dict(nodes_str)
            try:
                nodes = eval(nodes_str)  # 安全的eval，因为我们控制输入
                
                # 转换nodes为states_data格式
                for node in nodes:
                    node_id = node['id']
                    self.states_data[node_id] = {
                        'state_str': node_id,
                        'step': node.get('step', 0),
                        'foreground_activity': node.get('activity', ''),
                        'image': node.get('image', ''),
                        'xml': node.get('xml', '')
                    }
            except Exception as e:
                print(f"解析nodes数据失败: {e}")
                return
        else:
            print("警告: 未找到nodes数据")
            return
        
        # 解析edges数据 
        # 首先尝试查找独立的edges变量
        edges_match = re.search(r'var\s+edges\s*=\s*(\[.*?\]);', content, re.DOTALL)
        if not edges_match:
            # 如果没有找到独立的edges变量，尝试在nodes数组后查找
            # 查找nodes数组结束位置
            nodes_end = nodes_match.end() if nodes_match else 0
            remaining_content = content[nodes_end:]
            
            # 查找下一个数组（可能是edges）
            array_match = re.search(r'(\[.*?\]);', remaining_content, re.DOTALL)
            if array_match:
                edges_str = array_match.group(1)
            else:
                print("警告: 未找到edges数据")
                return
        else:
            edges_str = edges_match.group(1)
        
        if edges_str:
            # 将JavaScript对象转换为Python可解析的格式
            edges_str = self._js_to_python_dict(edges_str)
            try:
                edges = eval(edges_str)  # 安全的eval，因为我们控制输入
                
                # 转换edges为events_data格式
                for edge in edges:
                    self.events_data.append({
                        'event_id': edge.get('id', ''),
                        'tag': edge.get('tag', ''),
                        'step': edge.get('step', 0),
                        'from': edge.get('from', ''),
                        'to': edge.get('to', ''),
                        'raw_action': edge.get('raw_action', '')
                    })
            except Exception as e:
                print(f"解析edges数据失败: {e}")
        
        print(f"从utg.js加载: {len(self.states_data)} 个状态, {len(self.events_data)} 个事件")
    
    # def _js_to_python_dict(self, js_str: str) -> str:
    #     """
    #     将JavaScript对象字符串转换为Python字典字符串
    #     """
    #     # 给属性名添加引号
    #     js_str = re.sub(r'(\s*)([a-zA-Z_$][a-zA-Z0-9_$]*)(\s*):', r'\1"\2"\3:', js_str)
        
    #     # 处理字符串值，确保使用双引号
    #     # 先处理单引号字符串
    #     js_str = re.sub(r"'([^']*?)'", r'"\1"', js_str)
        
    #     return js_str
    def _js_to_python_dict(self, js_str):
        """更健壮的JavaScript到Python转换"""
        # 1. 确保数组元素之间有逗号
        import re
        # 在 } 后面添加逗号（如果后面是 { 或空格）
        js_str = re.sub(r'\}\s*\{', '}, {', js_str)
        
        # 2. 转换JavaScript的null为Python的None
        js_str = js_str.replace('null', 'None')
        
        # 3. 确保键被引号包围
        js_str = re.sub(r'(\w+):', r"'\1':", js_str)
        
        return js_str
    
    def _build_graph(self):
        """
        构建NetworkX图结构
        """
        # 添加节点
        for state_str in self.states_data:
            self.graph.add_node(state_str, **self.states_data[state_str])
            self.weighted_graph.add_node(state_str, **self.states_data[state_str])
        
        # 添加边
        for event_data in self.events_data:
            start_state = event_data.get('from', '')
            stop_state = event_data.get('to', '')
            
            if start_state in self.states_data and stop_state in self.states_data:
                # 添加边到图中
                if self.graph.has_edge(start_state, stop_state):
                    # 如果边已存在，增加权重
                    self.graph[start_state][stop_state]['weight'] = self.graph[start_state][stop_state].get('weight', 0) + 1
                else:
                    # 添加新边
                    self.graph.add_edge(start_state, stop_state, weight=1, event_data=event_data)
                
                # 同样处理加权图
                if self.weighted_graph.has_edge(start_state, stop_state):
                    self.weighted_graph[start_state][stop_state]['weight'] = self.weighted_graph[start_state][stop_state].get('weight', 0) + 1
                else:
                    self.weighted_graph.add_edge(start_state, stop_state, weight=1)
    
    def _calculate_edge_weights(self):
        """
        计算边权重，基于多种因素：
        1. 转换频次 - 同一条边出现的次数
        2. 状态相似度 - 基于activity等属性
        """
        # 计算转换频次权重
        edge_frequency = defaultdict(int)
        for event_data in self.events_data:
            start_state = event_data.get('from', '')
            stop_state = event_data.get('to', '')
            if start_state in self.states_data and stop_state in self.states_data:
                edge_frequency[(start_state, stop_state)] += 1
        
        # 更新边权重
        for (start_state, stop_state), frequency in edge_frequency.items():
            if self.weighted_graph.has_edge(start_state, stop_state):
                # 基础权重是频次
                base_weight = frequency
                
                # 添加状态相似度权重
                similarity = self._calculate_state_similarity(start_state, stop_state)
                
                # 最终权重 = 频次 * (1 + 相似度)
                final_weight = base_weight * (1 + similarity)
                
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
        
        # 基于Activity的相似度
        activity1 = data1.get('foreground_activity', '')
        activity2 = data2.get('foreground_activity', '')
        if activity1 == activity2 and activity1:
            similarity_score += 0.5
        
        return min(similarity_score, 1.0)
    
    def filter_isolated_states(self):
        """
        过滤掉没有任何连接的孤立状态节点
        """
        print("正在过滤孤立状态...")
        
        # 找出所有在事件中出现的状态（有连接的状态）
        connected_states = set()
        
        for event_data in self.events_data:
            from_state = event_data.get('from', '')
            to_state = event_data.get('to', '')
            
            if from_state in self.states_data:
                connected_states.add(from_state)
            if to_state in self.states_data:
                connected_states.add(to_state)
        
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
            print(f"被过滤的孤立状态: {list(isolated_states)[:5]}{'...' if len(isolated_states) > 5 else ''}")
    
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
            print(f"\n执行第 {level} 层聚类...")
            
            # 检查是否应该停止层次聚类
            if self._should_stop_hierarchical_clustering(current_partition):
                print(f"达到停止条件，结束层次聚类")
                break
            
            # 构建聚类间的图
            cluster_graph = self._build_cluster_graph(current_partition)
            
            if len(cluster_graph.nodes()) <= 2:
                print(f"聚类数过少({len(cluster_graph.nodes())})，停止层次聚类")
                break
            
            # 对聚类图运行Louvain算法
            cluster_partition = self._run_cluster_louvain(cluster_graph)
            
            # 将聚类级别的分区映射回状态级别
            new_partition = self._map_cluster_partition_to_states(current_partition, cluster_partition)
            
            # 检查是否有改进
            if len(set(new_partition.values())) >= len(set(current_partition.values())):
                print(f"聚类数没有减少，停止层次聚类")
                break
            
            # 更新当前分区
            current_partition = new_partition
            self.hierarchical_levels.append(current_partition)
        
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
            print(f"  迭代 {iteration}: 当前聚类数 = {len(set(current_partition.values()))}")
            
            # 第一阶段：优化模块度
            new_partition = self._phase1_optimize(current_graph, current_partition)
            
            # 计算模块度
            modularity = self._calculate_modularity(current_graph, new_partition)
            self.modularity_history.append(modularity)
            print(f"    模块度: {modularity:.4f}")
            
            # 保存第一轮结果
            if iteration == 1:
                first_round_partition = new_partition.copy()
            
            # 检查收敛
            if self._is_converged(current_partition, new_partition):
                print(f"  算法收敛，停止迭代")
                break
            
            # 第二阶段：网络聚合
            aggregated_graph = self._phase2_aggregate(current_graph, new_partition)
            
            # 映射分区到聚合图
            aggregated_partition = {}
            community_to_new_id = {community: str(i) for i, community in enumerate(set(new_partition.values()))}
            for community in set(new_partition.values()):
                aggregated_partition[community] = community_to_new_id[community]
            
            # 更新图和分区
            current_graph = aggregated_graph
            current_partition = aggregated_partition
            
            # 防止无限循环
            if iteration > 50:
                print(f"  达到最大迭代次数，停止")
                break
        
        return first_round_partition or new_partition
    
    def _should_stop_hierarchical_clustering(self, partition: Dict[str, str]) -> bool:
        """
        判断是否应该停止层次聚类
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
            from_state = event_data.get('from', '')
            to_state = event_data.get('to', '')
            
            if from_state in partition and to_state in partition:
                cluster1 = partition[from_state]
                cluster2 = partition[to_state]
                
                if cluster1 != cluster2:  # 不同聚类间的连接
                    edge_key = tuple(sorted([cluster1, cluster2]))
                    cluster_connections[edge_key] += 1
        
        # 添加聚类间的边
        for (cluster1, cluster2), weight in cluster_connections.items():
            cluster_graph.add_edge(cluster1, cluster2, weight=weight)
        
        print(f"  构建聚类图: {len(cluster_graph.nodes())} 个聚类, {len(cluster_graph.edges())} 条连接")
        
        return cluster_graph
    
    def _run_cluster_louvain(self, cluster_graph: nx.Graph) -> Dict[str, str]:
        """
        对聚类图运行Louvain算法
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
        """
        new_partition = {}
        
        for state, cluster in state_partition.items():
            super_cluster = cluster_partition.get(cluster, cluster)
            new_partition[state] = super_cluster
        
        return new_partition
    
    def _phase1_optimize(self, graph: nx.Graph, initial_partition: Dict[str, str]) -> Dict[str, str]:
        """
        Louvain算法第一阶段：局部模块度优化
        """
        partition = initial_partition.copy()
        nodes = list(graph.nodes())
        
        improved = True
        while improved:
            improved = False
            random.shuffle(nodes)  # 随机顺序访问节点
            
            for node in nodes:
                current_community = partition[node]
                
                # 找到邻居社区
                neighbor_communities = set()
                for neighbor in graph.neighbors(node):
                    neighbor_communities.add(partition[neighbor])
                
                # 测试移动到每个邻居社区的模块度增益
                best_community = current_community
                best_gain = 0
                
                for target_community in neighbor_communities:
                    if target_community != current_community:
                        gain = self._calculate_modularity_gain(graph, partition, node, target_community)
                        if gain > best_gain:
                            best_gain = gain
                            best_community = target_community
                
                # 如果有改进，移动节点
                if best_community != current_community:
                    partition[node] = best_community
                    improved = True
        
        return partition
    
    def _calculate_modularity_gain(self, graph: nx.Graph, partition: Dict[str, str], 
                                  node: str, target_community: str) -> float:
        """
        计算将节点移动到目标社区的模块度增益
        """
        # 计算节点的度和社区内外连接权重
        node_degree = sum(graph[node][neighbor].get('weight', 1) 
                         for neighbor in graph.neighbors(node))
        
        # 计算移动到目标社区的权重增益
        weight_to_target = 0
        weight_from_current = 0
        
        current_community = partition[node]
        
        for neighbor in graph.neighbors(node):
            weight = graph[node][neighbor].get('weight', 1)
            if partition[neighbor] == target_community:
                weight_to_target += weight
            elif partition[neighbor] == current_community:
                weight_from_current += weight
        
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
            node_u, node_v = edge
            comm_u = partition[node_u]
            comm_v = partition[node_v]
            weight = graph[node_u][node_v].get('weight', 1)
            
            if comm_u == comm_v:
                # 社区内部边，累加到自环权重
                community_weights[(comm_u, comm_u)] += weight
            else:
                # 社区间边
                edge_key = tuple(sorted([comm_u, comm_v]))
                community_weights[edge_key] += weight
        
        # 添加聚合后的边
        for (comm_u, comm_v), weight in community_weights.items():
            if comm_u == comm_v:
                # 自环
                new_graph.add_edge(comm_u, comm_v, weight=weight)
            else:
                new_graph.add_edge(comm_u, comm_v, weight=weight)
        
        return new_graph
    
    def _calculate_modularity(self, graph: nx.Graph, partition: Dict[str, str]) -> float:
        """
        计算给定分区的模块度
        """
        if len(graph.edges()) == 0:
            return 0
        
        # 使用NetworkX的内置模块度计算
        communities = defaultdict(list)
        for node, community in partition.items():
            communities[community].append(node)
        
        community_list = list(communities.values())
        return nx.algorithms.community.modularity(graph, community_list, weight='weight')
    
    def _is_converged(self, old_partition: Dict[str, str], new_partition: Dict[str, str]) -> bool:
        """
        检查算法是否收敛
        """
        return old_partition == new_partition
    
    def save_clustered_utg_js(self):
        """
        生成包含聚类信息的UTG JavaScript文件
        
        生成格式：
        - nodes: 包含id、step、activity、image、xml、cluster_id属性
        - edges: 包含id、from、to、tag、step、raw_action属性
        """
        print("正在生成聚类后的UTG JavaScript文件...")
        
        # 准备节点数据，添加聚类信息
        nodes = []
        for state_str, state_data in self.states_data.items():
            cluster_id = self.final_partition.get(state_str, "cluster_unknown")
            
            node = {
                "id": state_str,
                "step": state_data.get('step', 0),
                "activity": state_data.get('foreground_activity', ''),
                "image": state_data.get('image', ''),
                "xml": state_data.get('xml', ''),
                "cluster_id": cluster_id,
                "cluster_color": self._generate_cluster_color(cluster_id)
            }
            nodes.append(node)
        
        # 准备边数据
        edges = []
        for event_data in self.events_data:
            edge = {
                "id": event_data.get('event_id', ''),
                "tag": event_data.get('tag', ''),
                "step": event_data.get('step', 0),
                "from": event_data.get('from', ''),
                "to": event_data.get('to', ''),
                "raw_action": event_data.get('raw_action', '')
            }
            edges.append(edge)
        
        # 生成JavaScript内容
        js_content = self._generate_clustered_js_content(nodes, edges)
        
        # 保存到与utg.js同目录，命名为utg_clustered.js
        output_js_file = self.utg_folder / "utg_clustered.js"
        with open(output_js_file, 'w', encoding='utf-8') as f:
            f.write(js_content)
        
        print(f"聚类后的UTG JavaScript文件已生成: {output_js_file}")
        print(f"包含 {len(nodes)} 个节点和 {len(edges)} 条边")
        print(f"聚类数: {len(set(self.final_partition.values()))}")
        
        return output_js_file
    
    def _generate_clustered_js_content(self, nodes: List[Dict], edges: List[Dict]) -> str:
        """
        生成包含聚类信息的JavaScript文件内容
        """
        # 生成节点的JavaScript数组
        nodes_js = "var nodes = [\n"
        for i, node in enumerate(nodes):
            comma = "," if i < len(nodes) - 1 else ""
            nodes_js += f"  {json.dumps(node, ensure_ascii=False)}{comma}\n"
        nodes_js += "];\n\n"
        
        # 生成边的JavaScript数组
        edges_js = "var edges = [\n"
        for i, edge in enumerate(edges):
            comma = "," if i < len(edges) - 1 else ""
            edges_js += f"  {json.dumps(edge, ensure_ascii=False)}{comma}\n"
        edges_js += "];\n\n"
        
        # 生成聚类信息
        clusters_info = self._generate_cluster_info()
        clusters_js = f"var clusters = {json.dumps(clusters_info, indent=2, ensure_ascii=False)};\n\n"
        
        # 组合完整内容
        cluster_count = len(set(node['cluster_id'] for node in nodes))
        js_content = f"""// UTG Clustered JavaScript File
// Generated by UTG Louvain Clustering Algorithm
// Original file: {self.utg_js_path.name}
// Total nodes: {len(nodes)}
// Total edges: {len(edges)}
// Total clusters: {cluster_count}
// Modularity: {(self.modularity_history[-1] if self.modularity_history else 0):.4f}

{nodes_js}{edges_js}{clusters_js}// Export for use in visualization
if (typeof module !== 'undefined' && module.exports) {{
    module.exports = {{ nodes: nodes, edges: edges, clusters: clusters }};
}}
"""
        
        return js_content
    
    def _generate_cluster_info(self) -> Dict[str, Any]:
        """
        生成聚类信息
        """
        cluster_info = {}
        cluster_counts = defaultdict(int)
        
        # 统计每个聚类的大小
        for state_str in self.states_data:
            cluster_id = self.final_partition.get(state_str, "cluster_unknown")
            cluster_counts[cluster_id] += 1
        
        # 为每个聚类生成信息
        for cluster_id, count in cluster_counts.items():
            cluster_info[cluster_id] = {
                "id": cluster_id,
                "size": count,
                "color": self._generate_cluster_color(cluster_id)
            }
        
        return cluster_info
    
    def _generate_cluster_color(self, cluster_id: str) -> str:
        """
        为聚类生成颜色
        """
        # 使用聚类ID的哈希值生成一致的颜色
        hash_value = int(hashlib.md5(cluster_id.encode()).hexdigest()[:6], 16)
        
        # 转换为RGB
        r = (hash_value >> 16) & 255
        g = (hash_value >> 8) & 255
        b = hash_value & 255
        
        # 确保颜色不会太暗
        r = max(r, 100)
        g = max(g, 100)
        b = max(b, 100)
        
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def save_clustering_results(self, output_folder: str = None):
        """
        保存聚类结果
        """
        if output_folder is None:
            output_folder = self.utg_folder / "louvain_results"
        
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
        for i, partition in enumerate(self.hierarchical_levels):
            with open(output_path / f"partition_level_{i}.json", 'w', encoding='utf-8') as f:
                json.dump(partition, f, indent=2, ensure_ascii=False)
        
        # 生成聚类后的UTG JavaScript文件
        self.save_clustered_utg_js()
        
        print(f"聚类结果已保存到: {output_path}")
    
    def _generate_clustering_statistics(self) -> Dict[str, Any]:
        """
        生成聚类统计信息
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
            for community in partition.values():
                level_sizes[community] += 1
            
            hierarchical_info.append({
                "level": level,
                "num_clusters": len(level_communities),
                "largest_cluster": max(level_sizes.values()) if level_sizes else 0,
                "smallest_cluster": min(level_sizes.values()) if level_sizes else 0,
                "average_cluster_size": sum(level_sizes.values()) / len(level_sizes) if level_sizes else 0
            })
        
        statistics = {
            "input_file": str(self.utg_js_path),
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


def main():
    """
    主函数：从utg.js文件进行UTG Louvain聚类
    """
    # UTG JavaScript文件路径
    utg_js_path = r"C:\Projects\AndroidTaskAutomation\2_utg_clustering\utg\sata-com.quora.android-ape-sata-running-minutes-30_utg\utg.js"
    
    # 创建聚类器
    clusterer = UTGLouvainClustering(utg_js_path)
    
    # 配置层次聚类参数
    clusterer.max_clusters = 8  # 最大聚类数阈值
    clusterer.min_cluster_size = 3  # 最小聚类大小
    clusterer.resolution = 1.2  # 提高分辨率，倾向于更大的聚类
    
    # 加载UTG数据
    clusterer.load_utg_data()
    
    # 执行Louvain聚类
    final_partition = clusterer.run_louvain_clustering()
    
    # # 保存结果
    # clusterer.save_clustering_results()
    
    # 打印结果摘要
    communities = set(final_partition.values())
    print(f"\n=== UTG Louvain聚类结果 ===")
    print(f"输入文件: {clusterer.utg_js_path.name}")
    print(f"连通状态数: {len(clusterer.states_data)}")
    print(f"过滤孤立状态数: {len(clusterer.filtered_states)}")
    print(f"总转换数: {len(clusterer.events_data)}")
    print(f"层次聚类层数: {len(clusterer.hierarchical_levels)}")
    print(f"最终聚类数: {len(communities)}")
    print(f"最终模块度: {clusterer.modularity_history[-1]:.4f}")
    
    # 显示每层的聚类数变化
    if clusterer.hierarchical_levels:
        print(f"\n层次聚类过程:")
        for i, partition in enumerate(clusterer.hierarchical_levels):
            cluster_count = len(set(partition.values()))
            print(f"  层级 {i}: {cluster_count} 个聚类")
    
    # 显示最终聚类大小分布
    community_sizes = defaultdict(int)
    for community in final_partition.values():
        community_sizes[community] += 1
    
    sorted_clusters = sorted(community_sizes.items(), key=lambda x: x[1], reverse=True)
    print(f"\n最终聚类大小分布（前10个）:")
    for i, (cluster_id, size) in enumerate(sorted_clusters[:10]):
        print(f"  聚类 {cluster_id}: {size} 个状态")
    
    if clusterer.filtered_states:
        print(f"\n过滤的孤立状态示例: {list(clusterer.filtered_states)[:5]}")
    
    print(f"\n聚类结果已保存到: {clusterer.utg_folder}/utg_clustered.js")


if __name__ == "__main__":
    main()