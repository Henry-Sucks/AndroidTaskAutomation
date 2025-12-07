# intent_generator.py
import json
import os
import re
from utils import load_json, save_json
from clients.vlm_client import VLMClient
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed, ProcessPoolExecutor
from tqdm import tqdm
from multiprocessing import Manager, Lock


def load_utg_nodes(utg_cluster_js_path):
    """
    Parse utg_cluster.js and extract node list.
    Format:
    var nodes = [ {...}, {...} ]
    """
    text = open(utg_cluster_js_path, "r", encoding="utf-8").read()
    m = re.search(r"var\s+nodes\s*=\s*(\[[\s\S]*?\]);", text)
    if not m:
        raise ValueError("Cannot find 'nodes' in utg_cluster.js")

    return json.loads(m.group(1))


def build_system_prompt():
    """
    System prompt (English)
    """
    return (
        "You are an AI agent specialized in understanding smartphone UI pages and inferring user intentions.\n"
        "You analyze:\n"
        "1) A single UI page (page-level intent)\n"
        "2) All pages in the same cluster (cluster-level intent)\n\n"
        "You will receive:\n"
        "- Node screenshot\n"
        "- Optional interaction bounding boxes (bbox)\n"
        "- Cluster info and cluster summary\n"
        "- App package name\n\n"
        "Output must contain **five parts**:\n"
        "1. Observation:\n"
        "2. Title:\n"
        "3. Function Blocks:\n"
        "4. Intention (Page-level Intent):\n"
        "5. App-level Intention (Cluster-level Intent):\n"
        "Keep the format exactly as above.\n"
    )


def build_user_prompt(package_name, node, cluster, bboxes):
    """
    Build user prompt containing node info, cluster info, bbox, etc.
    """
    bbox_text = (
        "\n".join([f"- {bbox}" for bbox in bboxes])
        if bboxes else "(no user interaction bounding box available)"
    )

    prompt = (
        f"App package name: {package_name}\n\n"
        f"### Node Information\n"
        f"Node ID: {node['id']}\n"
        f"Activity: {node['activity']}\n"
        f"Screenshot path: {node['image']}\n\n"
        f"### Interaction Context (bbox)\n"
        f"{bbox_text}\n\n"
        f"### Cluster Information\n"
        f"Cluster ID: {node['cluster_id']}\n"
        f"Cluster size: {cluster.get('size','')}\n"
        f"Cluster nodes: {cluster.get('nodes','')}\n"
        f"Cluster summary: \"{cluster.get('summary', '')}\"\n\n"
        f"---\n\n"
        f"### TASK\n"
        f"Analyze the screenshot and output with EXACTLY the following format:\n\n"
        f"1. Observation:\n"
        f"2. Title:\n"
        f"3. Function Blocks:\n"
        f"4. Intention:\n"
        f"5. App-level Intention:\n"
    )

    return prompt


def summarize_node_intent(vlm_client: VLMClient, package_name, node, cluster, bboxes):
    """
    Perform VLM (Vision-Language Model) call.
    """
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(package_name, node, cluster, bboxes)

    full_prompt = system_prompt + "\n\n" + user_prompt


    image_root_path = "C:\\Projects\\AndroidTaskAutomation\\4_intent_generation\\utg\\NetEase Cloud Music\\states\\"
    image_path = image_root_path + node["image"]


    result = vlm_client.run(
        prompt=full_prompt,
        image_url=image_path,
        enable_thinking=False  # 可改成 True
    )

    return result["content"]


