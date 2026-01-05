"""
UTG 纯语义聚类 - 基于Embedding向量索引 + VLM在线判断

核心思路：
1. 初筛：使用embedding向量检索最相似的簇（快速）
2. 精判：不确定时使用VLM判断是否属于现有簇或创建新簇（精确）
3. 在线聚类：边遍历边分簇，动态创建簇

输入：utg.js 或 utg_clustered.js
输出：utg_clustered.js + cluster_summaries.json
"""

import json
import re
import threading
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# 导入CLIP模型
try:
    from sentence_transformers import SentenceTransformer
    from PIL import Image
    CLIP_AVAILABLE = True
except ImportError:
    CLIP_AVAILABLE = False
    print("警告: sentence_transformers未安装，将使用简化的embedding")
    print("安装命令: pip install sentence-transformers pillow")

# 导入客户端
import sys
sys.path.append(str(Path(__file__).parent.parent / "3_context_summarization"))
from clients.vlm_client import VLMClient


@dataclass
class ClusterSummary:
    """簇摘要数据结构"""
    cluster_id: str
    cluster_name: str
    functional_description: str
    node_ids: List[str]
    representative_node_id: str  # 代表性节点（用于向量索引）
    node_count: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)


class VectorIndex:
    """
    简化的向量索引（使用numpy实现）
    如需高性能，可替换为FAISS
    """
    
    def __init__(self, embedding_dim: int = 512):
        self.embedding_dim = embedding_dim
        self.vectors: List[np.ndarray] = []  # 向量列表
        self.cluster_ids: List[str] = []  # 对应的簇ID
        self.counts: List[int] = []  # 记录每个簇累积了多少向量
        
    def add(self, embedding: np.ndarray, cluster_id: str):
        """添加簇的代表向量"""
        if embedding.shape[0] != self.embedding_dim:
            raise ValueError(f"Embedding dimension mismatch: {embedding.shape[0]} != {self.embedding_dim}")
        
        self.vectors.append(embedding)
        self.cluster_ids.append(cluster_id)
        self.counts.append(1)  # 初始化计数
    
    def search(self, query_embedding: np.ndarray, top_k: int = 1) -> List[Tuple[str, float]]:
        """
        搜索最相似的簇
        
        Returns:
            List[(cluster_id, similarity_score)]
        """
        if len(self.vectors) == 0:
            return []
        
        # 计算余弦相似度
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        
        similarities = []
        for i, vec in enumerate(self.vectors):
            vec_norm = vec / (np.linalg.norm(vec) + 1e-8)
            similarity = np.dot(query_norm, vec_norm)
            similarities.append((self.cluster_ids[i], float(similarity)))
        
        # 按相似度降序排序
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
    
    def update(self, cluster_id: str, new_embedding: np.ndarray):
        """更新簇的代表向量（使用增量平均）"""
        if cluster_id in self.cluster_ids:
            idx = self.cluster_ids.index(cluster_id)
            n = self.counts[idx]
            
            # 正确的累积平均公式
            self.vectors[idx] = (self.vectors[idx] * n + new_embedding) / (n + 1)
            # 重新归一化，保证 Cosine Similarity 有效
            self.vectors[idx] = self.vectors[idx] / (np.linalg.norm(self.vectors[idx]) + 1e-8)
            
            self.counts[idx] += 1
    
    def remove(self, cluster_id: str):
        """删除簇向量"""
        if cluster_id in self.cluster_ids:
            idx = self.cluster_ids.index(cluster_id)
            del self.vectors[idx]
            del self.cluster_ids[idx]
            del self.counts[idx]


