# test_one_cluster.py

import json
from cluster_summary.loader import ClusterDataLoader
from cluster_summary.sampler import ClusterSampler
from cluster_summary.image_summarizer import ImageSummarizer


from clients.llm_client import LLMClient


def build_cluster_prompt_en(results):
    """
    Build the English prompt for cluster summarization.
    The model will reason over entry_points, exit_points,
    center_point, and sample_nodes from VLM summaries.
    """

    prompt_parts = []

    prompt_parts.append(
        "You are an expert in Android UI state analysis. "
        "You will be given VLM-generated summaries of UI nodes inside a cluster "
        "(entry points, exit points, center node, and sampled nodes). "
        "Your task is to infer the overall function and purpose of this cluster.\n\n"
        "Please produce the following structured output:\n"
        "1. **Cluster Overall Function (one concise sentence)**\n"
        "2. **Key Functional Capabilities** (3–8 bullet points)\n"
        "3. **Representative Page Types** (what UI pages appear in this cluster)\n"
        "4. **Likely User Tasks** (what a user is trying to accomplish inside this cluster)\n"
        "5. **Reasoning Evidence** (cite clues extracted from entry/exit/center/sample nodes)\n\n"
        "Below is the JSON containing node summaries:\n"
    )

    prompt_parts.append(json.dumps(results, ensure_ascii=False, indent=2))

    return "\n".join(prompt_parts)


def summarize_cluster(results, llm_client: LLMClient):
    """
    Summarize cluster functionality using the LLMClient defined in llm_client.py.
    """

    prompt = build_cluster_prompt_en(results)

    system_prompt = (
        "You are a highly skilled Android UI/UX workflow analysis assistant. "
        "You understand user flows, UI navigation, and app-level functionality."
    )

    # use the LLM client to run inference
    response = llm_client.run(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=0.2
    )

    return response


def test_cluster(
    cluster_id,
    cluster_info_path="C:\\Projects\\AndroidTaskAutomation\\3_context_summarization\\utg\\sata-org.wikipedia-ape-sata-running-minutes-15_utg\\cluster_info.json",
    utg_clustered_path="C:\\Projects\\AndroidTaskAutomation\\3_context_summarization\\utg\\sata-org.wikipedia-ape-sata-running-minutes-15_utg\\utg_clustered.js",
    image_root="C:\\Projects\\AndroidTaskAutomation\\3_context_summarization\\utg\\sata-org.wikipedia-ape-sata-running-minutes-15_utg\\states\\"
):
    # print(f"=== Testing Cluster {cluster_id} ===")

    # # 1. 加载数据
    # loader = ClusterDataLoader(cluster_info_path, utg_clustered_path, image_root)
    # if cluster_id not in loader.get_cluster_ids():
    #     print(f"Error: cluster {cluster_id} not found!")
    #     return

    # cluster = loader.get_cluster(cluster_id)
    # print("Cluster loaded.")

    # # 2. sampler: 随机几点 node
    # sampler = ClusterSampler(loader)
    # sample_nodes = sampler.get_sample_nodes(cluster)

    # # 4. summarizer
    # summarizer = ImageSummarizer()

    # # 选择需要测试的节点列表：只测几个点即可
    # points_to_test = {
    #     "entry_points": cluster["entry_points"],
    #     "exit_points": cluster["exit_points"],
    #     "center_point": cluster["center_point"],
    #     "sample_nodes": sample_nodes,
    # }

    # results = {}

    # for point_type, node_ids in points_to_test.items():
    #     print(f"\n--- Testing {point_type} ---")
    #     results[point_type] = []

    #     for nid in node_ids:
    #         node = loader.get_node(nid)
    #         if not node:
    #             print(f"  Node {nid} not found!")
    #             continue

    #         img_path = loader.node_to_image_path(node)
    #         if not img_path:
    #             print(f"  Image not found for node {nid}")
    #             continue

    #         print(f"  Processing node {nid}, image = {img_path}")

    #         try:
    #             desc = summarizer.summarize(
    #                 image_url_or_path=img_path,
    #                 extra_note=f"Point type: {point_type}",
    #                 enable_thinking=False
    #             )
    #         except Exception as e:
    #             print(f"  Error when summarizing node {nid}: {e}")
    #             continue

    #         results[point_type].append({
    #             "node_id": nid,
    #             "image": img_path,
    #             "description": desc
    #         })

    #         print("    ✓ Done")

    # print("\n=== Final Results ===")
    # print(json.dumps(results, indent=2, ensure_ascii=False))

    with open('results.json', 'r', encoding='utf-8') as file:
        results = json.load(file)

    client = LLMClient(model="deepseek-chat")
    summary = summarize_cluster(results, client)
    print(summary)


if __name__ == "__main__":
    # 修改为你要测试的簇号
    test_cluster("60")
