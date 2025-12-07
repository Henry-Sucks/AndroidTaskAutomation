#!/usr/bin/env python3
"""
KG-RAG Result Parser

Parses KG-RAG automation results and converts them
to standardized UTG (UI Transition Graph) format.

Input structure:
/input
    /layout          # XML Layout Files
    /screenshot       # Screenshots
    /widget          # Widget
    metadata.csv
    {package_name}.json  # KG-RAG result JSON file

Output structure:
    utg.js                 # Complete UTG in JavaScript format

Usage:
    python ape_parse.py <input_dir> <output_dir>
"""

import json
import os
import re
from collections import defaultdict

def get_widget_bbox_map(nodes):
    """return all widgets with bounding boxes"""
    widget_bbox_map = {}
    for node in nodes.values():
        exact_scene = node["exactScenes"][0]
        for widget_id, widget_info in exact_scene["widgetList"].items():
            if widget_id in widget_bbox_map:
                continue
            bounds = widget_info['bounds'].replace('][', ',').replace('[', '').replace(']', '')
            bbox = list(map(int, bounds.split(',')))
            widget_bbox_map[widget_id] = bbox
    return widget_bbox_map


def get_action_edge_map(edges):
    """mapping actionId → edge.id"""
    action_edge_map = {}
    for edge in edges:
        for event in edge['events']:
            action_edge_map[event['actionId']] = edge['id']
    return action_edge_map


def build_enhanced_edge_dict(nodes, raw_edges):
    """
    Assemble complete edge dict including bboxes & action types
    return {actionId: {...}}
    """
    widget_bbox_map = get_widget_bbox_map(nodes)
    action_edge_map = get_action_edge_map(raw_edges)

    enhanced_edges = {}

    for node in nodes.values():
        exact_scene = node["exactScenes"][0]
        for scene_action in exact_scene["sceneActionList"]:
            action_id = scene_action['actionId']
            if action_id not in action_edge_map:
                continue
            
            edge_id = action_edge_map[action_id]
            from_node, to_node = edge_id.split('#')

            bboxes = []
            action_types = []

            try:
                for action in scene_action['actionList']:
                    t = action['action'].lower()
                    # swipe type
                    if t == "swipe":
                        t = t + " " + action['swipeType'].lower().replace("swipe", "")
                    action_types.append(t)

                    widget_id = action['widgetId']
                    bbox = widget_bbox_map.get(widget_id)
                    if bbox:
                        bboxes.append(bbox)

                enhanced_edges[action_id] = {
                    "id": edge_id,
                    "bboxes": bboxes,
                    "action_types": action_types,
                    "from": from_node,
                    "to": to_node
                }
            except:
                continue

    return enhanced_edges



def convert_kgrag_to_utg(input_folder, package_name):
    """
    将KG-RAG JSON结果转换为UTG.js格式
    
    Args:
        input_folder: 输入文件夹路径
        package_name: 包名，用于查找JSON文件
    """
    
    # 文件路径
    json_file = os.path.join(input_folder, f"{package_name}.json")
    utg_file = os.path.join(input_folder, "utg.js")
    
    # 读取JSON文件
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 处理节点映射和场景信息
    scene_mapping = {}  # 存储sceneId到节点信息的映射
    node_counter = 1
    
    # 首先收集所有节点信息
    for scene_id, scene_data in data.get("nodes", {}).items():
        exact_scenes = scene_data.get("exactScenes", [])
        if exact_scenes:
            # 取第一个exactScene作为代表
            exact_scene = exact_scenes[0]
            scene_mapping[scene_id] = {
                "short_id": f"{node_counter:04d}",
                "activity": extract_activity_name(exact_scene.get("uri", "")),
                "image": exact_scene.get("img", ""),
                "xml": exact_scene.get("layout", ""),
                "scene_data": exact_scene
            }
            node_counter += 1
    
    # 生成节点列表
    nodes = []
    for scene_id, info in scene_mapping.items():
        nodes.append({
            "id": scene_id,  # 使用前12位作为短ID
            "step": int(info["short_id"]),
            "activity": info["activity"],
            "image": info["image"],
            "xml": info["xml"]
        })
    
    # 生成边列表
    # ---- Enhanced edge generation ----
    print("Building enhanced edges...")

    enhanced_edge_dict = build_enhanced_edge_dict(data["nodes"], data["edges"])

    edges = []
    edge_counter = 1

    for action_id, e in enhanced_edge_dict.items():
        edges.append({
            "id": e["id"],
            "step": edge_counter + 1,
            "bboxes": e["bboxes"],
            "action_types": e["action_types"],
            "from": e["from"],
            "to": e["to"]
        })
        edge_counter += 1
    
    # 写入UTG.js文件
    with open(utg_file, 'w', encoding='utf-8') as f:
        f.write("var nodes = [\n")
        for i, node in enumerate(nodes):
            f.write("  {\n")
            f.write(f'    id: "{node["id"]}",\n')
            f.write(f'    step: {node["step"]},\n')
            f.write(f'    activity: "{node["activity"]}",\n')
            f.write(f'    image: "{node["image"]}",\n')
            f.write(f'    xml: "{node["xml"]}"\n')
            f.write("  }")
            if i < len(nodes) - 1:
                f.write(",")
            f.write("\n")
        f.write("];\n\n")
        
        f.write("var edges = [\n")
        for i, edge in enumerate(edges):
            f.write("  {\n")
            f.write(f'    id: "{edge["id"]}",\n')
            f.write(f'    step: {edge["step"]},\n')
            f.write(f'    from: "{edge["from"]}",\n')
            f.write(f'    to: "{edge["to"]}",\n')
            f.write(f'    bboxes: {json.dumps(edge["bboxes"])},\n')
            f.write(f'    action_types: {json.dumps(edge["action_types"])}\n')
            f.write("  }")
            if i < len(edges) - 1:
                f.write(",")
            f.write("\n")
        f.write("];\n")

