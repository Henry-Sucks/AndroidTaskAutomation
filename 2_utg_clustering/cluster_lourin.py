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
        
        # 算法参数
        self.resolution = 1.0  # 分辨率参数，控制社区大小
        self.random_seed = 42
        
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
        
        print(f"UTG加载完成: {len(self.graph.nodes)} 个状态, {len(self.graph.edges)} 条转换")
    
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
    
    def run_louvain_clustering(self) -> Dict[str, str]:
        """
        执行Louvain算法进行UTG聚类（修复版）
        
        Returns:
            最终的分区结果 {state_str -> community_id}
        """
        print("开始执行Louvain聚类算法...")
        
        # 设置随机种子
        random.seed(self.random_seed)
        
        # 初始化：每个节点为一个社区
        current_partition = {node: str(i) for i, node in enumerate(self.weighted_graph.nodes())}
        current_graph = self.weighted_graph.copy()
        
        # 保存第一轮的分区结果（原始节点）
        first_round_partition = None
        
        iteration = 0
        while True:
            iteration += 1
            print(f"Louvain算法第 {iteration} 轮迭代...")
            
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
                print(f"算法收敛，最终模块度: {current_modularity:.4f}")
                
                # 如果收敛发生在第一轮，直接使用结果
                if iteration == 1:
                    self.final_partition = new_partition
                else:
                    # 否则使用第一轮的结果作为最终结果
                    self.final_partition = first_round_partition
                break
            
            # 存储分区结果
            if iteration == 1:
                # 第一轮的结果是在原始节点上的，直接保存
                self.partitions_history.append(new_partition.copy())
            
            # 阶段2：网络聚合
            current_graph = self._phase2_aggregate(current_graph, new_partition)
            current_partition = {node: str(i) for i, node in enumerate(current_graph.nodes())}
            
            print(f"第 {iteration} 轮完成，社区数: {len(set(new_partition.values()))}, 模块度: {current_modularity:.4f}")
        
        return self.final_partition
    
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
        
        statistics = {
            "total_states": len(self.states_data),
            "total_transitions": len(self.events_data),
            "num_communities": len(communities),
            "final_modularity": self.modularity_history[-1] if self.modularity_history else 0,
            "modularity_history": self.modularity_history,
            "community_sizes": dict(community_sizes),
            "largest_community_size": max(community_sizes.values()) if community_sizes else 0,
            "smallest_community_size": min(community_sizes.values()) if community_sizes else 0,
            "average_community_size": sum(community_sizes.values()) / len(community_sizes) if community_sizes else 0
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
            colors = plt.cm.Set3(np.linspace(0, 1, len(communities)))
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
    主函数：UTG Louvain聚类示例
    """
    # UTG数据文件夹路径
    utg_folder = r"c:\Projects\AndroidTaskAutomation\2_utg_clustering\utg\original_greedy_dfs_20251106_160351"
    
    # 创建聚类器
    clusterer = UTGLouvainClustering(utg_folder)
    
    # 加载UTG数据
    clusterer.load_utg_data()
    
    # 执行Louvain聚类
    final_partition = clusterer.run_louvain_clustering()
    
    # 保存结果
    output_folder = "utg_louvain_results"
    clusterer.save_clustering_results(output_folder)
    
    # 生成可视化（可选）
    clusterer.visualize_communities("utg_communities.png")
    
    # 打印结果摘要
    communities = set(final_partition.values())
    print(f"\n=== UTG Louvain聚类结果 ===")
    print(f"总状态数: {len(clusterer.states_data)}")
    print(f"总转换数: {len(clusterer.events_data)}")
    print(f"检测到的社区数: {len(communities)}")
    print(f"最终模块度: {clusterer.modularity_history[-1]:.4f}")


if __name__ == "__main__":
    main()