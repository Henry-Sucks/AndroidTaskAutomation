import json
import random
import networkx as nx
from typing import Dict, List, Set, Tuple, Optional, Any
from pathlib import Path
from collections import defaultdict
import math
import re
import hashlib
import os
# 引入 XML 解析库，用于计算 DOM 相似度
import xml.etree.ElementTree as ET
# 导入 VLM 客户端
from clients.vlm_client import VLMClient

class UTGLouvainClustering:
    """
    [增强版] 基于Louvain算法的UTG聚类系统
    
    改进点：
    1. 混合权重：结合 UI 结构相似度 (DOM) + 交互类型 (Action Type)
    2. Hub 节点处理：识别并降权通用导航页
    3. 后处理1：递归拆分超大簇，合并微小簇
    4. 后处理2：利用VLM/LLM总结簇，如果语义相似的簇需要合并
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
        
        # --- 新增增强配置参数 ---
        self.config = {
            # 交互类型权重
            'weights': {
                'basic_interaction': 1.0,  # 普通点击
                'strong_connection': 2.0,  # 列表点击、确认操作 (内容强相关)
                'weak_connection': 0.2,    # 返回(Back)、侧边栏、底部导航 (通用导航)
                'scroll': 0.5              # 滑动 (通常是同一页面的延伸)
            },
            # DOM 相似度阈值
            'dom_similarity_threshold': 0.65, # 超过此相似度视为同一界面的微变
            'dom_weight_bonus': 5.0,          # 高相似度时的权重加成
            
            # Hub 节点判定
            'hub_degree_percentile': 0.95,    # 度数超过 95% 分位数的视为 Hub
            
            # 后处理阈值
            'max_cluster_size': 50,           # 超过此大小尝试拆分
            'min_cluster_size': 5             # 小于此大小尝试合并
        }

        # 缓存 Hub 节点列表
        self.hub_nodes: Set[str] = set()
        
        # VLM 客户端
        self.vlm_client = VLMClient()
        
        print(f"初始化UTG Louvain聚类器: {self.utg_js_path}")
    
    def load_utg_data(self):
        """
        [增强版] 加载数据主流程
        """
        print(f"正在加载UTG数据: {self.utg_js_path}")
        self._load_from_utg_js()
        
        # 1. 构建基础图结构
        self._build_graph()
        
        # [新增] 2. 识别 Hub 节点 (导航中心)
        self._identify_hub_nodes()
        
        # [修改] 3. 计算增强型边权重 (核心优化点)
        self._calculate_hybrid_edge_weights()
        
        # 4. 过滤孤立节点
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
    
    # =========================================================================
    # 增强功能：Hub节点识别与混合权重计算
    # =========================================================================
    
    def _identify_hub_nodes(self):
        """
        [新增] 识别高中心性节点 (Hub Nodes)
        逻辑：计算 Degree Centrality，找出连接数异常高的节点（如主页、侧边栏根节点）。
        作用：在后续计算权重时，降低连接到 Hub 节点的边的权重，防止它把无关簇粘在一起。
        """
        if not self.graph.nodes():
            return
        
        # 1. 计算所有节点的度 (Degree)
        degrees = {}
        for node in self.graph.nodes():
            degrees[node] = len(list(self.graph.neighbors(node)))
                
        degree_values = list(degrees.values())
        
        if not degree_values:
            return
            
        # 2. 计算分位数阈值
        degree_values.sort()
        percentile_idx = int(len(degree_values) * self.config['hub_degree_percentile'])
        threshold = degree_values[min(percentile_idx, len(degree_values) - 1)]
        
        # 3. 将超过阈值的节点 ID 存入 self.hub_nodes
        for node, degree in degrees.items():
            if degree >= threshold:
                self.hub_nodes.add(node)
                
        print(f"识别出 {len(self.hub_nodes)} 个 Hub 节点 (阈值: {threshold})")

    def _calculate_hybrid_edge_weights(self):
        """
        [修改] 计算混合权重
        公式：Weight = (Base_Weight * Interaction_Factor * Hub_Penalty) + DOM_Similarity_Bonus
        """
        print("正在计算混合边权重 (Topology + Semantic)...")
        
        # 遍历所有边
        # 注意：这里需要处理 multigraph 的情况，因为两个节点间可能有多种操作
        # 这里简化逻辑，只取两个节点间最强的那条连接
        
        unique_edges = set()
        for event in self.events_data:
            u, v = event.get('from', ''), event.get('to', '')
            if u in self.states_data and v in self.states_data:
                unique_edges.add((u, v))

        for u, v in unique_edges:
            # 1. 获取交互类型权重 (Interaction Weight)
            w_interaction = self._get_interaction_weight(u, v)
            print(f"Debug: 计算交互权重 {u} -> {v}, 权重: {w_interaction}")

            # 2. 获取 DOM/视觉相似度 (Visual/Structural Similarity)  
            w_similarity = self._calculate_dom_similarity(u, v)

            # 3. Hub 节点惩罚 (Hub Penalty)
            # 如果 u 或 v 是 Hub 节点，且操作不是强相关操作，大幅降低权重
            w_hub_penalty = 1.0
            if (u in self.hub_nodes or v in self.hub_nodes) and w_interaction < 1.0:
                w_hub_penalty = 0.1

            # 4. 融合计算
            final_weight = w_interaction * w_hub_penalty
            
            # 如果相似度极高（可能是动态加载了个小图标），给予巨额奖励，强制锁死
            if w_similarity > self.config['dom_similarity_threshold']:
                final_weight += self.config['dom_weight_bonus']
            else:
                final_weight += w_similarity  # 加上微弱的相似度分

            # 更新图权重
            if self.weighted_graph.has_edge(u, v):
                self.weighted_graph[u][v]['weight'] = final_weight
            else:
                self.weighted_graph.add_edge(u, v, weight=final_weight)

    def _get_interaction_weight(self, u: str, v: str) -> float:
        """
        [新增] 根据操作类型返回权重
        """
        # 查找 u->v 的 event 数据
        for event in self.events_data:
            if event.get('from') == u and event.get('to') == v:
                raw_action = event.get('raw_action', '').lower()
                tag = event.get('tag', '').lower()
                
                print(f"Debug: 计算交互权重 {u} -> {v}, 操作: {raw_action}, 标签: {tag}")
                # 分析操作类型
                if 'back' in raw_action or 'back' in tag:
                    return self.config['weights']['weak_connection']
                elif 'scroll' in raw_action or 'scroll' in tag:
                    return self.config['weights']['scroll']
                elif any(keyword in raw_action or keyword in tag 
                        for keyword in ['list', 'item', 'confirm', 'submit']):
                    return self.config['weights']['strong_connection']
                else:
                    return self.config['weights']['basic_interaction']
                
        return self.config['weights']['basic_interaction']  # 默认权重

    def _calculate_dom_similarity(self, state1: str, state2: str) -> float:
        """
        [新增] 计算两个状态的 XML (DOM) 相似度
        """
        # 构建XML文件路径
        xml_file1 = self.utg_folder / "layout" / self.states_data[state1].get('xml', f"{state1}.xml")
        xml_file2 = self.utg_folder / "layout" / self.states_data[state2].get('xml', f"{state2}.xml")
        
        # 读取XML文件内容
        xml1 = self._read_xml_file(xml_file1)
        xml2 = self._read_xml_file(xml_file2)
        
        if not xml1 or not xml2:
            return 0.0
            
        try:
            # 提取所有 Resource ID 和 Class Name，计算 Jaccard 相似系数
            def extract_features(xml_str):
                features = set()
                try:
                    root = ET.fromstring(xml_str)
                    for elem in root.iter():
                        # 提取 resource-id
                        resource_id = elem.get('resource-id')
                        if resource_id:
                            features.add(f"id:{resource_id}")
                        
                        # 提取 class
                        class_name = elem.get('class')
                        if class_name:
                            features.add(f"class:{class_name}")
                            
                        # 提取 text (前10个字符)
                        text = elem.get('text', '')
                        if text and len(text.strip()) > 0:
                            features.add(f"text:{text[:10]}")
                            
                except ET.ParseError:
                    pass
                return features
            
            features1 = extract_features(xml1)
            features2 = extract_features(xml2)

            
            if not features1 and not features2:
                return 0.0
            if not features1 or not features2:
                return 0.0
                
            # Jaccard 相似度: Intersection / Union
            intersection = len(features1 & features2)
            union = len(features1 | features2)
            
            print(f"Debug: DOM相似度计算 {state1} <-> {state2}: "
                  f"交集={intersection}, 并集={union}, 相似度={intersection / union if union > 0 else 0.0}")
            return intersection / union if union > 0 else 0.0
            
        except Exception:
            return 0.0
    
    def _read_xml_file(self, xml_path: Path) -> str:
        """
        读取XML文件内容
        """
        try:
            if xml_path.exists():
                with open(xml_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                # 如果文件不存在，尝试其他可能的路径
                alternative_paths = [
                    self.utg_folder / "states" / f"{xml_path.stem}.xml",
                    self.utg_folder / f"{xml_path.stem}.xml"
                ]
                for alt_path in alternative_paths:
                    if alt_path.exists():
                        with open(alt_path, 'r', encoding='utf-8') as f:
                            return f.read()
                        
                print(f"警告: XML文件未找到: {xml_path}")
                return ""
        except Exception as e:
            print(f"读取XML文件失败 {xml_path}: {e}")
            return ""
    
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
        
        # [新增] 后处理：优化簇结构
        refined_partition = self._post_process_clusters(self.final_partition)
        self.final_partition = refined_partition
        
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
    
    def save_clustering_results(self, output_folder: Optional[str] = None):
        """
        保存聚类结果
        """
        if output_folder is None:
            output_folder = str(self.utg_folder / "louvain_results")
        
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
    
    # =========================================================================
    # 后处理与VLM语义修正功能
    # =========================================================================
    
    def _post_process_clusters(self, partition: Dict[str, str]) -> Dict[str, str]:
        """
        [新增] 后处理管道
        """
        print("开始后处理：优化簇结构...")
        new_partition = partition.copy()
        
        # 1. 递归拆分超大簇 (Recursive Split)
        # 对节点数 > max_cluster_size 的簇，在簇内部单独再跑一次 Louvain 或 K-Means
        new_partition = self._split_large_clusters(new_partition)
        
        # 2. 合并微小簇 (Merge Small Clusters)
        # 对节点数 < min_cluster_size 的簇，将其合并到连接最紧密的邻居簇
        new_partition = self._merge_small_clusters(new_partition)
        
        return new_partition

    def _split_large_clusters(self, partition: Dict[str, str]) -> Dict[str, str]:
        """
        [新增] 拆分过大的簇
        """
        print("检查并拆分过大的簇...")
        new_partition = partition.copy()
        
        # 统计每个 Cluster ID 的节点列表
        clusters = defaultdict(list)
        for node, cluster_id in partition.items():
            clusters[cluster_id].append(node)
        
        cluster_id_counter = max(int(cid) for cid in clusters.keys()) + 1 if clusters else 0
        
        for cluster_id, nodes in clusters.items():
            if len(nodes) > self.config['max_cluster_size']:
                print(f"self.config['max_cluster_size'] = {self.config['max_cluster_size']}")
                print(f"  拆分簇 {cluster_id} ({len(nodes)} 个节点)")
                
                # 取出该 Cluster 的子图
                subgraph = self.weighted_graph.subgraph(nodes).copy()
                
                if len(subgraph.nodes()) < 2:
                    continue
                
                # 对子图运行单次 Louvain
                sub_partition = {node: str(i) for i, node in enumerate(subgraph.nodes())}
                refined_sub_partition = self._phase1_optimize(subgraph, sub_partition)
                
                # 为生成的子簇分配新的 ID
                sub_communities = set(refined_sub_partition.values())
                if len(sub_communities) > 1:  # 成功拆分
                    for node in nodes:
                        sub_cluster = refined_sub_partition.get(node, '0')
                        new_cluster_id = f"{cluster_id}_{sub_cluster}"
                        new_partition[node] = new_cluster_id
        
        return new_partition

    def _merge_small_clusters(self, partition: Dict[str, str]) -> Dict[str, str]:
        """
        [新增] 合并过小的簇 (Orphans)
        """
        print("检查并合并过小的簇...")
        new_partition = partition.copy()
        
        max_iterations = 10  # 防止无限循环
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            changed = False
            
            # 统计 Cluster sizes
            cluster_sizes = defaultdict(int)
            for cluster_id in new_partition.values():
                cluster_sizes[cluster_id] += 1
            
            # 找到 size < min_cluster_size 的簇
            small_clusters = [cid for cid, size in cluster_sizes.items() 
                            if size < self.config['min_cluster_size']]
            
            if not small_clusters:
                break
                
            for small_cluster_id in small_clusters:
                # 获取该小簇的所有节点
                small_nodes = [node for node, cid in new_partition.items() 
                             if cid == small_cluster_id]
                
                # 计算它与所有邻居簇的边权重总和
                neighbor_weights = defaultdict(float)
                
                for node in small_nodes:
                    for neighbor in self.weighted_graph.neighbors(node):
                        neighbor_cluster = new_partition.get(neighbor)
                        if neighbor_cluster and neighbor_cluster != small_cluster_id:
                            weight = self.weighted_graph[node][neighbor].get('weight', 1.0)
                            neighbor_weights[neighbor_cluster] += weight
                
                # 找到连接最强的邻居簇
                if neighbor_weights:
                    best_neighbor = max(neighbor_weights.items(), key=lambda x: x[1])[0]
                    
                    # 将该小簇的所有节点重命名为邻居簇 ID
                    for node in small_nodes:
                        new_partition[node] = best_neighbor
                    
                    changed = True
                    print(f"  合并小簇 {small_cluster_id} ({len(small_nodes)} 节点) -> 簇 {best_neighbor}")
            
            if not changed:
                break
        
        return new_partition

    def refine_clusters_with_vlm(self):
        """
        [新增] 第五阶段：基于 VLM 的语义修正
        
        1. Pruning: 检查簇内节点是否与簇中心语义一致，不一致则剔除。
        2. Reassignment: 将游离节点重新分配到语义最匹配的簇。
        """
        print("启动 VLM 语义修正流程...")
        
        # 1. 识别每个簇的 Representative (中心节点)
        cluster_representatives = self._identify_cluster_representatives()
        
        # 2. 剔除阶段 (Pruning)
        # 将不符合簇语义的节点变为 'orphan' (无主节点)
        orphans = self._prune_clusters_semantically(cluster_representatives)
        
        # 3. 再分配阶段 (Reassignment)
        # 尝试将 orphans 分配给最相似的簇
        self._reassign_orphans_semantically(orphans, cluster_representatives)
        
        return self.final_partition

    def _identify_cluster_representatives(self) -> Dict[str, str]:
        """
        找出每个簇的'中心节点' (Representative Node)
        策略：选择簇内 Degree Centrality (度中心性) 最高的节点。
        Returns: {cluster_id: state_id}
        """
        representatives = {}
        clusters = defaultdict(list)
        for node, cluster_id in self.final_partition.items():
            clusters[cluster_id].append(node)
            
        for c_id, nodes in clusters.items():
            # 在子图中找度最大的节点
            subgraph = self.graph.subgraph(nodes)
            # 排序：度数降序
            degree_list = []
            for node in subgraph.nodes():
                degree = len(list(subgraph.neighbors(node)))
                degree_list.append((node, degree))
            sorted_nodes = sorted(degree_list, key=lambda x: x[1], reverse=True)
            if sorted_nodes:
                representatives[c_id] = sorted_nodes[0][0]  # 取度最高的作为代表
                
        print(f"已选定 {len(representatives)} 个簇代表节点")
        return representatives

    def _prune_clusters_semantically(self, representatives: Dict[str, str]) -> List[str]:
        """
        遍历簇内节点，与代表节点进行 VLM 对比。
        如果不相似，从簇中移除。
        """
        orphans = []
        
        # 为了节省成本，我们只检查"可疑节点"：
        # 1. 或者是通过 'weak_connection' 连进来的节点
        # 2. 或者是距离中心节点路径较远的节点
        # 这里演示简单逻辑：随机抽样检查 或 检查所有非中心节点 (成本较高)
        
        for state_id, cluster_id in list(self.final_partition.items()):
            rep_id = representatives.get(cluster_id)
            
            # 跳过代表节点本身
            if state_id == rep_id:
                continue
                
            # 获取截图路径 (假设 state_data 里有图片路径)
            img_target = self.states_data[state_id].get('image')
            img_rep = self.states_data[rep_id].get('image') if rep_id else None
            
            if not img_target or not img_rep:
                continue
            
            # 调用 VLM 判断一致性
            # is_consistent: bool, reason: str
            is_consistent, reason = self._call_vlm_compare(img_target, img_rep)
            
            if not is_consistent:
                print(f"剔除节点: {state_id} 不属于簇 {cluster_id} (代表: {rep_id})。原因: {reason}")
                # 从当前分区中移除
                del self.final_partition[state_id]
                orphans.append(state_id)
        
        return orphans

    def _reassign_orphans_semantically(self, orphans: List[str], representatives: Dict[str, str]):
        """
        将孤儿节点与所有簇代表进行对比，分配给最相似的簇。
        """
        for orphan_id in orphans:
            best_cluster = None
            max_score = 0.0
            
            orphan_img = self.states_data[orphan_id].get('image')
            if not orphan_img:
                continue
            
            # 遍历候选簇 (可以只选 Top-K 个可能的邻居簇来减少 API 调用)
            for cluster_id, rep_id in representatives.items():
                rep_img = self.states_data[rep_id].get('image')
                if not rep_img:
                    continue
                
                # 调用 VLM 获取相似度分数 (0-10分)
                score, _ = self._call_vlm_score(orphan_img, rep_img)
                
                if score > max_score:
                    max_score = score
                    best_cluster = cluster_id
            
            # 设定阈值，比如 7/10 分才准入
            if best_cluster and max_score >= 7.0:
                print(f"重新分配: {orphan_id} -> 簇 {best_cluster} (得分: {max_score})")
                self.final_partition[orphan_id] = best_cluster
            else:
                print(f"节点 {orphan_id} 无法归类，保持孤立或新建簇")
                # 可选：为它创建一个新簇

    # ================= VLM 接口部分 =================
    
    def _get_full_image_path(self, image_filename: str) -> str:
        """
        将相对图片文件名转换为完整的绝对路径
        """
        if not image_filename:
            return ""
        
        # 如果已经是绝对路径，直接返回
        if os.path.isabs(image_filename) and os.path.exists(image_filename):
            return image_filename
        
        # 尝试不同的可能路径
        possible_paths = [
            # UTG目录下的screenshot文件夹
            self.utg_folder / "screenshot" / image_filename,
            # UTG目录下的states文件夹  
            self.utg_folder / "states" / image_filename,
            # UTG目录下直接存放
            self.utg_folder / image_filename,
            # 父目录下的screenshot文件夹
            self.utg_folder.parent / "screenshot" / image_filename
        ]
        
        # 检查哪个路径存在
        for path in possible_paths:
            if path.exists():
                return str(path)
        
        # 如果都找不到，返回第一个可能的路径（用于调试）
        fallback_path = self.utg_folder / "states" / image_filename
        print(f"警告: 图片文件未找到 '{image_filename}'，使用回退路径: {fallback_path}")
        return str(fallback_path)

    def _call_vlm_compare(self, img_path1, img_path2) -> Tuple[bool, str]:
        """
        Prompt 设计：二分类判断 (Yes/No)
        """
        prompt = """
        I will provide two screenshots from an Android app.
        Image 1 is the 'Representative' of a functional cluster (e.g., Music Player, Settings, Search).
        Image 2 is a specific page I want to verify.
        
        Task: Does Image 2 functionally belong to the same specific module as Image 1?
        - Ignore minor visual differences (e.g., different song titles, scrolled content).
        - Focus on the Core Functionality (e.g., both are about editing user profile).
        - If Image 2 is a completely different screen (e.g., Settings vs. Chat), answer NO.
        
        Response JSON format: {"result": true/false, "reason": "brief explanation"}
        """
        try:
            # 确保传递给VLM的是完整的绝对路径
            full_img_path1 = self._get_full_image_path(img_path1)
            
            print(f"Debug: VLM调用图片路径: {full_img_path1}")
            
            # 调用 VLM 客户端
            response = self.vlm_client.run(prompt, full_img_path1)
            content = response.get('content', '')
            
            # 简单解析 JSON 响应
            import json
            try:
                result_data = json.loads(content)
                return result_data.get('result', False), result_data.get('reason', 'No reason provided')
            except:
                # 如果不是 JSON，则通过关键词判断
                if 'true' in content.lower() or 'yes' in content.lower():
                    return True, "VLM indicated similarity"
                else:
                    return False, "VLM indicated difference"
        except Exception as e:
            print(f"VLM compare error: {e}")
            return True, "VLM error - assumed similar"  # 保守策略

    def _call_vlm_score(self, img_path1, img_path2) -> Tuple[float, str]:
        """
        Prompt 设计：打分 (0-10)
        """
        prompt = """
        Compare the functional similarity of these two Android screenshots (0-10).
        - 10: Identical functionality (just different content).
        - 8-9: Same module, slightly different state (e.g., list vs detail in same flow).
        - 5-7: Related but distinct (e.g., Search bar vs Search results).
        - 0-4: Completely unrelated.
        
        Return JSON: {"score": 8.5, "reason": "..."}
        """
        try:
            # 确保传递给VLM的是完整的绝对路径
            full_img_path1 = self._get_full_image_path(img_path1)
            
            print(f"Debug: VLM评分图片路径: {full_img_path1}")
            
            response = self.vlm_client.run(prompt, full_img_path1)
            content = response.get('content', '')
            
            import json
            try:
                result_data = json.loads(content)
                return float(result_data.get('score', 0.0)), result_data.get('reason', 'No reason provided')
            except:
                # 提取数字分数
                import re
                score_match = re.search(r'(\d+\.?\d*)', content)
                if score_match:
                    return float(score_match.group(1)), "Extracted from VLM response"
                else:
                    return 0.0, "Could not parse VLM score"
        except Exception as e:
            print(f"VLM score error: {e}")
            return 0.0, "VLM error"


def main():
    """
    主函数：从utg.js文件进行UTG Louvain聚类（增强版）
    """
    # UTG JavaScript文件路径
    utg_js_path = r"C:\\Projects\\AndroidTaskAutomation\\2_clustering\\utg\\NetEase Cloud Music\\utg.js"
    
    # 创建聚类器
    clusterer = UTGLouvainClustering(utg_js_path)
    
    # [增强] 配置层次聚类参数
    clusterer.max_clusters = 8  # 最大聚类数阈值
    clusterer.min_cluster_size = 3  # 最小聚类大小
    clusterer.resolution = 1.2  # 提高分辨率，倾向于更大的聚类
    
    # [增强] 配置新功能参数
    clusterer.config['max_cluster_size'] = 50  # 超大簇拆分阈值
    clusterer.config['min_cluster_size'] = 10   # 微小簇合并阈值
    
    # 加载UTG数据（包含Hub节点识别和混合权重计算）
    clusterer.load_utg_data()
    
    # 执行Louvain聚类（包含后处理）
    final_partition = clusterer.run_louvain_clustering()
    
    # # [可选] VLM语义修正（需要有效的截图路径）
    # final_partition = clusterer.refine_clusters_with_vlm()
    
    # 保存结果
    clusterer.save_clustering_results()
    
    # 打印结果摘要
    communities = set(final_partition.values())
    print(f"\n=== UTG Louvain聚类结果（增强版） ===")
    print(f"输入文件: {clusterer.utg_js_path.name}")
    print(f"连通状态数: {len(clusterer.states_data)}")
    print(f"过滤孤立状态数: {len(clusterer.filtered_states)}")
    print(f"Hub节点数: {len(clusterer.hub_nodes)}")
    print(f"总转换数: {len(clusterer.events_data)}")
    print(f"层次聚类层数: {len(clusterer.hierarchical_levels)}")
    print(f"最终聚类数: {len(communities)}")
    if clusterer.modularity_history:
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
    
    if clusterer.hub_nodes:
        print(f"\nHub节点示例: {list(clusterer.hub_nodes)[:5]}")
    
    print(f"\n聚类结果已保存到: {clusterer.utg_folder}/utg_clustered.js")
    print("\n增强功能说明：")
    print("  ✓ Hub节点识别与权重调整")
    print("  ✓ DOM相似度计算")
    print("  ✓ 交互类型权重分析")
    print("  ✓ 超大簇自动拆分")
    print("  ✓ 微小簇自动合并")
    print("  • VLM语义修正 (可选启用)")


if __name__ == "__main__":
    main()