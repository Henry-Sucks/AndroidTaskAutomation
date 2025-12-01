import json
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        self.summarizer = ImageSummarizer()

    def process_single_node(self, point_type, nid):
        """并行执行的单个节点 summarization"""
        node = self.loader.get_node(nid)
        if not node:
            return {"node_id": nid, "error": "Node not found"}

        img_path = self.loader.node_to_image_path(node)
        if not img_path:
            return {"node_id": nid, "error": "Image not found"}

        try:
            desc = self.summarizer.summarize(
                package_name=self.package_name,
                image_url_or_path=img_path,
                extra_note=f"Point type: {point_type}",
                enable_thinking=False
            )
            return {
                "node_id": nid,
                "image": img_path,
                "description": desc
            }
        except Exception as e:
            return {"node_id": nid, "error": str(e)}

    def run_single_cluster(self, cluster_id, max_workers=8):
        """处理单个簇，返回VLM分析结果"""
        print(f"=== Processing Cluster {cluster_id} ===")
        
        if cluster_id not in self.loader.get_cluster_ids():
            print(f"Error: cluster {cluster_id} not found!")
            return None

        cluster = self.loader.get_cluster(cluster_id)
        print(f"Cluster {cluster_id} loaded.")

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
            print(f"\n--- Processing {point_type} (parallel) ---")
            results[point_type] = []

            # 并行执行
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
                        print(f"  ✓ Node {nid} done")
                    except Exception as e:
                        print(f"  ✗ Node {nid} failed: {e}")

        return results

    def run(self, cluster_ids=None, output_path="output/cluster_summaries.json", 
            results_output_path="output/vlm_results.json", max_workers=8):
        """运行完整的集群摘要流水线"""
        
        # 如果没有指定cluster_ids，处理所有簇
        if cluster_ids is None:
            cluster_ids = self.loader.get_cluster_ids()
        elif isinstance(cluster_ids, (str, int)):
            cluster_ids = [str(cluster_ids)]

        all_vlm_results = {}
        all_summaries = {}

        for cid in cluster_ids:
            if cid == "95":
                # 1. 获取VLM分析结果
                vlm_results = self.run_single_cluster(str(cid), max_workers)
                if vlm_results is None:
                    continue
                    
                all_vlm_results[str(cid)] = vlm_results

                # 2. 使用LLM生成摘要
                llm_summarizer = LLMSummarizer()
                try:
                    summary = llm_summarizer.summarize_cluster(vlm_results)
                    all_summaries[str(cid)] = {
                        "vlm_results": vlm_results,
                        "llm_summary": summary
                    }
                    print(f"\n✓ Cluster {cid} summary generated")
                except Exception as e:
                    print(f"\n✗ Failed to generate summary for cluster {cid}: {e}")
                    all_summaries[str(cid)] = {
                        "vlm_results": vlm_results,
                        "llm_summary": None,
                        "error": str(e)
                    }

        # 保存VLM结果
        with open(results_output_path, "w", encoding='utf-8') as f:
            json.dump(all_vlm_results, f, ensure_ascii=False, indent=2)
        print(f"✓ VLM results saved → {results_output_path}")

        # 保存完整摘要结果
        with open(output_path, "w", encoding='utf-8') as f:
            json.dump(all_summaries, f, ensure_ascii=False, indent=2)
        print(f"✓ Complete summaries saved → {output_path}")

        return all_summaries

        





