import os
import re
import json
import sys
from typing import Dict, List, Any

from PIL import Image, ImageDraw
from tqdm import tqdm

current_path = os.getcwd()
sys.path.append(current_path)

from utils import load_json
from clients.vlm_client import VLMClient


# ------------------------------------------------------------
# Helper: draw bboxes & merge into one image
# ------------------------------------------------------------
def make_edge_img(from_img_path, to_img_path, bboxes, save_path):
    combined_images = []

    for bbox in bboxes:
        from_img = Image.open(from_img_path)
        draw = ImageDraw.Draw(from_img)
        draw.rectangle(bbox, outline="red", width=3)
        combined_images.append(from_img)

    combined_images.append(Image.open(to_img_path))

    total_width = sum(img.size[0] for img in combined_images)
    max_height = max(img.size[1] for img in combined_images)

    edge_img = Image.new("RGB", (total_width, max_height), (255, 255, 255))

    current_x = 0
    for img in combined_images:
        edge_img.paste(img, (current_x, 0))
        current_x += img.size[0]

    edge_img.save(save_path)
    return save_path


# ------------------------------------------------------------
# Prompt builder (your version + bbox context)
# ------------------------------------------------------------
def build_edge_prompt(cluster_context, action_types, edge_type, bboxes, other_cluster_context=None):
    """
    edge_type: "intra" or "inter"
    """

    bbox_context = (
        f"\nThe transition was triggered by user interaction at the following screen positions:\n{bboxes}\n"
        if bboxes else "\n(No bounding box interaction data provided.)\n"
    )

    if edge_type == "intra":
        edge_type_instruction = """
This transition occurs *within the same cluster*. Interpret the action as a **local interaction**:
- revealing details, switching a tab, opening a sub-view
- scrolling or layout adjustment
- expanding or collapsing UI areas
Do NOT describe this as switching to a new functional module.
"""
    else:
        edge_type_instruction = f"""
This transition goes *across clusters*. User is moving to a **different functional area**.

Source cluster context:
{cluster_context}

Destination cluster context:
{other_cluster_context}

Describe it as a major functional jump, not a local UI change.
"""

    return {
        "role": "system",
        "content": [{
            "text": f"""
You are an AI assistant describing a UI transition caused by user interaction.

Your output: ONE concise English sentence about the functional meaning of the transition.

Action types: {action_types}
Bounding box interaction info:
{bbox_context}

--- Instructions ---
{edge_type_instruction}

--- Cluster Context ---
{cluster_context}
"""
        }]
    }


def extract_cluster_context(cluster_id, cluster_data):
    ctx = []

    llm_summary = cluster_data.get("llm_summary", {})
    if llm_summary:
        ctx.append(f"Cluster {cluster_id} overall function: {llm_summary.get('cluster_overall_function', '')}")

        if "key_functional_capabilities" in llm_summary:
            ctx.append("Key capabilities:\n- " + "\n- ".join(llm_summary["key_functional_capabilities"]))

        if "representative_page_types" in llm_summary:
            ctx.append("Representative page types:\n- " + "\n- ".join(llm_summary["representative_page_types"]))

    return "\n".join(ctx) if ctx else f"(Cluster {cluster_id} has no summary.)"


# ------------------------------------------------------------
# VLM call
# ------------------------------------------------------------
def run_vlm(prompt, image_path):
    client = VLMClient()
    resp = client.run(prompt=prompt, image_url=image_path, enable_thinking=False)
    return resp.get("content", "")


# ------------------------------------------------------------
# MAIN LOGIC: Traverse clusters and edges
# ------------------------------------------------------------
def traverse_clusters(cluster_info_path, utg_dir):
    data = load_json(cluster_info_path)
    output_path = os.path.join(utg_dir, "edge_desc.jsonl")

    screenshot_dir = os.path.join(utg_dir, "screenshot")
    os.makedirs(os.path.join(utg_dir, "edge_img"), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as out_f:

        for cluster_id, cluster in data.items():
            print(f"\n===== Processing Cluster {cluster_id} =====")

            cluster_context = extract_cluster_context(cluster_id, cluster)

            # =====================================================
            # 1. INTRA edges
            # =====================================================
            for edge in tqdm(cluster.get("edges_inside_cluster", []), desc=f"Intra edges C{cluster_id}"):

                from_node = edge["from"]
                to_node = edge["to"]
                bboxes = edge.get("bbox", [])

                from_img = os.path.join(screenshot_dir, f"{from_node}.png")
                to_img = os.path.join(screenshot_dir, f"{to_node}.png")

                edge_img_path = os.path.join(utg_dir, "edge_img", f"{from_node}__{to_node}.jpg")
                make_edge_img(from_img, to_img, bboxes, edge_img_path)

                prompt = build_edge_prompt(
                    cluster_context=cluster_context,
                    action_types=edge.get("action_types", []),
                    edge_type="intra",
                    bboxes=bboxes,
                )

                desc = run_vlm(prompt, edge_img_path)

                out_f.write(json.dumps({
                    "type": "intra",
                    "cluster_id": cluster_id,
                    "from": from_node,
                    "to": to_node,
                    "action_types": edge.get("action_types", []),
                    "bboxes": bboxes,
                    "edge_img": edge_img_path,
                    "description": desc
                }, ensure_ascii=False) + "\n")

            # =====================================================
            # 2. INTER edges
            # =====================================================
            for group in cluster.get("edges_from_other_clusters", []):
                from_cluster_id = group["from_cluster_id"]
                other_cluster = data.get(from_cluster_id, {})
                other_context = extract_cluster_context(from_cluster_id, other_cluster)

                for edge in tqdm(group["edges"], desc=f"Inter edges C{from_cluster_id}->{cluster_id}"):

                    from_node = edge["from"]
                    to_node = edge["to"]
                    bboxes = edge.get("bbox", [])

                    from_img = os.path.join(screenshot_dir, f"{from_node}.png")
                    to_img = os.path.join(screenshot_dir, f"{to_node}.png")

                    edge_img_path = os.path.join(utg_dir, "edge_img", f"{from_node}__{to_node}.jpg")
                    make_edge_img(from_img, to_img, bboxes, edge_img_path)

                    prompt = build_edge_prompt(
                        cluster_context=cluster_context,
                        action_types=edge.get("action_types", []),
                        edge_type="inter",
                        bboxes=bboxes,
                        other_cluster_context=other_context,
                    )

                    desc = run_vlm(prompt, edge_img_path)

                    out_f.write(json.dumps({
                        "type": "inter",
                        "from_cluster": from_cluster_id,
                        "to_cluster": cluster_id,
                        "from": from_node,
                        "to": to_node,
                        "action_types": edge.get("action_types", []),
                        "bboxes": bboxes,
                        "edge_img": edge_img_path,
                        "description": desc
                    }, ensure_ascii=False) + "\n")

    print(f"\n=== Finished. Edge descriptions saved to {output_path} ===")


if __name__ == "__main__":
    # Example:
    # utg_dir = "/path/to/utg/NetEase Cloud Music"
    utg_dir = "./utg"  # modify for your directory
    cluster_info_path = os.path.join(utg_dir, "cluster_info.json")

    traverse_clusters(cluster_info_path, utg_dir)
