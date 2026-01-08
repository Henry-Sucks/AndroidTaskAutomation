import json
import os
import numpy as np
import hashlib
import pickle
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from clients.vlm_client import VLMClient
from clients.llm_client import LLMClient
from openai import OpenAI


@dataclass
class TIGNode:
    """Task Intent Graph Node"""
    id: str
    intent_label: str
    mapped_utg_ids: List[str]
    capabilities: List[str]
    ui_description: str = ""  # UI描述
    embedding: Optional[np.ndarray] = None  # 节点的语义向量


class TIGGrounder:
    """
    TIG Grounder: 将当前UI截图定位到TIG中的对应节点
    """
    
    def __init__(self, tig_path: str, vlm_client: VLMClient = None, llm_client: LLMClient = None):
        """
        初始化TIG Grounder
        
        Args:
            tig_path: TIG JSON文件路径
            vlm_client: 视觉语言模型客户端
            llm_client: LLM客户端（用于生成embedding）
        """
        self.vlm_client = vlm_client or VLMClient()
        self.llm_client = llm_client or LLMClient()
        
        # 初始化用于embedding的LLM客户端（使用阿里云DashScope）
        from clients.config import QWEN_VLM_API_KEY
        self.embedding_client = LLMClient(
            api_key=QWEN_VLM_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model="qwen-vl-max"  # 模型名称（embedding会自动使用text-embedding-v4）
        )
        
        # 设置embedding缓存目录
        cache_dir = os.path.join(os.path.dirname(tig_path), '.embedding_cache')
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        print(f"Embedding cache directory: {self.cache_dir}")
        
        # 加载TIG
        self.tig_nodes = self._load_tig(tig_path)
        
        # 为每个TIG节点生成embedding
        self._initialize_node_embeddings()
        
        # 阈值：如果相似度低于此值，认为进入了 TIG 未知的"荒原"
        self.similarity_threshold = 0.65
    
    def _load_tig(self, tig_path: str) -> List[TIGNode]:
        """加载TIG JSON文件"""
        print(f"Loading TIG from {tig_path}...")
        
        with open(tig_path, 'r', encoding='utf-8') as f:
            tig_data = json.load(f)
        
        nodes = []
        for node_data in tig_data['nodes']:
            # 生成UI描述（如果JSON中没有，则从intent和capabilities生成）
            ui_desc = node_data.get('ui_description', '')
            if not ui_desc:
                ui_desc = f"Screen for {node_data['intent_label'].replace('_', ' ')}. "
                ui_desc += f"Capabilities: {', '.join(node_data['capabilities'][:5])}"
            
            nodes.append(TIGNode(
                id=node_data['id'],
                intent_label=node_data['intent_label'],
                mapped_utg_ids=node_data['mapped_utg_ids'],
                capabilities=node_data['capabilities'],
                ui_description=ui_desc
            ))
        
        print(f"Loaded {len(nodes)} TIG nodes")
        return nodes
    
    def _initialize_node_embeddings(self):
        """为所有TIG节点生成embedding"""
        print("Initializing node embeddings...")
        
        for i, node in enumerate(self.tig_nodes, 1):
            # 构建节点的文本描述
            node_desc = self._create_node_description(node)
            
            # 生成embedding
            node.embedding = self._text_to_embedding(node_desc)
            
            print(f"  [{i}/{len(self.tig_nodes)}] Initialized embedding for {node.id}")
    
    def _create_node_description(self, node: TIGNode) -> str:
        """为TIG节点创建文本描述"""
        desc = f"Intent: {node.intent_label}\n"
        desc += f"Capabilities: {', '.join(node.capabilities[:10])}"  # 取前10个能力
        return desc
    
    def _text_to_embedding(self, text: str) -> np.ndarray:
        """
        将文本转换为embedding向量，使用阿里云DashScope API并支持本地缓存
        
        工作流程：
        1. 生成文本的hash作为缓存key
        2. 检查本地缓存，如果存在直接返回
        3. 如果不存在，调用DashScope embedding API
        4. 将结果保存到本地缓存
        
        Args:
            text: 输入文本
            
        Returns:
            embedding向量 (np.ndarray)
        """
        # 1. 生成缓存key（基于文本的hash）
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        cache_file = self.cache_dir / f"{text_hash}.pkl"
        
        # 2. 检查缓存
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    cached_data = pickle.load(f)
                    return cached_data['embedding']
            except Exception as e:
                print(f"⚠️ Warning: Failed to load cache {cache_file}: {e}")
        
        # 3. 调用DashScope embedding API
        try:
            # 使用LLMClient的get_embedding方法
            vec = self.embedding_client.get_embedding(
                text=text,
                model="text-embedding-v4",  # 阿里云的embedding模型
                dimensions=1024  # 向量维度
            )
            
            if vec is None:
                raise ValueError("Embedding API returned None")
            
            # L2归一化
            vec = vec / (np.linalg.norm(vec) + 1e-8)
            
            # 4. 保存到缓存
            cache_data = {
                'text': text[:200],  # 只保存前200字符用于调试
                'embedding': vec,
                'model': 'text-embedding-v4',
                'dimension': len(vec)
            }
            
            with open(cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            
            return vec
            
        except Exception as e:
            print(f"⚠️ Embedding API error: {e}")
            print(f"   Using hash-based embedding as fallback")
            # Fallback：使用hash方法
            vec = self._hash_based_embedding(text)
            
            # 保存fallback结果到缓存
            cache_data = {
                'text': text[:200],
                'embedding': vec,
                'model': 'hash-based-fallback',
                'dimension': len(vec)
            }
            
            with open(cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            
            return vec
    
    def _hash_based_embedding(self, text: str) -> np.ndarray:
        """
        基于hash的简单embedding（作为API失败时的fallback）
        """
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()
        
        # 转换为384维向量
        vector = np.frombuffer(hash_bytes, dtype=np.uint8)
        vector = np.tile(vector, (384 // len(vector) + 1))[:384]
        
        # 归一化
        vector = vector.astype(np.float32)
        vector = vector / (np.linalg.norm(vector) + 1e-8)
        
        return vector

    def ground(self, screenshot_path: str, xml_path: str = None, verbose: bool = True) -> Optional[TIGNode]:
        """
        核心方法：将当前 App 界面锚定到 TIG 节点
        
        Args:
            screenshot_path: 截图路径
            xml_path: 可选的XML视图层级文件路径
            verbose: 是否打印详细信息
            
        Returns:
            匹配的TIG节点，如果无法匹配则返回None
        """
        # 1. 使用VLM分析截图，生成UI描述
        ui_description = self._analyze_screenshot(screenshot_path)
        
        if verbose:
            print(f"\n🔍 UI Description:\n{ui_description}\n")
        
        # 2. 将UI描述转换为embedding
        ui_embedding = self._text_to_embedding(ui_description)
        
        # 3. 遍历所有 TIG 节点寻找最佳匹配
        best_node = None
        max_score = -1.0
        scores = []
        
        for node in self.tig_nodes:
            score = self._compute_similarity_score(
                ui_description, 
                ui_embedding, 
                node,
                xml_path
            )
            scores.append((node, score))
            
            if score > max_score:
                max_score = score
                best_node = node
        
        # 4. 显示top-3匹配结果
        if verbose:
            scores.sort(key=lambda x: x[1], reverse=True)
            print("📊 Top-3 Matches:")
            for i, (node, score) in enumerate(scores[:3], 1):
                print(f"  {i}. {node.id} ({node.intent_label}) - Score: {score:.3f}")
        
        # 5. 阈值判断
        if max_score >= self.similarity_threshold:
            if verbose:
                print(f"\n✅ Grounded to Node: {best_node.id} (Score: {max_score:.3f})")
            return best_node
        else:
            if verbose:
                print(f"\n⚠️ Grounding Failed. Max Score: {max_score:.3f} < Threshold: {self.similarity_threshold}")
                print("   This may be a new screen not seen in exploration.")
            return None
    
    def _analyze_screenshot(self, screenshot_path: str) -> str:
        """使用VLM分析截图，生成UI功能描述"""
        prompt = """Analyze this Android app screenshot and describe its primary purpose and available actions.

Focus on:
1. What is the main intent/purpose of this screen? (e.g., Search, Playback, Settings, Library Browse)
2. What are the key interactive elements and their functions?
3. What capabilities does this screen offer to the user?

Provide a concise description focusing on functional aspects, not visual design details."""

        try:
            # 确保使用绝对路径
            abs_screenshot_path = os.path.abspath(screenshot_path)
            
            result = self.vlm_client.run(
                prompt=prompt,
                image_url=abs_screenshot_path
            )
            
            # 处理返回值（可能是dict或str）
            if isinstance(result, dict):
                return result.get("content", "Unknown screen")
            return str(result)
        except Exception as e:
            print(f"Error analyzing screenshot: {e}")
            return "Unknown screen"
    
    def _compute_similarity_score(
        self, 
        ui_description: str,
        ui_embedding: np.ndarray, 
        node: TIGNode,
        xml_path: str = None
    ) -> float:
        """
        计算混合相似度分数
        
        Args:
            ui_description: UI文本描述
            ui_embedding: UI描述的embedding向量
            node: TIG节点
            xml_path: 可选的XML文件路径
            
        Returns:
            相似度分数 (0-1)
        """
        # A. 语义向量相似度 (Semantic Similarity)
        sem_sim = cosine_similarity(ui_embedding, node.embedding)
        
        # B. 关键词匹配 (Keyword Match)
        # 从UI描述和节点能力中提取关键词进行匹配
        keyword_score = self._compute_keyword_match(ui_description, node)
        
        # C. 加权融合
        # 语义相似度占主导，关键词匹配作为辅助
        final_score = 0.7 * sem_sim + 0.3 * keyword_score
        
        return final_score
    
    def _compute_keyword_match(self, ui_description: str, node: TIGNode) -> float:
        """
        计算关键词匹配分数
        
        基于UI描述和节点的intent_label及capabilities进行匹配
        """
        ui_desc_lower = ui_description.lower()
        
        # 1. Intent Label匹配
        intent_keywords = node.intent_label.lower().replace('_', ' ').split()
        intent_matches = sum(1 for kw in intent_keywords if kw in ui_desc_lower)
        intent_score = intent_matches / len(intent_keywords) if intent_keywords else 0
        
        # 2. Capabilities匹配
        capability_matches = 0
        for cap in node.capabilities[:20]:  # 只检查前20个能力
            # 提取能力中的关键词
            cap_lower = cap.lower()
            # 移除函数调用格式，提取核心词
            cap_keywords = cap_lower.replace('(', ' ').replace(')', ' ').replace('_', ' ').split()
            if any(kw in ui_desc_lower for kw in cap_keywords if len(kw) > 3):
                capability_matches += 1
        
        capability_score = capability_matches / min(20, len(node.capabilities)) if node.capabilities else 0
        
        # 综合分数
        keyword_score = 0.6 * intent_score + 0.4 * capability_score
        
        return keyword_score


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    计算两个向量的余弦相似度
    
    Args:
        vec1: 向量1
        vec2: 向量2
        
    Returns:
        余弦相似度 (0-1)
    """
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    similarity = dot_product / (norm1 * norm2)
    # 将[-1, 1]映射到[0, 1]
    return (similarity + 1) / 2


def main():
    """测试grounding功能"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Ground screenshot to TIG node')
    parser.add_argument('--tig', type=str, required=True,
                        help='Path to TIG JSON file')
    parser.add_argument('--screenshot', type=str, required=True,
                        help='Path to screenshot image')
    parser.add_argument('--xml', type=str, default=None,
                        help='Optional path to XML view hierarchy file')
    parser.add_argument('--threshold', type=float, default=0.65,
                        help='Similarity threshold (default: 0.65)')
    
    args = parser.parse_args()
    
    # 初始化Grounder
    grounder = TIGGrounder(tig_path=args.tig)
    grounder.similarity_threshold = args.threshold
    
    # 执行grounding
    result = grounder.ground(
        screenshot_path=args.screenshot,
        xml_path=args.xml,
        verbose=True
    )
    
    if result:
        print(f"\n🎯 Result: {result.id}")
        print(f"   Intent: {result.intent_label}")
        print(f"   Mapped UTG IDs: {len(result.mapped_utg_ids)}")
        print(f"   Capabilities: {len(result.capabilities)}")
    else:
        print("\n❌ Failed to ground screenshot to any TIG node")


if __name__ == '__main__':
    main()
