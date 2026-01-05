from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import numpy as np

# ==========================================
# 1. 数据结构定义 (Data Structures)
# ==========================================

@dataclass
class CurrentState:
    """输入：当前待定位的UI状态"""
    screenshot_path: str
    xml_tree: str  # 原始XML字符串
    activity_name: str
    foreground_package: str

@dataclass
class LocalizationResult:
    """输出：定位结果"""
    node_id: Optional[str]      # 在UTG中匹配到的节点ID
    cluster_id: Optional[str]   # 所属的功能簇ID
    confidence: float           # 置信度 (0.0 - 1.0)
    match_stage: str            # 匹配阶段: 'anchor_hit', 'vector_sim', 'structure_match', 'fallback'
    candidates: List[str]       # (调试用) Top-N 候选节点列表

# ==========================================
# 2. 定位器主类 (Main Localizer)
# ==========================================

class UILocalizer:
    """
    负责将当前 UI 状态映射回原始 UTG 图中的节点。
    采用 Coarse-to-Fine (由粗到细) 的三层筛选策略。
    """

    def __init__(self, utg_graph_data: Dict, embedding_model=None):
        """
        Args:
            utg_graph_data: 加载后的 UTG 数据 (包含 nodes, edges, clusters, summaries)
            embedding_model: 用于计算语义向量的模型 (如 Sentence-BERT 或 CLIP)
        """
        self.graph = utg_graph_data
        self.embedder = embedding_model
        
        # --- 预计算索引 (Indices) ---
        # 1. 锚点索引: { "Settings": ["node_1", "node_5"], "Login": ["node_10"] }
        self.anchor_index: Dict[str, List[str]] = {} 
        
        # 2. 簇中心向量: { "cluster_1": [vector], "cluster_2": [vector] }
        self.cluster_vectors: Dict[str, np.ndarray] = {}
        
        # 3. 节点摘要向量: { "node_1": [vector], ... }
        self.node_vectors: Dict[str, np.ndarray] = {}
        
        # 初始化构建索引
        self._build_offline_indices()

    # ==========================================
    # A. 预处理与索引构建 (Offline Indexing)
    # ==========================================
    
    def _build_offline_indices(self):
        """
        [初始化阶段]
        遍历 UTG，提取“硬特征”(Anchors) 和“软特征”(Embeddings) 构建快速检索索引。
        """
        # 1. 遍历所有节点
        #    - 提取 XML 中的 Title, Unique Button Text 作为 Anchor Key
        #    - 存入 self.anchor_index
        
        # 2. 遍历所有簇
        #    - 将 Cluster Summary 文本转化为向量，存入 self.cluster_vectors
        
        # 3. 遍历所有节点的 Summary
        #    - 将 Page Content Summary 转化为向量，存入 self.node_vectors
        pass

    # ==========================================
    # B. 在线定位主流程 (Online Pipeline)
    # ==========================================

    def locate(self, current_state: CurrentState) -> LocalizationResult:
        """
        [核心方法] 执行定位逻辑
        """
        # --- 步骤 0: 快速特征提取 ---
        # 从 current_state.xml 提取当前页面的 Anchors (Title, unique buttons)
        current_anchors = self._extract_anchors(current_state.xml_tree)
        
        # --- 步骤 1: 锚点硬匹配 (Level 1: Anchor Match) ---
        # 最快、最准。如果当前页面有独一无二的 Title (如 "About Version 1.0")，直接返回。
        anchor_match = self._match_by_anchors(current_anchors)
        if anchor_match and anchor_match.confidence > 0.95:
            return anchor_match

        # --- 步骤 2: 语义簇筛选 (Level 2: Cluster Filter) ---
        # 如果硬匹配失败（比如在列表页），先确定当前大概在哪个功能模块。
        # 利用 VLM 生成当前截图的临时描述，或直接利用 XML 文本。
        current_semantic_vec = self._get_state_embedding(current_state)
        candidate_cluster_id = self._predict_cluster(current_semantic_vec)
        
        # 获取该簇内的所有节点作为候选集
        candidate_nodes = self._get_nodes_in_cluster(candidate_cluster_id)

        # --- 步骤 3: 细粒度重排序 (Level 3: Fine-grained Re-ranking) ---
        # 在候选集中，结合“结构相似度”和“语义相似度”找出 Top-1
        best_node, score = self._rerank_candidates(current_state, candidate_nodes)

        if score > 0.8:
            return LocalizationResult(
                node_id=best_node, 
                cluster_id=candidate_cluster_id, 
                confidence=score, 
                match_stage='hybrid_rerank',
                candidates=[]
            )

        # --- 步骤 4: 兜底 (Fallback) ---
        # 无法定位，可能是新状态
        return LocalizationResult(None, None, 0.0, 'failed', [])

    # ==========================================
    # C. 具体的匹配逻辑实现
    # ==========================================

    def _extract_anchors(self, xml_str: str) -> List[str]:
        """
        从 XML 中提取关键文本特征。
        例如：Action Bar 的 Title，底部导航栏的高亮 Item，特定的 Button Text。
        """
        # 解析 XML
        # 查找 id 为 'title', 'action_bar' 的 TextView
        # 返回 ["Settings", "Account"]
        pass

    def _match_by_anchors(self, anchors: List[str]) -> Optional[LocalizationResult]:
        """
        查询 anchor_index，看是否有完全命中的节点。
        """
        # 如果 anchors 中的词在 index 中对应的节点 ID 是唯一的
        # return LocalizationResult(..., match_type='exact_anchor')
        pass

    def _predict_cluster(self, current_vec: np.ndarray) -> str:
        """
        计算当前向量与所有 self.cluster_vectors 的余弦相似度，返回 Top-1 Cluster ID。
        """
        # Cosine Similarity Calculation
        # Return best cluster ID
        pass

    def _rerank_candidates(self, state: CurrentState, candidates: List[str]) -> Tuple[str, float]:
        """
        对候选节点进行混合打分。
        Score = w1 * Structural_Sim(XML) + w2 * Semantic_Sim(Summary)
        """
        best_score = -1
        best_node = None
        
        for node_id in candidates:
            # 1. 计算结构相似度 (DOM Tree Edit Distance 或 Jaccard of Resource IDs)
            struct_score = self._calc_structure_score(state.xml_tree, self.graph.nodes[node_id].xml)
            
            # 2. 计算语义相似度 (向量相似度)
            semantic_score = self._calc_semantic_score(state, node_id)
            
            # 3. 加权 (结构通常比语义更敏感，但在内容变化大时语义更鲁棒)
            final_score = 0.4 * struct_score + 0.6 * semantic_score
            
            if final_score > best_score:
                best_score = final_score
                best_node = node_id
                
        return best_node, best_score

    def _get_state_embedding(self, state: CurrentState) -> np.ndarray:
        """
        获取当前状态的向量表示。
        策略：
        1. (快) 对 XML 中的所有可见文本做 Embedding。
        2. (慢) 调用 VLM 生成描述，再做 Embedding。
        """
        pass