def run_intent_generation(
    package_name: str,
    utg_root_path: str,
    bbox_dict: dict = None,
):  
    # 1) 每个线程复用的初始化函数（只执行一次）
    def _init_worker(_vlm_client):
        global thread_vlm_client
        thread_vlm_client = _vlm_client

    # 2) 线程任务：处理单个 node
    def _process_node(task):
        node_id, cluster_id, cluster_data, package_name, bbox_dict = task
        try:
            if node_id not in node_map:
                return node_id, None, "[Warning] node_id not found in UTG nodes"

            node = node_map[node_id]
            bboxes = bbox_dict.get(node_id, []) if bbox_dict else []

            image_path = os.path.abspath(node["image"])
            intent_text = summarize_node_intent(
                vlm_client=thread_vlm_client,
                package_name=package_name,
                node=node,
                cluster=cluster_data,
                bboxes=bboxes,
            )
            return node_id, intent_text, None
        except Exception as e:
            return node_id, None, f"[Error] {e}"

    # 3) 并行处理当前 cluster 的 nodes
    def _parallel_process_cluster(cluster_id, cluster_data, package_name, bbox_dict, max_workers, node_map, results):
        node_ids = cluster_data.get("nodes", [])
        tasks = [(nid, cluster_id, cluster_data, package_name, bbox_dict) for nid in node_ids]

        with ThreadPoolExecutor(
            max_workers=max_workers, initializer=_init_worker, initargs=(vlm,)
        ) as pool:
            futures = {pool.submit(_process_node, t): t[0] for t in tasks}
            pbar = tqdm(total=len(futures), desc=f"Cluster {cluster_id}", unit="node")
            for future in as_completed(futures, timeout=60):  # 迭代器层面的超时
                try:
                    node_id, intent_text, err = future.result(timeout=60)  # 任务层面的超时
                except Exception as e:
                    node_id = futures[future]
                    err = str(e)
                    intent_text = None
                if err:
                    tqdm.write(f"[WARN] node={node_id} error: {err}")
                else:
                    # 写入共享 results（主进程合并）
                    results.setdefault(cluster_id, {})[node_id] = {
                        "intent": intent_text,
                        "image": node_map[node_id].get("image"),
                    }
                pbar.update(1)
            pbar.close()

    """
    主流程：对每个 cluster 内部的 node 生成 intent。
    """

    cluster_info_path = os.path.join(utg_root_path, "cluster_summaries.json")
    utg_cluster_js_path = os.path.join(utg_root_path, "utg_clustered.js")
    output_path = os.path.join(utg_root_path, "intent_results.json")

    print(f"Loading cluster info from: {cluster_info_path}")
    cluster_info = load_json(cluster_info_path)

    print(f"Loading UTG nodes from: {utg_cluster_js_path}")
    nodes = load_utg_nodes(utg_cluster_js_path)

    # 把所有 nodes 转成 {node_id → node_data} 的 map（方便 lookup）
    node_map = {node["id"]: node for node in nodes}

    print("Initializing VLM client...")
    vlm = VLMClient()

    results = {}  # 普通 dict，最后由主进程一次性更新

    clusters = cluster_info.get("clusters", {})
    max_workers = min(32, (os.cpu_count() or 4) * 2)

    # 如需多进程并行处理“不同 cluster”，再包一层 ProcessPoolExecutor
    for cluster_id, cluster_data in clusters.items():
        _parallel_process_cluster(
            cluster_id=cluster_id,
            cluster_data=cluster_data,
            package_name=package_name,
            bbox_dict=bbox_dict,
            max_workers=max_workers,
            node_map=node_map,
            results=results,  # 传普通 dict
        )

    final_output = build_final_output(results)
    save_json(final_output, output_path)
    print(f"✔ Intent generation completed → {output_path}")

def build_final_output(per_cluster):
    final = []
    for cluster_id, node_dict in per_cluster.items():
        nodes_out = []
        for nid, item in node_dict.items():
            intent_raw = item.get("intent")
            # 保证 intents 为列表
            if isinstance(intent_raw, list):
                intents = [str(x).strip() for x in intent_raw if str(x).strip()]
            else:
                intents = [str(intent_raw).strip()] if str(intent_raw).strip() else []
            nodes_out.append({
                "node_id": str(nid),
                "intents": intents
            })
        final.append({
            "cluster_id": str(cluster_id),
            "nodes": nodes_out
        })
    return final

if __name__ == "__main__":
    package_name = "com.netease.cloudmusic"
    utg_root_path = "C:\\Projects\\AndroidTaskAutomation\\4_intent_generation\\utg\\NetEase Cloud Music"

    run_intent_generation(
        package_name,
        utg_root_path,
        bbox_dict={},
    )
