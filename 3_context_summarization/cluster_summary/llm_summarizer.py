import json
from typing import Dict, Any, Optional
from clients.llm_client import LLMClient

# ----------------- PROMPTS -----------------

CLUSTER_SYNTHESIS_PROMPT_TEMPLATE = """
You are an expert Android Navigation Analyst. 
Your task is to synthesize a **Functional Cluster Summary** based on the visual analysis of its key UI nodes.

### Input Data
The cluster contains the following nodes (analyzed by VLM):
{vlm_results_json}

### Goal
Determine the specific purpose of this functional module.
- **Scope**: What specific data or domain does this cover? (e.g., "User's Local Music Library" vs "Online Music Store").
- **Differentiation**: What makes this distinct from other similar pages?

### Output Format (Strict JSON)
Please output a single JSON object with the following structure:
{{
  "cluster_name": "Short, specific name (e.g., 'Settings - Account Security')",
  "summary": "A concise sentence describing the primary function.",
  "primary_capabilities": ["List of 3-5 core actions user can take here"],
  "typical_navigation_flow": "Brief description of how a user moves through this cluster",
  "reasoning": "Why you concluded this based on the node evidence"
}}
"""

class LLMSummarizer:
    """
    负责聚合 VLM 产生的节点信息，生成簇的初始功能摘要。
    """
    
    def __init__(self, model="deepseek-chat"):
        # 假设 LLM Client 已经封装好了 API 调用逻辑
        self.client = LLMClient(model=model)

    def summarize_cluster(self, vlm_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成簇的初稿摘要。
        
        Args:
            vlm_results: 包含 entry/center/exit/sample 节点的 VLM 摘要字典。
                         格式参考 pipeline 中的 results 结构。
        
        Returns:
            Dict: 包含 'summary', 'cluster_name' 等字段的结构化数据。
        """
        
        # 1. 构建 Prompt
        prompt = self._build_synthesis_prompt(vlm_results)
        
        # 2. 调用 LLM
        system_prompt = (
            "You are a strict and precise UI Analysis Assistant. "
            "Do not hallucinate features not present in the provided JSON data."
        )
        
        try:
            response_str = self.client.run(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.2  # 低温度以保证事实性
            )
            
            # 3. 解析并返回结果
            return self._parse_json_response(response_str)
            
        except Exception as e:
            print(f"Error in LLM synthesis: {e}")
            # 返回一个降级的空对象，避免 Pipeline 崩溃
            return {
                "cluster_name": "Unknown Cluster",
                "summary": "Failed to generate summary due to LLM error.",
                "error": str(e)
            }

    def _build_synthesis_prompt(self, vlm_results: Dict[str, Any]) -> str:
        """
        将 VLM 结果字典转换为 Prompt 字符串。
        为了节省 Token，这里可以做一些精简处理。
        """
        # 简单清洗数据，移除 image path 等非语义信息，只保留 description
        clean_data = {}
        for point_type, nodes in vlm_results.items():
            clean_nodes = []
            if isinstance(nodes, list):
                for node in nodes:
                    # 容错处理：确保 node 是字典且包含 description
                    if isinstance(node, dict) and "description" in node:
                        clean_nodes.append(node["description"])
                    elif isinstance(node, dict) and "error" in node:
                        continue # 跳过错误的节点
            
            if clean_nodes:
                clean_data[point_type] = clean_nodes

        # 序列化为 JSON 字符串嵌入 Prompt
        data_json = json.dumps(clean_data, ensure_ascii=False, indent=2)
        
        return CLUSTER_SYNTHESIS_PROMPT_TEMPLATE.format(vlm_results_json=data_json)

    def _parse_json_response(self, response_str: str) -> Dict[str, Any]:
        """
        清洗并解析 LLM 返回的 JSON 字符串。
        处理可能存在的 Markdown 代码块标记。
        """
        try:
            clean_str = response_str.strip()
            # 移除 Markdown 代码块标记 ```json ... ```
            if clean_str.startswith("```"):
                # 找到第一个换行符和最后一个```
                start = clean_str.find("\n") + 1
                end = clean_str.rfind("```")
                clean_str = clean_str[start:end].strip()
            
            return json.loads(clean_str)
        except json.JSONDecodeError:
            print(f"JSON Parse Error. Raw response: {response_str[:100]}...")
            # 尝试返回原始文本作为 fallback
            return {
                "cluster_name": "Unparsed Response",
                "summary": response_str, 
                "raw_response": True
            }