import json
from pathlib import Path
from PIL import Image, ImageDraw

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# -----------------------------
#  新增：生成 edge 图像（带 bbox 的 from + to 拼接）
# -----------------------------
def make_edge_img_single_edge(edge, graph_dir, save_dir):
    """
    根据 edge 输入生成带 bbox 的合成图，并返回保存路径。
    输入 edge 示例：
    {
        "from": "s0012",
        "to": "s0013",
        "bboxes": [[x1,y1,x2,y2], ...]
    }
    """
    from_node = edge["from"]
    to_node = edge["to"]
    bboxes = edge.get("bboxes", [])

    from_img_path = Path(graph_dir) / "states" / f"{from_node}.png"
    to_img_path = Path(graph_dir) / "states" / f"{to_node}.png"

    # 输出目录创建
    save_dir = Path(save_dir)
    save_dir.mkdir(exist_ok=True, parents=True)

    save_path = save_dir / f"{from_node}__to__{to_node}.png"

    # --- 生成合成图 ---
    combined_images = []

    for bbox in bboxes:
        img = Image.open(from_img_path).copy()
        draw = ImageDraw.Draw(img)
        draw.rectangle(bbox, outline="red", width=3)
        combined_images.append(img)

    # 如果没有 bbox，仍然加入单张 from_img
    if not bboxes:
        combined_images.append(Image.open(from_img_path))

    combined_images.append(Image.open(to_img_path))

    total_width = sum(img.size[0] for img in combined_images)
    max_height = max(img.size[1] for img in combined_images)

    edge_img = Image.new('RGB', (total_width, max_height), (255, 255, 255))
    current_x = 0
    for img in combined_images:
        edge_img.paste(img, (current_x, 0))
        current_x += img.size[0]

    edge_img.save(save_path)
    return str(save_path)

# ------------------------------------------------------
#  Prompt Builder （加入了 edge image path）
# ------------------------------------------------------
def build_edge_prompt(cluster_context, action_types, edge_type, edge_img_path, other_cluster_context=None):
    """
    edge_type ∈ {"intra", "inter"}
    """

    edge_type_instruction = ""
    if edge_type == "intra":
        edge_type_instruction = """
This transition occurs *within the same cluster*. 
Interpret the action as a **local interaction inside the same functional area**, such as:
- opening a sub-view
- switching tabs or changing visual layout
- revealing additional details
- scrolling or navigating within the same task
- modifying something without leaving the main functional scope

DO NOT describe it as navigating to a new major functionality or leaving the current feature group.
"""
    elif edge_type == "inter":
        edge_type_instruction = f"""
This transition goes *across clusters*, meaning the user leaves one functional area and enters another.
Interpret the action as a **cross-functional navigation**, such as:
- returning to a previous main screen
- jumping to a different module
- opening a distinct new functional section

Previous cluster context:
{cluster_context}

Destination cluster context:
{other_cluster_context}

Your description MUST reflect that the user is moving between different functional domains.
"""

    return {
        "role": "system",
        "content": [{
            "text": f"""
You are an AI assistant summarizing UI transitions inside a mobile app.
You will receive an image pair representing the visual change caused by a user's action.

Your job:
Produce **one concise English sentence** describing the *functional meaning* of the transition.

Focus on:
1. What the user is trying to accomplish
2. The semantic change in the UI
3. The intended goal behind the action

Action types for this edge: {action_types}

--- IMPORTANT INSTRUCTIONS ---
{edge_type_instruction}

--- Cluster Context ---
{cluster_context}

--- Edge image file path ---
{edge_img_path}
"""
        }]
    }

# ------------------------------------------------------
# Cluster context extractor
# ------------------------------------------------------
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

# ------------------------------------------------------
# Main traversal logic （整合 edge image generation）
# ------------------------------------------------------
def traverse_clusters(cluster_info_path, graph_dir, edge_img_output_dir="edge_images"):
    data = load_json(cluster_info_path)

    for cluster_id, cluster in data.items():

        print(f"\n===== Processing Cluster {cluster_id} =====")
        cluster_context = extract_cluster_context(cluster_id, cluster)

        # ------------------------------
        # 1. 遍历簇内边
        # ------------------------------
        for edge in cluster.get("edges_inside_cluster", []):
            action_types = edge.get("action_types", [])
            from_node = edge["from"]
            to_node = edge["to"]

            # --- 生成 edge 图片 ---
            edge_img_path = make_edge_img_single_edge(edge, graph_dir, edge_img_output_dir)

            # --- 构造 prompt ---
            prompt = build_edge_prompt(
                cluster_context=cluster_context,
                action_types=action_types,
                edge_type="intra",
                edge_img_path=edge_img_path,
                other_cluster_context=None
            )

            print("\n[INTRA EDGE]")
            print("From:", from_node)
            print("To:", to_node)
            print("Image:", edge_img_path)
            print("Prompt:", prompt["content"][0]["text"][:200], "...")

        # ------------------------------
        # 2. 遍历跨簇边
        # ------------------------------
        for group in cluster.get("edges_from_other_clusters", []):
            from_cluster_id = group["from_cluster_id"]
            edges = group["edges"]

            other_cluster = data.get(from_cluster_id, {})
            other_cluster_ctx = extract_cluster_context(from_cluster_id, other_cluster)

            for edge in edges:
                action_types = edge.get("action_types", [])
                from_node = edge["from"]
                to_node = edge["to"]

                # --- generate edge image ---
                edge_img_path = make_edge_img_single_edge(edge, graph_dir, edge_img_output_dir)

                prompt = build_edge_prompt(
                    cluster_context=cluster_context,
                    action_types=action_types,
                    edge_type="inter",
                    edge_img_path=edge_img_path,
                    other_cluster_context=other_cluster_ctx
                )

                print("\n[INTER EDGE]")
                print(f"From Cluster {from_cluster_id} → Cluster {cluster_id}")
                print("From:", from_node)
                print("To:", to_node)
                print("Image:", edge_img_path)
                print("Prompt:", prompt["content"][0]["text"][:200], "...")


