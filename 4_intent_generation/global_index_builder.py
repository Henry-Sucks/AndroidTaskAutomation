"""
===========================================================
Cluster Intent Summarizer
===========================================================

目标
----
从 local_index.json 中提取每个功能簇的意图信息，
使用大模型生成高层语义描述和支持的用户意图列表。

输出格式：
{
    cluster_id: {
        "summary": "该功能簇的整体语义描述",
        "supported_intents": [
            "高层用户意图1",
            "高层用户意图2",
            ...
        ]
    }
}

===========================================================
"""

import json
import os
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from clients.llm_client import LLMClient


class ClusterIntentSummarizer:
    """
    功能簇意图总结器
    """
    
    def __init__(self, local_index_path: str):
        """
        初始化总结器
        
        Args:
            local_index_path: local_index.json文件路径
        """
        self.local_index_path = local_index_path
        self.llm_client = LLMClient()
        
        # 加载local index数据
        self._load_local_index()
    
    def _load_local_index(self):
        """加载local index数据"""
        with open(self.local_index_path, 'r', encoding='utf-8') as f:
            self.local_index = json.load(f)
    
    def extract_cluster_intents(self, cluster_id: str, cluster_data: List[dict]) -> List[str]:
        """
        提取指定簇中的所有intent
        
        Args:
            cluster_id: 簇ID
            cluster_data: 簇数据，包含多个任务
            
        Returns:
            该簇中所有intent的列表
        """
        intents = []
        for task in cluster_data:
            intent = task.get('intent', '')
            if intent:
                intents.append(intent)
        
        return intents
    
    def summarize_cluster_function(self, cluster_id: str, intents: List[str]) -> Dict[str, Any]:
        """
        使用大模型总结功能簇的高层语义和支持的意图
        
        Args:
            cluster_id: 簇ID
            intents: 该簇中的所有intent列表
            
        Returns:
            包含summary和supported_intents的字典
        """
        # 构建LLM分析prompt
        intents_text = '\n'.join([f"- {intent}" for intent in intents])
        
        prompt = f"""Please analyze this mobile app functional cluster and provide a high-level semantic summary.

Cluster ID: {cluster_id}

Detailed Intents in this Cluster:
{intents_text}

Based on these specific intents, please provide a JSON response with the following structure:
{{
    "summary": "A concise high-level description of what this functional cluster accomplishes from the user's perspective (1-2 sentences in English)",
    "supported_intents": ["List of 3-6 high-level user intents this cluster can fulfill (in English, focus on user goals rather than technical actions)"]
}}

Guidelines:
1. Focus on USER GOALS rather than technical UI actions
2. Group similar low-level actions into higher-level intents  
3. Use natural English language that users would understand
4. Avoid technical jargon like "click", "swipe" - focus on what the user wants to accomplish
5. The summary should capture the overall purpose of this functional area
6. Supported intents should be distinct high-level goals

Provide only valid JSON, no additional text:"""

        try:
            result = self.llm_client.run(
                prompt=prompt,
                temperature=0.3,
                max_tokens=600
            )
            
            # 解析LLM返回的JSON
            content = result.strip()
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            
            cluster_summary = json.loads(content)
            
            return {
                "summary": cluster_summary.get("summary", f"功能簇 {cluster_id}"),
                "supported_intents": cluster_summary.get("supported_intents", [])
            }
            
        except Exception as e:
            print(f"Error summarizing cluster {cluster_id}: {e}")
            # 提供回退总结
            return {
                "summary": f"功能簇 {cluster_id} - 基于 {len(intents)} 个具体操作的功能模块",
                "supported_intents": [
                    f"执行簇 {cluster_id} 中的相关功能",
                    "浏览和交互该功能区域"
                ]
            }
    
    def summarize_all_clusters(self) -> Dict[str, Dict[str, Any]]:
        """
        总结所有功能簇
        
        Returns:
            包含所有簇总结的字典
        """
        cluster_summaries = {}
        
        print(f"Processing {len(self.local_index)} clusters...")
        
        # 预处理：提取所有有效的cluster和它们的intents
        valid_clusters = {}
        for cluster_id, cluster_data in self.local_index.items():
            intents = self.extract_cluster_intents(cluster_id, cluster_data)
            if intents:
                valid_clusters[cluster_id] = intents
                print(f"Found {len(intents)} intents in cluster {cluster_id}")
            else:
                print(f"No intents found in cluster {cluster_id}, skipping...")
        
        print(f"Starting parallel analysis of {len(valid_clusters)} valid clusters...")
        
        # 使用ThreadPoolExecutor并行处理cluster语义分析
        with ThreadPoolExecutor(max_workers=5) as executor:  # 限制并发数量以控制API调用频率
            # 提交所有任务
            future_to_cluster = {
                executor.submit(self.summarize_cluster_function, cluster_id, intents): cluster_id
                for cluster_id, intents in valid_clusters.items()
            }
            
            # 收集结果
            for future in as_completed(future_to_cluster):
                cluster_id = future_to_cluster[future]
                try:
                    summary = future.result()
                    cluster_summaries[cluster_id] = summary
                    print(f"Completed analysis for cluster {cluster_id}")
                    print(f"Summary: {summary['summary']}")
                    print(f"Supported intents: {len(summary['supported_intents'])}")
                    print("-" * 50)
                except Exception as e:
                    print(f"Error analyzing cluster {cluster_id}: {e}")
                    # 使用fallback信息
                    intents = valid_clusters[cluster_id]
                    cluster_summaries[cluster_id] = {
                        "summary": f"功能簇 {cluster_id} - 基于 {len(intents)} 个具体操作的功能模块",
                        "supported_intents": [
                            f"执行簇 {cluster_id} 中的相关功能",
                            "浏览和交互该功能区域"
                        ]
                    }
        
        return cluster_summaries
    
    def save_results(self, results: Dict[str, Dict[str, Any]], output_path: str):
        """
        保存结果到文件
        
        Args:
            results: 总结结果
            output_path: 输出文件路径
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"Results saved to: {output_path}")
    
    def print_formatted_results(self, results: Dict[str, Dict[str, Any]]):
        """
        以指定格式打印结果
        
        Args:
            results: 总结结果
        """
        print("\n" + "="*60)
        print("CLUSTER INTENT SUMMARY RESULTS")
        print("="*60)
        
        for cluster_id, cluster_info in results.items():
            print(f"\n{cluster_id}: {{")
            print(f'    "summary": "{cluster_info["summary"]}",')
            print(f'    "supported_intents": [')
            
            for intent in cluster_info["supported_intents"]:
                print(f'        "{intent}",')
            
            print(f'    ]')
            print("}")


def main():
    """主函数"""
    # 配置路径
    local_index_path = "utg/NetEase Cloud Music/local_index.json"
    output_path = "utg/NetEase Cloud Music/global_index.json"
    
    # 检查文件是否存在
    if not os.path.exists(local_index_path):
        print(f"Error: {local_index_path} not found!")
        return
    
    try:
        # 创建总结器实例
        summarizer = ClusterIntentSummarizer(local_index_path)
        
        # 生成所有簇的总结
        results = summarizer.summarize_all_clusters()
        
        # 保存结果
        summarizer.save_results(results, output_path)
        
        # 打印格式化结果
        summarizer.print_formatted_results(results)
        
        # 打印统计信息
        print(f"\n" + "="*60)
        print("STATISTICS")
        print("="*60)
        print(f"Total clusters processed: {len(results)}")
        total_intents = sum(len(cluster_info['supported_intents']) for cluster_info in results.values())
        print(f"Total supported intents: {total_intents}")
        print(f"Average intents per cluster: {total_intents / len(results):.1f}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()