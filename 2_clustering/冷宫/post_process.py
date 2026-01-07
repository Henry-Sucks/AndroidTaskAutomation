"""
UTG 聚类后处理模块 - 基于语义相似度的簇合并

主要功能：
1. 对每个簇进行语义总结（基于VLM/LLM）
2. 计算簇之间的语义相似度
3. 合并语义相似的簇
4. 递归执行直到簇之间差异显著或人工停止
"""

import json
import difflib
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional
from collections import defaultdict

# 导入VLM和LLM客户端
import sys
sys.path.append(str(Path(__file__).parent.parent / "3_context_summarization"))
from clients.vlm_client import VLMClient
from clients.llm_client import LLMClient


class ClusterSemanticMerger:
    """
    基于语义相似度的簇合并器
    
    工作流程：
    1. 加载聚类结果（utg_clustered.js 和 cluster_info.json）
    2. 为每个簇生成语义摘要
    3. 计算簇间语义相似度
    4. 合并高相似度簇
    5. 递归执行直到收敛或手动停止
    """
    
    def __init__(self, 
                 utg_folder: str,
                 similarity_threshold: float = 0.75,
                 min_cluster_size: int = 3,
                 max_iterations: int = 10,
                 use_vlm: bool = True):
        """
        初始化语义合并器
        
        Args:
            utg_folder: UTG 文件夹路径（包含 utg_clustered.js 等文件）
            similarity_threshold: 语义相似度阈值（0-1），超过此值则合并
            min_cluster_size: 最小簇大小，避免过度合并
            max_iterations: 最大递归迭代次数
            use_vlm: 是否使用VLM进行视觉分析（False则仅用LLM基于文本）
        """
        self.utg_folder = Path(utg_folder)
        self.similarity_threshold = similarity_threshold
        self.min_cluster_size = min_cluster_size
        self.max_iterations = max_iterations
        self.use_vlm = use_vlm
        
        # 文件路径
        self.utg_clustered_path = self.utg_folder / "utg_clustered.js"
        self.cluster_info_path = self.utg_folder / "cluster_info.json"
        self.states_folder = self.utg_folder / "states"
        self.layout_folder = self.utg_folder / "layout"
        
        # 数据结构
        self.nodes: List[Dict] = []  # 所有节点
        self.node_map: Dict[str, Dict] = {}  # node_id -> node_data
        self.cluster_info: Dict = {}  # cluster_info.json 内容
        self.clusters: Dict[str, List[str]] = {}  # cluster_id -> [node_ids]
        
        # 簇摘要缓存
        self.cluster_summaries: Dict[str, Dict[str, Any]] = {}  # cluster_id -> summary_data
        
        # 客户端
        self.vlm_client = VLMClient() if use_vlm else None
        self.llm_client = LLMClient(model="deepseek-chat")
        
        # 合并历史记录
        self.merge_history: List[Dict] = []  # 记录每次合并操作
        
        print(f"初始化簇语义合并器: {self.utg_folder}")
        print(f"  相似度阈值: {self.similarity_threshold}")
        print(f"  最大迭代次数: {self.max_iterations}")
        print(f"  使用VLM: {self.use_vlm}")
    
    def load_data(self):
        """加载聚类数据"""
        print("\n=== 加载聚类数据 ===")
        
        # 1. 加载 utg_clustered.js
        self._load_utg_clustered()
        
        # 2. 加载 cluster_info.json
        self._load_cluster_info()
        
        # 3. 构建簇-节点映射
        self._build_cluster_mapping()
        
        print(f"✓ 加载完成: {len(self.nodes)} 个节点, {len(self.clusters)} 个簇")
    
    def _load_utg_clustered(self):
        """从 utg_clustered.js 加载节点数据"""
        with open(self.utg_clustered_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取 nodes 数组
        nodes_match = re.search(r'var\s+nodes\s*=\s*(\[.*?\]);', content, re.DOTALL)
        if not nodes_match:
            raise ValueError("无法从 utg_clustered.js 中提取 nodes 数据")
        
        nodes_str = nodes_match.group(1)
        
        # JavaScript 转 Python
        nodes_str = self._js_to_python(nodes_str)
        
        try:
            self.nodes = eval(nodes_str)
            self.node_map = {n['id']: n for n in self.nodes}
        except Exception as e:
            print(f"解析 nodes 失败: {e}")
            raise
    
    def _load_cluster_info(self):
        """加载 cluster_info.json"""
        if not self.cluster_info_path.exists():
            print(f"警告: cluster_info.json 不存在，将从节点的 cluster_id 属性推断")
            return
        
        with open(self.cluster_info_path, 'r', encoding='utf-8') as f:
            self.cluster_info = json.load(f)
    
    def _build_cluster_mapping(self):
        """构建簇ID到节点列表的映射"""
        for node in self.nodes:
            cluster_id = node.get('cluster_id', 'unknown')
            if cluster_id not in self.clusters:
                self.clusters[cluster_id] = []
            self.clusters[cluster_id].append(node['id'])
    
    def _js_to_python(self, js_str: str) -> str:
        """将JavaScript对象转换为Python字典"""
        js_str = re.sub(r'\}\s*\{', '}, {', js_str)
        js_str = js_str.replace('null', 'None')
        js_str = re.sub(r'(\w+):', r"'\1':", js_str)
        return js_str
    
    # =========================================================================
    # 语义摘要生成
    # =========================================================================
    
    def generate_cluster_summaries(self, sample_size: int = 5):
        """
        为所有簇生成语义摘要
        
        Args:
            sample_size: 每个簇采样的节点数量（用于VLM分析）
        """
        print("\n=== 生成簇语义摘要 ===")
        
        for cluster_id, node_ids in self.clusters.items():
            if cluster_id == 'unknown':
                continue
            
            print(f"\n处理簇 {cluster_id} ({len(node_ids)} 个节点)...")
            
            # 1. 采样节点
            sampled_nodes = self._sample_cluster_nodes(node_ids, sample_size)
            
            # 2. 使用VLM分析节点（如果启用）
            vlm_results = []
            if self.use_vlm:
                vlm_results = self._analyze_nodes_with_vlm(sampled_nodes)
            
            # 3. 使用LLM生成簇摘要
            summary = self._generate_cluster_summary_with_llm(
                cluster_id, node_ids, sampled_nodes, vlm_results
            )
            
            self.cluster_summaries[cluster_id] = {
                'cluster_id': cluster_id,
                'node_count': len(node_ids),
                'sampled_nodes': sampled_nodes,
                'vlm_results': vlm_results,
                'summary': summary
            }
            
            print(f"✓ 簇 {cluster_id} 摘要: {summary.get('cluster_name', 'N/A')}")
    
    def _sample_cluster_nodes(self, node_ids: List[str], sample_size: int) -> List[str]:
        """从簇中采样代表性节点"""
        import random
        
        # 如果节点数少于采样数，返回所有节点
        if len(node_ids) <= sample_size:
            return node_ids
        
        # 优先选择有图片的节点
        nodes_with_image = [nid for nid in node_ids if self.node_map[nid].get('image')]
        
        if len(nodes_with_image) >= sample_size:
            return random.sample(nodes_with_image, sample_size)
        else:
            # 补充没有图片的节点
            remaining = sample_size - len(nodes_with_image)
            nodes_without_image = [nid for nid in node_ids if not self.node_map[nid].get('image')]
            return nodes_with_image + random.sample(nodes_without_image, min(remaining, len(nodes_without_image)))
    
    def _analyze_nodes_with_vlm(self, node_ids: List[str]) -> List[Dict]:
        """使用VLM分析节点截图"""
        results = []
        
        for node_id in node_ids:
            node = self.node_map.get(node_id)
            if not node:
                continue
            
            image_file = node.get('image', '')
            if not image_file:
                continue
            
            image_path = self.states_folder / image_file
            if not image_path.exists():
                continue
            
            try:
                # 使用VLM分析截图
                description = self.vlm_client.analyze_image(
                    str(image_path),
                    prompt=self._get_vlm_prompt()
                )
                
                results.append({
                    'node_id': node_id,
                    'image': str(image_path),
                    'description': description
                })
            except Exception as e:
                print(f"  VLM分析失败 ({node_id}): {e}")
        
        return results
    
    def _get_vlm_prompt(self) -> str:
        """获取VLM分析提示词"""
        return """
Analyze this Android app screenshot and describe its functionality.

Focus on:
1. **Page Title/Header**: What is the main title or label?
2. **Primary Function**: What is the main purpose of this screen?
3. **Functional Scope**: What specific data or domain does this screen operate on?
4. **Unique Features**: What visual elements or capabilities distinguish this from generic pages?
5. **User Actions**: What key actions can users perform here?

Output as JSON:
{
    "page_title": "...",
    "primary_function": "...",
    "functional_scope": "...",
    "unique_features": "...",
    "visible_actions": ["...", "..."]
}
"""
    
    def _generate_cluster_summary_with_llm(self,
                                           cluster_id: str,
                                           node_ids: List[str],
                                           sampled_nodes: List[str],
                                           vlm_results: List[Dict]) -> Dict[str, Any]:
        """使用LLM生成簇摘要"""
        
        # 构建Prompt
        prompt = self._build_cluster_summary_prompt(cluster_id, node_ids, sampled_nodes, vlm_results)
        
        try:
            response_str = self.llm_client.run(
                prompt=prompt,
                system_prompt="You are an expert Android UI analyst. Provide precise, factual analysis.",
                temperature=0.2
            )
            
            # 解析JSON响应
            return self._parse_json_response(response_str)
        except Exception as e:
            print(f"  LLM生成摘要失败: {e}")
            return {
                'cluster_name': f'Cluster {cluster_id}',
                'summary': 'Failed to generate summary',
                'error': str(e)
            }
    
    def _build_cluster_summary_prompt(self,
                                      cluster_id: str,
                                      node_ids: List[str],
                                      sampled_nodes: List[str],
                                      vlm_results: List[Dict]) -> str:
        """构建LLM摘要生成Prompt"""
        
        # 提取VLM分析结果
        vlm_text = ""
        if vlm_results:
            vlm_text = "\n### VLM Analysis Results:\n"
            for result in vlm_results:
                vlm_text += f"- Node {result['node_id']}: {result['description']}\n"
        
        # 提取节点的Activity信息
        activities = set()
        for nid in sampled_nodes:
            node = self.node_map.get(nid)
            if node and node.get('activity'):
                activities.add(node['activity'])
        
        activities_text = ""
        if activities:
            activities_text = "\n### Android Activities:\n" + "\n".join(f"- {a}" for a in activities)
        
        prompt = f"""
You are an Android Navigation Expert analyzing a UI cluster.

**Cluster Information:**
- Cluster ID: {cluster_id}
- Total nodes: {len(node_ids)}
- Sampled nodes: {len(sampled_nodes)}

{vlm_text}

{activities_text}

**Task:**
Synthesize a concise functional summary for this cluster.

**Focus on:**
1. **Unique Purpose**: What specific function does this cluster serve?
2. **Scope**: What data or domain does it operate on?
3. **Differentiation**: What makes it distinct from generic pages?

**Output Format (JSON):**
{{
    "cluster_name": "Short, specific name (e.g., 'Settings - Account Security')",
    "summary": "One sentence describing the primary function",
    "primary_capabilities": ["List of 3-5 core actions users can perform"],
    "functional_scope": "Specific domain/data this cluster operates on",
    "key_distinguishing_features": "What makes this cluster unique"
}}
"""
        return prompt
    
    def _parse_json_response(self, response_str: str) -> Dict[str, Any]:
        """解析LLM的JSON响应"""
        try:
            clean_str = response_str.strip()
            
            # 移除Markdown代码块标记
            if clean_str.startswith("```"):
                start = clean_str.find("\n") + 1
                end = clean_str.rfind("```")
                clean_str = clean_str[start:end].strip()
            
            return json.loads(clean_str)
        except json.JSONDecodeError as e:
            print(f"  JSON解析失败: {e}")
            return {
                'cluster_name': 'Unparsed',
                'summary': response_str[:200],
                'parse_error': True
            }
    
    # =========================================================================
    # 语义相似度计算与簇合并
    # =========================================================================
    
    def calculate_similarity_matrix(self) -> Dict[Tuple[str, str], float]:
        """
        计算所有簇对之间的语义相似度
        
        Returns:
            Dict: (cluster_id_1, cluster_id_2) -> similarity_score
        """
        print("\n=== 计算簇间语义相似度 ===")
        
        cluster_ids = [cid for cid in self.clusters.keys() if cid != 'unknown']
        similarity_matrix = {}
        
        for i in range(len(cluster_ids)):
            for j in range(i + 1, len(cluster_ids)):
                cid_a, cid_b = cluster_ids[i], cluster_ids[j]
                
                summary_a = self.cluster_summaries.get(cid_a, {}).get('summary', {})
                summary_b = self.cluster_summaries.get(cid_b, {}).get('summary', {})
                
                # 计算相似度
                similarity = self._calculate_cluster_similarity(summary_a, summary_b)
                similarity_matrix[(cid_a, cid_b)] = similarity
                
                if similarity > self.similarity_threshold:
                    print(f"  高相似度: {cid_a} <-> {cid_b} = {similarity:.3f}")
        
        return similarity_matrix
    
    def _calculate_cluster_similarity(self, summary_a: Dict, summary_b: Dict) -> float:
        """
        计算两个簇摘要的相似度
        
        策略：
        1. 提取关键文本（cluster_name + summary + functional_scope）
        2. 使用 SequenceMatcher 计算文本相似度
        3. （可选）使用LLM进行语义相似度判断
        """
        # 提取文本
        text_a = self._extract_summary_text(summary_a)
        text_b = self._extract_summary_text(summary_b)
        
        if not text_a or not text_b:
            return 0.0
        
        # 方法1: SequenceMatcher (快速但不够精确)
        seq_similarity = difflib.SequenceMatcher(None, text_a, text_b).ratio()
        
        # 方法2: LLM语义判断 (更准确但耗时)
        # 这里可以选择性启用
        use_llm_similarity = True
        if use_llm_similarity and seq_similarity > 0.5:  # 仅对潜在相似的簇使用LLM
            llm_similarity = self._llm_semantic_similarity(text_a, text_b)
            # 综合两种方法
            final_similarity = (seq_similarity + llm_similarity) / 2
            return final_similarity
        
        return seq_similarity
    
    def _extract_summary_text(self, summary: Dict) -> str:
        """从摘要字典中提取关键文本"""
        if not summary:
            return ""
        
        parts = []
        
        # 提取各个字段
        if 'cluster_name' in summary:
            parts.append(summary['cluster_name'])
        if 'summary' in summary:
            parts.append(summary['summary'])
        if 'functional_scope' in summary:
            parts.append(summary['functional_scope'])
        if 'primary_capabilities' in summary and isinstance(summary['primary_capabilities'], list):
            parts.extend(summary['primary_capabilities'])
        
        return " ".join(parts)
    
    def _llm_semantic_similarity(self, text_a: str, text_b: str) -> float:
        """使用LLM判断语义相似度"""
        prompt = f"""
Compare the following two UI cluster descriptions and determine if they represent semantically similar or distinct functionalities.

Cluster A: "{text_a}"
Cluster B: "{text_b}"

**Task:**
Rate the semantic similarity from 0.0 (completely different) to 1.0 (essentially the same).

Consider:
- Are they describing the same feature/module?
- Do they operate on the same data domain?
- Could they be merged without losing meaningful distinction?

Output ONLY a JSON object:
{{
    "similarity_score": <float between 0.0 and 1.0>,
    "reasoning": "Brief explanation"
}}
"""
        
        try:
            response = self.llm_client.run(
                prompt=prompt,
                system_prompt="You are a semantic similarity expert. Be precise and objective.",
                temperature=0.1
            )
            
            result = self._parse_json_response(response)
            return float(result.get('similarity_score', 0.0))
        except Exception as e:
            print(f"  LLM相似度判断失败: {e}")
            return 0.0
    
    def merge_similar_clusters(self, similarity_matrix: Dict[Tuple[str, str], float]) -> Dict[str, str]:
        """
        基于相似度矩阵合并簇
        
        Returns:
            Dict: old_cluster_id -> new_cluster_id 的映射
        """
        print("\n=== 合并相似簇 ===")
        
        # 找出所有需要合并的簇对
        merge_pairs = [
            (cid_a, cid_b, score)
            for (cid_a, cid_b), score in similarity_matrix.items()
            if score > self.similarity_threshold
        ]
        
        # 按相似度降序排序
        merge_pairs.sort(key=lambda x: x[2], reverse=True)
        
        # 使用Union-Find进行簇合并
        parent = {}  # cluster_id -> parent_cluster_id
        
        def find(x):
            if x not in parent:
                parent[x] = x
            if parent[x] != x:
                parent[x] = find(parent[x])  # 路径压缩
            return parent[x]
        
        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[py] = px  # 合并
                return True
            return False
        
        merge_count = 0
        merged_groups = []
        
        for cid_a, cid_b, score in merge_pairs:
            # 检查合并后簇大小是否合理
            size_a = len(self.clusters.get(find(cid_a), []))
            size_b = len(self.clusters.get(find(cid_b), []))
            
            # 避免创建过大的簇
            if size_a + size_b > 100:  # 可配置的阈值
                print(f"  跳过合并 {cid_a} <-> {cid_b} (合并后过大: {size_a + size_b})")
                continue
            
            if union(cid_a, cid_b):
                merge_count += 1
                merged_groups.append((cid_a, cid_b, score))
                print(f"  ✓ 合并 {cid_a} <- {cid_b} (相似度: {score:.3f})")
        
        # 构建映射表
        cluster_mapping = {}
        for cid in self.clusters.keys():
            if cid != 'unknown':
                cluster_mapping[cid] = find(cid)
        
        # 记录合并历史
        self.merge_history.append({
            'merge_count': merge_count,
            'merged_groups': merged_groups,
            'cluster_mapping': cluster_mapping
        })
        
        print(f"✓ 完成: 合并了 {merge_count} 对簇")
        
        return cluster_mapping
    
    def apply_cluster_mapping(self, cluster_mapping: Dict[str, str]):
        """应用簇合并映射，更新数据结构"""
        print("\n=== 应用簇合并映射 ===")
        
        # 1. 更新节点的 cluster_id
        for node in self.nodes:
            old_cid = node.get('cluster_id')
            if old_cid in cluster_mapping:
                node['cluster_id'] = cluster_mapping[old_cid]
        
        # 2. 重建 clusters 映射
        new_clusters = defaultdict(list)
        for node_id, node in self.node_map.items():
            cid = node.get('cluster_id', 'unknown')
            new_clusters[cid].append(node_id)
        
        self.clusters = dict(new_clusters)
        
        # 3. 合并簇摘要
        new_summaries = {}
        for old_cid, new_cid in cluster_mapping.items():
            if new_cid not in new_summaries:
                # 使用第一个遇到的摘要作为基础
                if old_cid in self.cluster_summaries:
                    new_summaries[new_cid] = self.cluster_summaries[old_cid]
            else:
                # 如果已存在，可以选择合并或保留原有
                pass
        
        self.cluster_summaries = new_summaries
        
        print(f"✓ 更新完成: 当前有 {len(self.clusters)} 个簇")
    
    def run_iterative_merging(self, interactive: bool = False) -> int:
        """
        递归执行簇合并，直到收敛或达到最大迭代次数
        
        Args:
            interactive: 是否在每次迭代后询问用户是否继续
        
        Returns:
            int: 执行的迭代次数
        """
        print("\n" + "=" * 60)
        print("开始迭代簇合并流程")
        print("=" * 60)
        
        iteration = 0
        
        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n{'=' * 60}")
            print(f"迭代 {iteration}/{self.max_iterations}")
            print(f"{'=' * 60}")
            
            # 1. 生成/更新簇摘要
            self.generate_cluster_summaries()
            
            # 2. 计算相似度矩阵
            similarity_matrix = self.calculate_similarity_matrix()
            
            # 3. 检查是否有需要合并的簇
            high_similarity_pairs = [
                (cid_a, cid_b, score)
                for (cid_a, cid_b), score in similarity_matrix.items()
                if score > self.similarity_threshold
            ]
            
            if not high_similarity_pairs:
                print(f"\n✓ 收敛: 没有发现相似度超过阈值 ({self.similarity_threshold}) 的簇对")
                break
            
            print(f"\n发现 {len(high_similarity_pairs)} 对高相似度簇")
            
            # 4. 执行合并
            cluster_mapping = self.merge_similar_clusters(similarity_matrix)
            
            # 5. 应用合并
            self.apply_cluster_mapping(cluster_mapping)
            
            # 6. 交互式确认
            if interactive:
                user_input = input("\n继续下一轮合并? (y/n): ").strip().lower()
                if user_input != 'y':
                    print("用户终止迭代")
                    break
        
        print(f"\n{'=' * 60}")
        print(f"迭代完成: 执行了 {iteration} 轮合并")
        print(f"最终簇数: {len(self.clusters)}")
        print(f"{'=' * 60}")
        
        return iteration
    
    # =========================================================================
    # 结果保存
    # =========================================================================
    
    def save_results(self, output_folder: Optional[str] = None):
        """保存合并后的结果"""
        if output_folder is None:
            output_folder = self.utg_folder / "semantic_merged"
        else:
            output_folder = Path(output_folder)
        
        output_folder.mkdir(exist_ok=True)
        
        print(f"\n=== 保存结果到 {output_folder} ===")
        
        # 1. 保存更新后的 utg_clustered.js
        self._save_utg_clustered(output_folder)
        
        # 2. 保存簇摘要
        self._save_cluster_summaries(output_folder)
        
        # 3. 保存合并历史
        self._save_merge_history(output_folder)
        
        print("✓ 结果保存完成")
    
    def _save_utg_clustered(self, output_folder: Path):
        """保存更新后的 utg_clustered.js"""
        output_path = output_folder / "utg_clustered.js"
        
        # 生成JavaScript内容
        nodes_json = json.dumps(self.nodes, ensure_ascii=False, indent=2)
        
        js_content = f"""// UTG Clustered Graph (Semantic Merged)
var nodes = {nodes_json};

// Cluster color mapping
var clusterColors = {{}};
{self._generate_color_mapping()}

// Apply colors to nodes
nodes.forEach(function(node) {{
    if (node.cluster_id && clusterColors[node.cluster_id]) {{
        node.color = clusterColors[node.cluster_id];
    }}
}});
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(js_content)
        
        print(f"  ✓ 保存 {output_path}")
    
    def _generate_color_mapping(self) -> str:
        """生成簇颜色映射JavaScript代码"""
        import hashlib
        
        lines = []
        for cid in self.clusters.keys():
            if cid == 'unknown':
                continue
            
            # 使用hash生成颜色
            hash_val = int(hashlib.md5(cid.encode()).hexdigest()[:6], 16)
            color = f"#{hash_val % 0xFFFFFF:06x}"
            lines.append(f'clusterColors["{cid}"] = "{color}";')
        
        return "\n".join(lines)
    
    def _save_cluster_summaries(self, output_folder: Path):
        """保存簇摘要"""
        output_path = output_folder / "cluster_summaries.json"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.cluster_summaries, f, ensure_ascii=False, indent=2)
        
        print(f"  ✓ 保存 {output_path}")
    
    def _save_merge_history(self, output_folder: Path):
        """保存合并历史"""
        output_path = output_folder / "merge_history.json"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.merge_history, f, ensure_ascii=False, indent=2)
        
        print(f"  ✓ 保存 {output_path}")


# =============================================================================
# 命令行接口
# =============================================================================

def main():
    """主函数 - 命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="UTG 簇语义合并工具")
    parser.add_argument("utg_folder", help="UTG 文件夹路径")
    parser.add_argument("--threshold", type=float, default=0.75,
                        help="相似度阈值 (0-1), 默认: 0.75")
    parser.add_argument("--max-iterations", type=int, default=10,
                        help="最大迭代次数, 默认: 10")
    parser.add_argument("--no-vlm", action="store_true",
                        help="禁用VLM视觉分析")
    parser.add_argument("--interactive", action="store_true",
                        help="交互模式，每次迭代后询问是否继续")
    parser.add_argument("--output", help="输出文件夹路径")
    
    args = parser.parse_args()
    
    # 创建合并器
    merger = ClusterSemanticMerger(
        utg_folder=args.utg_folder,
        similarity_threshold=args.threshold,
        max_iterations=args.max_iterations,
        use_vlm=not args.no_vlm
    )
    
    # 加载数据
    merger.load_data()
    
    # 执行迭代合并
    iterations = merger.run_iterative_merging(interactive=args.interactive)
    
    # 保存结果
    merger.save_results(output_folder=args.output)
    
    print("\n" + "=" * 60)
    print("处理完成！")
    print(f"  总迭代次数: {iterations}")
    print(f"  最终簇数: {len(merger.clusters)}")
    print(f"  输出路径: {args.output or merger.utg_folder / 'semantic_merged'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
