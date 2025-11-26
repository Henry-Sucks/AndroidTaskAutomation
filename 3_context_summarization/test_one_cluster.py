# test_one_cluster.py

import json
from cluster_summary.loader import ClusterDataLoader
from cluster_summary.sampler import ClusterSampler
from cluster_summary.image_summarizer import ImageSummarizer


from clients.llm_client import LLMClient


from concurrent.futures import ThreadPoolExecutor, as_completed


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
    graph_path = "C:\\Projects\\AndroidTaskAutomation\\3_context_summarization\\utg\\NetEase Cloud Music",
):
    print(f"=== Testing Cluster {cluster_id} ===")

    cluster_info_path = graph_path + "\\cluster_info.json"
    utg_clustered_path = graph_path + "\\utg_clustered.js"
    image_root = graph_path + "\\states\\"

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

    summarizer = ImageSummarizer()

    points_to_test = {
        "entry_points": cluster["entry_points"],
        "exit_points": cluster["exit_points"],
        "center_point": cluster["center_point"],
        "sample_nodes": sample_nodes,
    }

    results = {}

    def process_single_node(point_type, nid):
        """并行执行的单个节点 summarization"""
        node = loader.get_node(nid)
        if not node:
            return {"node_id": nid, "error": "Node not found"}

        img_path = loader.node_to_image_path(node)
        if not img_path:
            return {"node_id": nid, "error": "Image not found"}

        try:
            desc = summarizer.summarize(
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

    # ------------------------------
    #       ⭐ 并行执行主循环 ⭐
    # ------------------------------
    for point_type, node_ids in points_to_test.items():
        print(f"\n--- Testing {point_type} (parallel) ---")
        results[point_type] = []

        # 并行执行
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_id = {
                executor.submit(process_single_node, point_type, nid): nid
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

    print("\n=== Final Results ===")
    print(json.dumps(results, indent=2, ensure_ascii=False))

    with open('results.json', 'w', encoding='utf-8') as file:
        json.dump(results, file, ensure_ascii=False, indent=2)

    client = LLMClient(model="deepseek-chat")
    summary = summarize_cluster(results, client)
    print(summary)

    # 将summary保存到新的JSON文件中
    try:
        # 读取原始cluster_info.json
        with open(cluster_info_path, 'r', encoding='utf-8') as f:
            cluster_info = json.load(f)
        
        # 确保cluster_id存在于cluster_info中
        if str(cluster_id) in cluster_info.get('clusters', {}):
            # 创建副本并添加summary
            cluster_info_with_summary = json.loads(json.dumps(cluster_info))  # 深拷贝
            cluster_info_with_summary['clusters'][str(cluster_id)]['summary'] = summary
            
            # 生成新文件名：cluster_info_with_summary.json
            summary_file_path = cluster_info_path.replace('cluster_info.json', 'cluster_info_with_summary.json')
            
            # 写入新文件，保持缩进格式
            with open(summary_file_path, 'w', encoding='utf-8') as f:
                json.dump(cluster_info_with_summary, f, ensure_ascii=False, indent=2)
            
            print(f"\n✓ Summary已成功保存到新文件: {summary_file_path}")
            print(f"✓ Cluster {cluster_id} 的summary已添加到新JSON文件中")
        else:
            print(f"\n✗ 警告: cluster {cluster_id} 不存在于cluster_info.json中")
            
    except Exception as e:
        print(f"\n✗ 保存summary到新JSON文件时出错: {e}")


if __name__ == "__main__":
    # 修改为你要测试的簇号
    test_cluster("95")
