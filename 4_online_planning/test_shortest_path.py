"""
测试文件：计算TIG中两个节点之间的最短路径
使用BFS算法查找最短路径
"""

import json
import argparse
from collections import deque
from typing import List, Dict, Optional, Tuple


def load_tig(tig_path: str) -> Tuple[Dict, Dict]:
    """
    加载TIG文件并构建图结构
    
    Args:
        tig_path: TIG JSON文件路径
        
    Returns:
        (nodes_dict, adjacency_list)
        - nodes_dict: {node_id: node_data}
        - adjacency_list: {node_id: [(target_id, edge_data), ...]}
    """
    with open(tig_path, 'r', encoding='utf-8') as f:
        tig_data = json.load(f)
    
    # 构建节点字典
    nodes_dict = {}
    for node in tig_data.get('nodes', []):
        nodes_dict[node['id']] = node
    
    # 构建邻接表
    adjacency_list = {node_id: [] for node_id in nodes_dict.keys()}
    for edge in tig_data.get('edges', []):
        source = edge['source']
        target = edge['target']
        if source in adjacency_list:
            adjacency_list[source].append((target, edge))
    
    return nodes_dict, adjacency_list


def find_shortest_path(
    start_id: str,
    end_id: str,
    nodes_dict: Dict,
    adjacency_list: Dict
) -> Optional[List[Dict]]:
    """
    使用BFS查找两个节点之间的最短路径
    
    Args:
        start_id: 起点节点ID
        end_id: 终点节点ID
        nodes_dict: 节点字典
        adjacency_list: 邻接表
        
    Returns:
        路径列表，每个元素包含 {node, edge}，如果不存在路径则返回None
    """
    # 验证节点存在性
    if start_id not in nodes_dict:
        print(f"错误：起点节点 '{start_id}' 不存在")
        return None
    if end_id not in nodes_dict:
        print(f"错误：终点节点 '{end_id}' 不存在")
        return None
    
    # 特殊情况：起点和终点相同
    if start_id == end_id:
        return [{
            'node': nodes_dict[start_id],
            'edge': None
        }]
    
    # BFS搜索
    queue = deque([(start_id, [start_id])])
    visited = {start_id}
    parent_edge = {}  # 记录每个节点是通过哪条边到达的
    
    while queue:
        current_id, path = queue.popleft()
        
        # 遍历所有邻居
        for target_id, edge_data in adjacency_list.get(current_id, []):
            if target_id not in visited:
                visited.add(target_id)
                new_path = path + [target_id]
                parent_edge[target_id] = (current_id, edge_data)
                
                # 找到终点
                if target_id == end_id:
                    # 重建路径，包含边信息
                    result_path = []
                    for i, node_id in enumerate(new_path):
                        node_data = nodes_dict[node_id]
                        edge_data = None
                        if i > 0:  # 不是起点
                            prev_id = new_path[i-1]
                            edge_data = parent_edge[node_id][1]
                        
                        result_path.append({
                            'node': node_data,
                            'edge': edge_data
                        })
                    
                    return result_path
                
                queue.append((target_id, new_path))
    
    # 未找到路径
    return None


def print_path(path: List[Dict]):
    """
    格式化打印路径
    
    Args:
        path: 路径列表
    """
    print("\n" + "="*80)
    print("找到最短路径！")
    print("="*80)
    print(f"\n路径长度: {len(path)} 个节点, {len(path)-1} 条边\n")
    
    for i, step in enumerate(path):
        node = step['node']
        edge = step['edge']
        
        # 打印节点信息
        print(f"[步骤 {i+1}] 节点: {node['id']}")
        print(f"  意图标签: {node['intent_label']}")
        print(f"  UI描述: {node.get('ui_description', 'N/A')[:100]}...")
        
        # 打印边信息（如果不是最后一个节点）
        if edge:
            print(f"\n  ↓ 执行动作: {edge.get('action', 'N/A')}")
            if edge.get('description'):
                print(f"  动作描述: {edge['description'][:100]}...")
            print()
    
    print("="*80)


def list_all_nodes(nodes_dict: Dict):
    """
    列出所有可用的节点ID
    
    Args:
        nodes_dict: 节点字典
    """
    print("\n所有可用的TIG节点：")
    print("="*80)
    for node_id, node_data in nodes_dict.items():
        intent = node_data.get('intent_label', 'Unknown')
        print(f"  {node_id:30s} -> {intent}")
    print("="*80)
    print(f"总共 {len(nodes_dict)} 个节点\n")


def main():
    parser = argparse.ArgumentParser(
        description='计算TIG中两个节点之间的最短路径',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法：
  # 查找最短路径
  python test_shortest_path.py --tig "../3_intent_graph/utg/NetEase Cloud Music/tig.json" \\
      --start TIG_SEARCH_MODE --end TIG_PLAYBACK_CONTROL
  
  # 列出所有节点
  python test_shortest_path.py --tig "../3_intent_graph/utg/NetEase Cloud Music/tig.json" --list
        """
    )
    
    parser.add_argument('--tig', type=str, required=True,
                        help='TIG JSON文件路径')
    parser.add_argument('--start', type=str,
                        help='起点节点ID')
    parser.add_argument('--end', type=str,
                        help='终点节点ID')
    parser.add_argument('--list', action='store_true',
                        help='列出所有可用的节点ID')
    
    args = parser.parse_args()
    
    # 加载TIG
    print(f"正在加载TIG文件: {args.tig}")
    try:
        nodes_dict, adjacency_list = load_tig(args.tig)
        print(f"成功加载 {len(nodes_dict)} 个节点和 {sum(len(v) for v in adjacency_list.values())} 条边\n")
    except Exception as e:
        print(f"错误：无法加载TIG文件 - {e}")
        return
    
    # 列出所有节点
    if args.list:
        list_all_nodes(nodes_dict)
        return
    
    # 查找最短路径
    if not args.start or not args.end:
        print("错误：请提供 --start 和 --end 参数，或使用 --list 查看所有节点")
        return
    
    print(f"查找从 '{args.start}' 到 '{args.end}' 的最短路径...\n")
    path = find_shortest_path(args.start, args.end, nodes_dict, adjacency_list)
    
    if path:
        print_path(path)
    else:
        print(f"\n未找到从 '{args.start}' 到 '{args.end}' 的路径")
        print("提示：请使用 --list 参数查看所有可用的节点ID")


if __name__ == '__main__':
    main()