def extract_activity_name(uri):
    """
    从URI中提取activity名称
    
    Args:
        uri: Android activity URI
    """
    if not uri:
        return "UnknownActivity"
    
    # 提取activity类名
    if "/" in uri:
        # 格式: com.package.name/.activity.Name
        parts = uri.split("/")
        if len(parts) > 1 and parts[1].startswith("."):
            return parts[0] + parts[1]
        elif len(parts) > 1:
            return parts[1]
    
    return uri.split("/")[-1] if "/" in uri else uri

def generate_raw_action(event, scene_data):
    """
    生成原始动作描述
    
    Args:
        event: 事件数据
        scene_data: 场景数据（用于获取widget信息）
    """
    action_id = event.get("actionId", "")
    
    # 尝试从widget信息中获取更多细节
    # widget_info = find_widget_by_action_id(scene_data, action_id)
    
    # if widget_info:
    #     # 构建详细的action描述
    #     text = widget_info.get("text", "").replace('"', "'").replace("\n", " ")
    #     widget_type = widget_info.get("type", "Unknown")
    #     bounds = widget_info.get("bounds", "")
    #     actions = ",".join(widget_info.get("actions", []))
        
    #     return f"CLICK@{widget_type};text={text};bounds={bounds};actions={actions}"
    # else:
    #     # 基础action描述
    return f"ACTION_{action_id[:8]}"

# def find_widget_by_action_id(scene_data, action_id):
#     """
#     根据actionId查找对应的widget信息
    
#     Args:
#         scene_data: 场景数据
#         action_id: 动作ID
#     """
#     widget_list = scene_data.get("widgetList", {})
    
#     for widget_id, widget_info in widget_list.items():
#         # 检查widget的actions是否包含对应的actionId
#         print(f"Checking widget {widget_id} for actionId {action_id}")
#         if action_id in [action.get("actionId", "") for action in widget_info.get("actions", [])]:
#             return widget_info
    
#     # 如果没有找到精确匹配，尝试通过其他方式匹配
#     for widget_id, widget_info in widget_list.items():
#         if action_id in widget_id:
#             return widget_info
    
#     return None

def main():
    """
    主函数 - 处理命令行参数并执行转换
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='将KG-RAG JSON转换为UTG.js格式')
    parser.add_argument('input_folder', help='输入文件夹路径')
    parser.add_argument('package_name', help='应用包名')
    
    args = parser.parse_args()
    
    try:
        convert_kgrag_to_utg(args.input_folder, args.package_name)
        print(f"转换完成！UTG.js文件已生成在: {os.path.join(args.input_folder, 'utg.js')}")
    except Exception as e:
        print(f"转换过程中出错: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 示例用法（取消注释以直接运行）
    input_folder = "C:\\Projects\\AndroidTaskAutomation\\1_exploration\\results\\NetEase Cloud Music"
    package_name = "com.netease.cloudmusic"
    convert_kgrag_to_utg(input_folder, package_name)