class ClusterRegistry:
    """簇注册表 - 管理所有簇的摘要信息"""
    
    def __init__(self):
        self.clusters: Dict[str, ClusterSummary] = {}
        self.next_id = 0
        self.lock = threading.Lock()  # 线程安全
    
    def create_new(self, cluster_name: str, description: str, 
                   representative_node_id: str) -> str:
        """创建新簇"""
        with self.lock:
            cluster_id = f"semantic_cluster_{self.next_id}"
            self.next_id += 1
            
            self.clusters[cluster_id] = ClusterSummary(
                cluster_id=cluster_id,
                cluster_name=cluster_name,
                functional_description=description,
                node_ids=[],
                representative_node_id=representative_node_id,
                node_count=0
            )
            
            return cluster_id
    
    def add_node(self, cluster_id: str, node_id: str):
        """向簇中添加节点"""
        if cluster_id in self.clusters:
            with self.lock:
                if node_id not in self.clusters[cluster_id].node_ids:
                    self.clusters[cluster_id].node_ids.append(node_id)
                    self.clusters[cluster_id].node_count = len(self.clusters[cluster_id].node_ids)
    
    def get_active_summaries(self) -> List[Dict[str, str]]:
        """获取所有活跃簇的摘要（用于VLM判断）"""
        with self.lock:
            return [
                {
                    'cluster_id': c.cluster_id,
                    'cluster_name': c.cluster_name,
                    'description': c.functional_description
                }
                for c in self.clusters.values()
            ]
    
    def get_cluster(self, cluster_id: str) -> Optional[ClusterSummary]:
        """获取簇信息"""
        return self.clusters.get(cluster_id)
    
    def to_dict(self) -> Dict[str, Dict]:
        """导出为字典"""
        return {cid: c.to_dict() for cid, c in self.clusters.items()}


