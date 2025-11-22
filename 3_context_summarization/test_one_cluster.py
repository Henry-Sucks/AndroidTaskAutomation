# test_one_cluster.py

import json
from cluster_summary.loader import ClusterDataLoader
from cluster_summary.sampler import ClusterSampler
from cluster_summary.summarizer import ImageSummarizer


def test_cluster(
    cluster_id,
    cluster_info_path="C:\\Projects\\AndroidTaskAutomation\\3_context_summarization\\utg\\sata-org.wikipedia-ape-sata-running-minutes-15_utg\\cluster_info.json",
    utg_clustered_path="C:\\Projects\\AndroidTaskAutomation\\3_context_summarization\\utg\\sata-org.wikipedia-ape-sata-running-minutes-15_utg\\utg_clustered.js",
    image_root="C:\\Projects\\AndroidTaskAutomation\\3_context_summarization\\utg\\sata-org.wikipedia-ape-sata-running-minutes-15_utg\\states\\"
):
    print(f"=== Testing Cluster {cluster_id} ===")

    # 1. 加载数据
    loader = ClusterDataLoader(cluster_info_path, utg_clustered_path, image_root)
    if cluster_id not in loader.get_cluster_ids():
        print(f"Error: cluster {cluster_id} not found!")
        return

    cluster = loader.get_cluster(cluster_id)
    print("Cluster loaded.")

    # 2. sampler: 随机几点 node
    sampler = ClusterSampler(loader)
    sample_nodes = sampler.get_sample_nodes(cluster)

    # 4. summarizer
    summarizer = ImageSummarizer()

    # 选择需要测试的节点列表：只测几个点即可
    points_to_test = {
        "entry_points": cluster["entry_points"],
        "exit_points": cluster["exit_points"],
        "center_point": cluster["center_point"],
        "sample_nodes": sample_nodes,
    }

    results = {}

    for point_type, node_ids in points_to_test.items():
        print(f"\n--- Testing {point_type} ---")
        results[point_type] = []

        for nid in node_ids:
            node = loader.get_node(nid)
            if not node:
                print(f"  Node {nid} not found!")
                continue

            img_path = loader.node_to_image_path(node)
            if not img_path:
                print(f"  Image not found for node {nid}")
                continue

            print(f"  Processing node {nid}, image = {img_path}")

            try:
                desc = summarizer.summarize(
                    image_url_or_path=img_path,
                    extra_note=f"Point type: {point_type}",
                    enable_thinking=False
                )
            except Exception as e:
                print(f"  Error when summarizing node {nid}: {e}")
                continue

            results[point_type].append({
                "node_id": nid,
                "image": img_path,
                "description": desc
            })

            print("    ✓ Done")

    print("\n=== Final Results ===")
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    # 修改为你要测试的簇号
    test_cluster("60")
