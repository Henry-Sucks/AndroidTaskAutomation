import json
import difflib
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any

from .loader import ClusterDataLoader
from .sampler import ClusterSampler
from .image_summarizer import ImageSummarizer
from .llm_summarizer import LLMSummarizer

class ClusterSummaryPipeline:
    def __init__(self, package_name, graph_path):
        self.package_name = package_name

        cluster_info_path = graph_path + "\\cluster_info.json"
        utg_clustered_path = graph_path + "\\utg_clustered.js"
        image_root = graph_path + "\\states\\"

        self.loader = ClusterDataLoader(cluster_info_path, utg_clustered_path, image_root)
        self.sampler = ClusterSampler(self.loader)
        self.img_summarizer = ImageSummarizer() # VLM for single nodes
        self.llm_summarizer = LLMSummarizer()   # LLM for cluster synthesis

    def process_single_node(self, point_type, nid):
        """并行执行的单个节点 summarization"""
        node = self.loader.get_node(nid)
        if not node:
            return {"node_id": nid, "error": "Node not found"}

        img_path = self.loader.node_to_image_path(node)
        if not img_path:
            return {"node_id": nid, "error": "Image not found"}

        try:
            desc = self.img_summarizer.summarize(
                package_name=self.package_name,
                image_path=img_path,
                extra_context=f"Point type: {point_type}"
            )
            return {
                "node_id": nid,
                "image": img_path,
                "description": desc
            }
        except Exception as e:
            return {"node_id": nid, "error": str(e)}

    def run_single_cluster_vlm(self, cluster_id, max_workers=8):
        """阶段1：处理单个簇的视觉感知，返回VLM分析结果"""
        print(f"=== [VLM Phase] Processing Cluster {cluster_id} ===")
        
        if cluster_id not in self.loader.get_cluster_ids():
            print(f"Error: cluster {cluster_id} not found!")
            return None

        cluster = self.loader.get_cluster(cluster_id)
        
        # 获取采样节点
        sample_nodes = self.sampler.get_sample_nodes(cluster)

        points_to_test = {
            "entry_points": cluster["entry_points"],
            "exit_points": cluster["exit_points"], 
            "center_point": cluster["center_point"],
            "sample_nodes": sample_nodes,
        }

        results = {}

        # 并行处理各类型节点
        for point_type, node_ids in points_to_test.items():
            results[point_type] = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_id = {
                    executor.submit(self.process_single_node, point_type, nid): nid
                    for nid in node_ids
                }

                for future in as_completed(future_to_id):
                    nid = future_to_id[future]
                    try:
                        res = future.result()
                        results[point_type].append(res)
                    except Exception as e:
                        print(f"  ✗ Node {nid} failed: {e}")

        return results

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度 (0.0 - 1.0)。
        此处使用 SequenceMatcher 作为轻量级方案。
        如果需要更高精度，可替换为 Embedding Cosine Similarity。
        """
        if not text1 or not text2:
            return 0.0
        return difflib.SequenceMatcher(None, text1, text2).ratio()

    def _extract_summary_text(self, llm_output: Any) -> str:
        """从LLM的JSON输出中提取核心摘要文本"""
        if not llm_output:
            return ""
        # 假设 llm_output 是字典，包含 'summary' 或 'Cluster Overall Function'
        # 根据你的 prompt 结构进行调整
        if isinstance(llm_output, str):
            try:
                # 尝试解析 JSON 字符串
                data = json.loads(llm_output)
                return data.get("summary", data.get("Cluster Overall Function", llm_output))
            except:
                return llm_output
        elif isinstance(llm_output, dict):
            return llm_output.get("summary", llm_output.get("Cluster Overall Function", ""))
        return str(llm_output)

    def _run_global_critic_loop(self, all_summaries: Dict[str, Any]):
        """
        [新增] 阶段3：全局批判与修正循环
        1. 提取所有簇的摘要文本。
        2. 计算两两相似度。
        3. 对于高相似度对，调用 LLM 进行辨析和改写。
        """
        print("\n=== [Critic Phase] Starting Global Consistency Check ===")
        
        cluster_ids = list(all_summaries.keys())
        similarity_threshold = 0.6  # 设定相似度阈值，超过则触发检查
        
        # 为了避免重复比较 (A vs B 和 B vs A)，使用已处理集合
        processed_pairs = set()

        for i in range(len(cluster_ids)):
            cid_a = cluster_ids[i]
            data_a = all_summaries[cid_a].get("llm_summary")
            text_a = self._extract_summary_text(data_a)
            
            if not text_a: continue

            for j in range(i + 1, len(cluster_ids)):
                cid_b = cluster_ids[j]
                data_b = all_summaries[cid_b].get("llm_summary")
                text_b = self._extract_summary_text(data_b)
                
                if not text_b: continue
                
                # 计算相似度
                score = self._calculate_similarity(text_a, text_b)
                
                if score > similarity_threshold:
                    print(f"⚠️ High similarity detected ({score:.2f}) between Cluster {cid_a} and {cid_b}")
                    
                    # 触发 LLM 改写
                    new_summary_a = self._rewrite_confusing_summary(cid_a, text_a, cid_b, text_b)
                    
                    if new_summary_a:
                        # 更新摘要
                        print(f"  ✓ Rewrote Cluster {cid_a} to emphasize difference.")
                        # 注意：这里需要根据实际数据结构更新，这里假设 llm_summary 是字典
                        if isinstance(all_summaries[cid_a]["llm_summary"], dict):
                            all_summaries[cid_a]["llm_summary"]["summary"] = new_summary_a
                            all_summaries[cid_a]["llm_summary"]["differentiation_note"] = f"Distinguished from Cluster {cid_b}"
                        # 更新本地变量以便后续比较
                        text_a = new_summary_a

    def _rewrite_confusing_summary(self, id_a, text_a, id_b, text_b):
        """
        调用 LLM 辨析两个相似簇，并重写 A 的摘要。
        """
        prompt = f"""
        You are a Semantic Consistency Critic for an Android UI automation system.
        
        We have detected that the functional summaries of two different UI clusters are too similar, which might confuse the planner.
        
        Cluster A Summary: "{text_a}"
        Cluster B Summary: "{text_b}"
        
        Task:
        1. Analyze if Cluster A and Cluster B represent semantically distinct functions.
        2. If they are distinct, REWRITE the summary for Cluster A to explicitly differentiate it from Cluster B. Focus on unique keywords.
        3. If they are truly identical (impossible to distinguish), return the original summary.
        
        Return ONLY the rewritten summary string for Cluster A.
        """
        
        try:
            # 复用 llm_summarizer 的 client
            # 假设 llm_summarizer.client.run 是同步调用
            response = self.llm_summarizer.client.run(
                prompt=prompt,
                system_prompt="You are a strict editor ensuring unique functional descriptions.",
                temperature=0.2
            )
            return response.strip()
        except Exception as e:
            print(f"  ✗ Critic rewrite failed: {e}")
            return None

    def run(self, cluster_ids=None, output_path="output/cluster_summaries.json", 
            results_output_path="output/vlm_results.json", max_workers=8):
        """
        运行完整的集群摘要流水线
        流程：
        1. VLM Perception (所有簇并行/串行)
        2. Initial LLM Summarization (生成初稿)
        3. Global Critic & Rewrite (解决语义混淆)
        4. Save Results
        """
        
        if cluster_ids is None:
            cluster_ids = self.loader.get_cluster_ids()
        elif isinstance(cluster_ids, (str, int)):
            cluster_ids = [str(cluster_ids)]

        all_vlm_results = {}
        all_summaries = {}

        # --- Phase 1 & 2: VLM Perception & Initial Summarization ---
        print("\n=== Phase 1 & 2: Generation ===")
        for cid in cluster_ids:
            # 1. 获取VLM分析结果
            vlm_results = self.run_single_cluster_vlm(str(cid), max_workers)
            if vlm_results is None:
                continue
                
            all_vlm_results[str(cid)] = vlm_results

            # 2. 使用LLM生成初稿摘要
            try:
                # 假设 summarize_cluster 返回 JSON 对象或字典
                summary = self.llm_summarizer.summarize_cluster(vlm_results)
                all_summaries[str(cid)] = {
                    "vlm_results": vlm_results,
                    "llm_summary": summary
                }
                print(f"  ✓ Cluster {cid} initial summary generated")
            except Exception as e:
                print(f"  ✗ Failed to generate summary for cluster {cid}: {e}")
                all_summaries[str(cid)] = {
                    "vlm_results": vlm_results,
                    "llm_summary": None,
                    "error": str(e)
                }

        # --- Phase 3: Global Critic Loop ---
        # 只有当生成了多个簇的摘要时才需要进行交叉对比
        if len(all_summaries) > 1:
            self._run_global_critic_loop(all_summaries)

        # --- Phase 4: Save Results ---
        print("\n=== Phase 4: Saving Results ===")
        # 保存VLM结果
        with open(results_output_path, "w", encoding='utf-8') as f:
            json.dump(all_vlm_results, f, ensure_ascii=False, indent=2)
        print(f"✓ VLM results saved → {results_output_path}")

        # 保存最终摘要结果
        with open(output_path, "w", encoding='utf-8') as f:
            json.dump(all_summaries, f, ensure_ascii=False, indent=2)
        print(f"✓ Complete summaries saved → {output_path}")

        return all_summaries