class PureSemanticClustering:
    """
    纯语义聚类器
    
    基于embedding向量索引 + VLM在线判断
    """
    
    def __init__(self, 
                 utg_path: str,
                 high_similarity_threshold: float = 0.85,
                 embedding_model: str = "clip"):
        """
        初始化聚类器
        
        Args:
            utg_path: UTG文件路径 (utg.js)
            high_similarity_threshold: 高相似度阈值，超过则直接分配
            embedding_model: embedding模型选择 ('clip', 'vlm-embedding', etc.)
        """
        self.utg_path = Path(utg_path)
        self.utg_folder = self.utg_path.parent
        self.high_threshold = high_similarity_threshold
        self.embedding_model = embedding_model
        
        # 数据结构
        self.nodes: List[Dict] = []
        self.node_map: Dict[str, Dict] = {}
        
        # 聚类组件
        self.vector_index = VectorIndex(embedding_dim=512)
        self.cluster_registry = ClusterRegistry()
        
        # VLM客户端
        self.vlm_client = VLMClient()
        
        # CLIP模型（如果可用）
        self.clip_model = None
        if CLIP_AVAILABLE and embedding_model == 'clip':
            print("正在加载 CLIP 模型...")
            try:
                self.clip_model = SentenceTransformer('clip-ViT-B-32')
                print("✓ CLIP 模型加载成功")
            except Exception as e:
                print(f"警告: CLIP模型加载失败: {e}")
                print("将使用简化的embedding方法")
        
        # 统计信息
        self.stats = {
            'total_nodes': 0,
            'direct_assignments': 0,  # 直接分配（高相似度）
            'vlm_judgments': 0,       # VLM判断次数
            'new_clusters_created': 0
        }
        
        print(f"初始化纯语义聚类器: {self.utg_path}")
        print(f"  高相似度阈值: {self.high_threshold}")
        print(f"  Embedding模型: {self.embedding_model}")
    
    # =========================================================================
    # 数据加载
    # =========================================================================
    
    def load_utg_data(self):
        """加载UTG数据"""
        print("\n=== 加载UTG数据 ===")
        
        with open(self.utg_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取nodes数组
        nodes_match = re.search(r'var\s+nodes\s*=\s*(\[.*?\]);', content, re.DOTALL)
        if not nodes_match:
            raise ValueError("无法从UTG文件中提取nodes数据")
        
        nodes_str = nodes_match.group(1)
        nodes_str = self._js_to_python(nodes_str)
        
        try:
            self.nodes = eval(nodes_str)
            self.node_map = {n['id']: n for n in self.nodes}
            self.stats['total_nodes'] = len(self.nodes)
            print(f"✓ 加载 {len(self.nodes)} 个节点")
        except Exception as e:
            print(f"解析nodes失败: {e}")
            raise
    
    def _js_to_python(self, js_str: str) -> str:
        """JavaScript转Python"""
        js_str = re.sub(r'\}\s*\{', '}, {', js_str)
        js_str = js_str.replace('null', 'None')
        js_str = re.sub(r'(\w+):', r"'\1':", js_str)
        return js_str
    
    # =========================================================================
    # Embedding生成
    # =========================================================================
    
    def get_embedding(self, node: Dict) -> np.ndarray:
        """
        获取节点的embedding向量
        
        策略：
        1. 如果有CLIP模型且有截图，使用CLIP图像embedding
        2. 如果有CLIP模型无截图，使用CLIP文本embedding
        3. 否则使用简化的embedding方法
        """
        image_file = node.get('image', '')
        image_path = self.utg_folder / "states" / image_file
        
        try:
            if self.clip_model is not None:
                if image_file and image_path.exists():
                    # CLIP 图像 Embedding
                    img = Image.open(image_path)
                    embedding = self.clip_model.encode(img)
                    return embedding.astype(np.float32)
                else:
                    # CLIP 文本 Embedding (Fallback)
                    text = node.get('activity', '') + " " + node.get('id', '')
                    embedding = self.clip_model.encode(text)
                    return embedding.astype(np.float32)
            else:
                # 使用原有方法
                if image_file and image_path.exists():
                    return self._get_image_embedding(str(image_path))
                else:
                    return self._get_text_embedding(node)
        except Exception as e:
            print(f"  Embedding error for node {node.get('id', 'unknown')}: {e}")
            # 返回零向量
            return np.zeros(512, dtype=np.float32)
    
    def _get_image_embedding(self, image_path: str) -> np.ndarray:
        """
        获取图像的embedding向量
        
        实现方式：
        1. 使用VLM的embedding接口（如果支持）
        2. 或调用CLIP等模型
        3. 或使用VLM生成描述后转为文本embedding
        """
        try:
            # 方法1: 直接调用VLM的embedding接口（如果支持）
            # embedding = self.vlm_client.get_embedding(image_path)
            
            # 方法2: 使用VLM生成描述，然后转为文本embedding
            result = self.vlm_client.run(
                prompt="Describe this UI screen in one sentence focusing on its primary function.",
                image_url=image_path
            )
            description = result.get('content', '')
            
            # 简单的文本embedding（实际应使用sentence-transformers等）
            embedding = self._text_to_embedding(description)
            
            return embedding
            
        except Exception as e:
            print(f"  警告: 获取图像embedding失败 ({image_path}): {e}")
            # 返回随机向量作为fallback
            return np.random.randn(512).astype(np.float32)
    
    def _get_text_embedding(self, node: Dict) -> np.ndarray:
        """基于节点文本特征生成embedding"""
        features = []
        
        # 提取文本特征
        if 'activity' in node:
            features.append(node['activity'])
        if 'id' in node:
            features.append(node['id'])
        
        text = " ".join(features)
        return self._text_to_embedding(text)
    
    def _text_to_embedding(self, text: str) -> np.ndarray:
        """
        文本转embedding
        
        简单实现：使用hash函数
        实际应使用: sentence-transformers, OpenAI embeddings等
        """
        # 简化版：使用字符hash生成伪embedding
        # TODO: 替换为真实的embedding模型
        import hashlib
        hash_obj = hashlib.sha512(text.encode())
        hash_bytes = hash_obj.digest()
        
        # 转为512维向量
        embedding = np.frombuffer(hash_bytes[:512], dtype=np.uint8).astype(np.float32)
        
        # 归一化
        embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
        
        return embedding
    
    # =========================================================================
    # 核心聚类逻辑
    # =========================================================================
    
    def run_clustering(self, max_workers: int = 5, use_parallel: bool = False):
        """
        执行在线聚类
        
        Args:
            max_workers: 并行处理的线程数（仅当use_parallel=True时使用）
            use_parallel: 是否使用并行处理（注意：VLM调用可能有并发限制）
        
        流程：
        1. 遍历所有节点
        2. 对每个节点：
           a. 计算embedding
           b. 向量索引检索最相似的簇
           c. 如果相似度高，直接分配
           d. 否则调用VLM判断
        """
        if use_parallel:
            self._run_clustering_parallel(max_workers)
        else:
            self._run_clustering_sequential()
        
        print("\n=== 聚类完成 ===")
        self._print_statistics()
    
    def _run_clustering_sequential(self):
        """串行聚类处理"""
        print("\n=== 开始纯语义聚类（串行模式） ===")
        
        for i, node in enumerate(self.nodes):
            node_id = node['id']
            
            if (i + 1) % 10 == 0:
                print(f"处理进度: {i+1}/{len(self.nodes)} ({(i+1)/len(self.nodes)*100:.1f}%)")
            
            # 处理单个节点
            cluster_id = self._process_node(node)
            
            # 更新节点的cluster_id
            node['cluster_id'] = cluster_id
    
    def _run_clustering_parallel(self, max_workers: int):
        """并行聚类处理"""
        print(f"\n=== 开始并行纯语义聚类 (Workers: {max_workers}) ===")
        
        processed_count = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_node = {
                executor.submit(self._process_node, node): node 
                for node in self.nodes
            }
            
            for future in as_completed(future_to_node):
                node = future_to_node[future]
                processed_count += 1
                try:
                    cluster_id = future.result()
                    node['cluster_id'] = cluster_id
                    
                    if processed_count % 10 == 0:
                        print(f"进度: {processed_count}/{len(self.nodes)} - 当前簇数量: {len(self.cluster_registry.clusters)}")
                        
                except Exception as e:
                    print(f"节点 {node['id']} 处理异常: {e}")
    
    def _process_node(self, node: Dict) -> str:
        """
        处理单个节点，返回分配的簇ID
        
        实现伪代码中的核心逻辑
        """
        node_id = node['id']
        
        # 1. 获取embedding
        embedding = self.get_embedding(node)
        
        # 2. 向量索引检索
        search_results = self.vector_index.search(embedding, top_k=1)
        
        if search_results:
            nearest_cluster_id, similarity_score = search_results[0]
            
            # 3. 如果相似度高于阈值，直接分配
            if similarity_score > self.high_threshold:
                self.cluster_registry.add_node(nearest_cluster_id, node_id)
                self.stats['direct_assignments'] += 1
                
                # 更新簇的代表向量（增量平均）
                self.vector_index.update(nearest_cluster_id, embedding)
                
                return nearest_cluster_id
        
        # 4. 不确定 -> 调用VLM判断
        return self._vlm_judgment(node, embedding)
    
    def _vlm_judgment(self, node: Dict, embedding: np.ndarray) -> str:
        """
        使用VLM判断节点应属于哪个簇（或创建新簇）
        """
        self.stats['vlm_judgments'] += 1
        
        node_id = node['id']
        image_file = node.get('image', '')
        
        if not image_file:
            # 没有截图，创建新簇
            return self._create_new_cluster_fallback(node, embedding)
        
        image_path = self.utg_folder / "states" / image_file
        if not image_path.exists():
            return self._create_new_cluster_fallback(node, embedding)
        
        # 优化：不获取所有summary，只获取向量距离最近的Top-K个
        # 即使相似度没达到high_threshold，它们也是最可能的"嫌疑人"
        candidates = self.vector_index.search(embedding, top_k=min(5, len(self.cluster_registry.clusters)))
        
        candidate_summaries = []
        for cid, score in candidates:
            summ = self.cluster_registry.get_cluster(cid)
            if summ:
                candidate_summaries.append({
                    'cluster_id': summ.cluster_id,
                    'cluster_name': summ.cluster_name,
                    'description': summ.functional_description,
                    'similarity': f"{score:.3f}"  # 可以在prompt里告诉VLM相似度供参考
                })
        
        # 调用VLM判断
        decision = self._call_vlm_for_decision(str(image_path), candidate_summaries)
        
        if decision['is_new']:
            # 创建新簇
            cluster_id = self.cluster_registry.create_new(
                cluster_name=decision['cluster_name'],
                description=decision['description'],
                representative_node_id=node_id
            )
            
            # 添加到向量索引
            self.vector_index.add(embedding, cluster_id)
            
            # 添加节点
            self.cluster_registry.add_node(cluster_id, node_id)
            
            self.stats['new_clusters_created'] += 1
            
            return cluster_id
        else:
            # 分配到现有簇
            existing_cluster_id = decision['existing_cluster_id']
            self.cluster_registry.add_node(existing_cluster_id, node_id)
            
            # 更新向量索引
            self.vector_index.update(existing_cluster_id, embedding)
            
            return existing_cluster_id
    
    def _call_vlm_for_decision(self, image_path: str, 
                               active_summaries: List[Dict]) -> Dict[str, Any]:
        """
        调用VLM判断节点归属
        
        Returns:
            {
                'is_new': bool,
                'cluster_name': str (if is_new),
                'description': str (if is_new),
                'existing_cluster_id': str (if not is_new)
            }
        """
        # 构建Prompt
        summaries_text = ""
        if active_summaries:
            summaries_text = "### Candidate Functional Clusters (Top-K most similar):\n"
            for i, summary in enumerate(active_summaries, 1):
                summaries_text += f"{i}. **{summary['cluster_name']}** (ID: {summary['cluster_id']})"
                if 'similarity' in summary:
                    summaries_text += f" [Similarity: {summary['similarity']}]"
                summaries_text += "\n"
                summaries_text += f"   - {summary['description']}\n"
        else:
            summaries_text = "No existing clusters yet."
        
        prompt = f"""
Analyze this Android app screenshot and determine if it belongs to any existing functional cluster.

{summaries_text}

**Task:**
Does this UI screen fit into any of the existing clusters above?

- If YES: Return the cluster ID it belongs to.
- If NO: Propose a NEW cluster name and description for this screen.

**Output Format (JSON):**
```json
{{
    "is_new": true/false,
    "existing_cluster_id": "cluster_id" (if is_new=false),
    "cluster_name": "New Cluster Name" (if is_new=true),
    "description": "Functional description" (if is_new=true),
    "reasoning": "Brief explanation of your decision"
}}
```

Focus on **functional purpose**, not visual similarity.
"""
        
        try:
            result = self.vlm_client.run(
                prompt=prompt,
                image_url=image_path
            )
            response = result.get('content', '')
            
            # 解析JSON响应
            decision = self._parse_json_response(response)
            
            # 验证响应格式
            if 'is_new' not in decision:
                raise ValueError("VLM响应缺少 'is_new' 字段")
            
            return decision
            
        except Exception as e:
            print(f"  VLM判断失败: {e}")
            # Fallback: 创建新簇
            return {
                'is_new': True,
                'cluster_name': f'Auto Cluster (Node {len(self.cluster_registry.clusters)})',
                'description': 'Automatically created due to VLM failure',
                'reasoning': str(e)
            }
    
    def _create_new_cluster_fallback(self, node: Dict, embedding: np.ndarray) -> str:
        """当无法使用VLM时的fallback策略"""
        cluster_name = f"Cluster {len(self.cluster_registry.clusters)}"
        description = f"Auto-created cluster for node {node['id']}"
        
        cluster_id = self.cluster_registry.create_new(
            cluster_name=cluster_name,
            description=description,
            representative_node_id=node['id']
        )
        
        self.vector_index.add(embedding, cluster_id)
        self.cluster_registry.add_node(cluster_id, node['id'])
        
        self.stats['new_clusters_created'] += 1
        
        return cluster_id
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """解析VLM的JSON响应"""
        try:
            clean_str = response.strip()
            
            # 移除Markdown代码块
            if '```json' in clean_str:
                start = clean_str.find('```json') + 7
                end = clean_str.find('```', start)  # 找第一个结束标记
                if end != -1:
                    clean_str = clean_str[start:end].strip()
            elif '```' in clean_str:
                start = clean_str.find('```') + 3
                end = clean_str.find('```', start)  # 找第一个结束标记
                if end != -1:
                    clean_str = clean_str[start:end].strip()
            
            # 尝试找到JSON对象的边界
            # 查找第一个 { 和最后一个匹配的 }
            first_brace = clean_str.find('{')
            if first_brace == -1:
                raise ValueError("响应中没有找到JSON对象")
            
            # 找到匹配的右括号
            brace_count = 0
            last_brace = -1
            for i in range(first_brace, len(clean_str)):
                if clean_str[i] == '{':
                    brace_count += 1
                elif clean_str[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        last_brace = i
                        break
            
            if last_brace == -1:
                raise ValueError("JSON对象不完整，缺少右括号")
            
            json_str = clean_str[first_brace:last_brace+1]
            return json.loads(json_str)
            
        except json.JSONDecodeError as e:
            print(f"  JSON解析失败: {e}")
            print(f"  原始响应: {response[:200]}")
            raise
        except Exception as e:
            print(f"  解析错误: {e}")
            print(f"  原始响应: {response[:200]}")
            raise
    
    # =========================================================================
    # 结果输出
    # =========================================================================
    
    def save_results(self, output_folder: Optional[str] = None):
        """保存聚类结果"""
        if output_folder is None:
            output_folder = self.utg_folder / "semantic_clustered"
        else:
            output_folder = Path(output_folder)
        
        output_folder.mkdir(exist_ok=True)
        
        print(f"\n=== 保存结果到 {output_folder} ===")
        
        # 1. 保存 utg_clustered.js
        self._save_utg_clustered(output_folder)
        
        # 2. 保存 cluster_summaries.json
        self._save_cluster_summaries(output_folder)
        
        # 3. 保存统计信息
        self._save_statistics(output_folder)
        
        print("✓ 结果保存完成")
    
    def _save_utg_clustered(self, output_folder: Path):
        """保存聚类后的UTG文件"""
        output_path = output_folder / "utg_clustered.js"
        
        # 生成颜色映射
        color_mapping = self._generate_color_mapping()
        
        # 为节点添加颜色
        for node in self.nodes:
            cluster_id = node.get('cluster_id', 'unknown')
            if cluster_id in color_mapping:
                node['color'] = color_mapping[cluster_id]
        
        # 生成JavaScript内容
        nodes_json = json.dumps(self.nodes, ensure_ascii=False, indent=2)
        
        js_content = f"""// UTG Pure Semantic Clustering Result
var nodes = {nodes_json};

// Cluster color mapping
var clusterColors = {json.dumps(color_mapping, indent=2)};
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(js_content)
        
        print(f"  ✓ 保存 {output_path}")
    
    def _generate_color_mapping(self) -> Dict[str, str]:
        """生成簇颜色映射"""
        import hashlib
        
        color_mapping = {}
        for cluster_id in self.cluster_registry.clusters.keys():
            hash_val = int(hashlib.md5(cluster_id.encode()).hexdigest()[:6], 16)
            color = f"#{hash_val % 0xFFFFFF:06x}"
            color_mapping[cluster_id] = color
        
        return color_mapping
    
    def _save_cluster_summaries(self, output_folder: Path):
        """保存簇摘要"""
        output_path = output_folder / "cluster_summaries.json"
        
        summaries = self.cluster_registry.to_dict()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(summaries, f, ensure_ascii=False, indent=2)
        
        print(f"  ✓ 保存 {output_path}")
    
    def _save_statistics(self, output_folder: Path):
        """保存统计信息"""
        output_path = output_folder / "clustering_stats.json"
        
        stats = {
            **self.stats,
            'final_cluster_count': len(self.cluster_registry.clusters),
            'avg_cluster_size': self.stats['total_nodes'] / len(self.cluster_registry.clusters) 
                                if len(self.cluster_registry.clusters) > 0 else 0,
            'vlm_usage_rate': self.stats['vlm_judgments'] / self.stats['total_nodes']
                              if self.stats['total_nodes'] > 0 else 0
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        print(f"  ✓ 保存 {output_path}")
    
    def _print_statistics(self):
        """打印统计信息"""
        print("\n" + "=" * 60)
        print("聚类统计信息")
        print("=" * 60)
        print(f"总节点数: {self.stats['total_nodes']}")
        print(f"最终簇数: {len(self.cluster_registry.clusters)}")
        print(f"直接分配: {self.stats['direct_assignments']} "
              f"({self.stats['direct_assignments']/self.stats['total_nodes']*100:.1f}%)")
        print(f"VLM判断: {self.stats['vlm_judgments']} "
              f"({self.stats['vlm_judgments']/self.stats['total_nodes']*100:.1f}%)")
        print(f"新建簇数: {self.stats['new_clusters_created']}")
        print(f"平均簇大小: {self.stats['total_nodes']/len(self.cluster_registry.clusters):.1f}")
        
        print("\n簇大小分布:")
        cluster_sizes = [c.node_count for c in self.cluster_registry.clusters.values()]
        cluster_sizes.sort(reverse=True)
        for i, size in enumerate(cluster_sizes[:10], 1):
            cluster_id = [cid for cid, c in self.cluster_registry.clusters.items() 
                         if c.node_count == size][0]
            cluster_name = self.cluster_registry.clusters[cluster_id].cluster_name
            print(f"  {i}. {cluster_name}: {size} 节点")
        
        print("=" * 60)


# =============================================================================
# 命令行接口
# =============================================================================

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="UTG纯语义聚类工具")
    parser.add_argument("utg_path", help="UTG文件路径 (utg.js)")
    parser.add_argument("--threshold", type=float, default=0.85,
                        help="高相似度阈值，默认: 0.85")
    parser.add_argument("--embedding", choices=['clip', 'vlm', 'text'], 
                        default='vlm', help="Embedding模型选择")
    parser.add_argument("--output", help="输出文件夹路径")
    
    args = parser.parse_args()
    
    # 创建聚类器
    clusterer = PureSemanticClustering(
        utg_path=args.utg_path,
        high_similarity_threshold=args.threshold,
        embedding_model=args.embedding
    )
    
    # 加载数据
    clusterer.load_utg_data()
    
    # 执行聚类
    clusterer.run_clustering()
    
    # 保存结果
    clusterer.save_results(output_folder=args.output)
    
    print("\n处理完成！")


if __name__ == "__main__":
    main()
