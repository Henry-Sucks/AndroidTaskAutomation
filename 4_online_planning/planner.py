import heapq
import json
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from clients.llm_client import LLMClient


@dataclass
class TIGNode:
    id: str
    intent_label: str
    capabilities: List[str]
    ui_description: str


@dataclass
class TIGEdge:
    source_id: str
    target_id: str
    action_signature: str
    cost: float = 1.0


class TIGPlanner:
    def __init__(self, tig_nodes: List[TIGNode], tig_edges: List[TIGEdge], llm_client: Optional[LLMClient] = None):
        self.nodes_map = {n.id: n for n in tig_nodes}
        self.adjacency_list = self._build_graph(tig_edges)
        self.llm_client = llm_client or LLMClient()

    def plan(self, start_node_id: str, target_intent: str) -> List[TIGEdge]:
        """
        规划路径：从当前节点 ID 到 满足 target_intent 的任意节点
        
        Args:
            start_node_id: 当前 Grounding 得到的节点 ID
            target_intent: 目标意图标签 (e.g., "Playback_Control")
        """
        # 1. 找到所有可能的目标节点 (因为 TIG 中可能有多个节点属于同一意图)
        goal_node_ids = [
            nid for nid, node in self.nodes_map.items() 
            if node.intent_label == target_intent
        ]
        
        if not goal_node_ids:
            raise ValueError(f"TIG 中不存在意图为 {target_intent} 的节点")

        # 2. 运行 Dijkstra 算法寻找最短路径
        # priority_queue: (accumulated_cost, current_node_id, path_history)
        pq = [(0, start_node_id, [])] 
        visited = set()

        while pq:
            cost, curr_id, path = heapq.heappop(pq)

            # A. 检查是否到达目标
            if curr_id in goal_node_ids:
                print(f"🚀 Path Found! Steps: {len(path)}")
                return path

            if curr_id in visited:
                continue
            visited.add(curr_id)

            # B. 扩展邻居
            for neighbor_id, edge_obj in self.adjacency_list.get(curr_id, []):
                if neighbor_id not in visited:
                    new_cost = cost + edge_obj.cost
                    new_path = path + [edge_obj] # 记录路径上的边
                    heapq.heappush(pq, (new_cost, neighbor_id, new_path))

        print("❌ No path found in TIG.")
        return []

    def plan_from_natural_language(self, start_node_id: str, task_description: str, verbose: bool = False) -> List[TIGEdge]:
        """
        从自然语言任务描述生成路径
        
        Args:
            start_node_id: 当前所在节点的 TIG ID
            task_description: 用户的自然语言任务描述 (e.g., "播放一首歌")
            verbose: 是否打印详细信息
        
        Returns:
            路径（TIGEdge列表）
        """
        if verbose:
            print(f"📝 Task: {task_description}")
            print(f"📍 Starting from node: {start_node_id}")
        
        # 1. 使用LLM将自然语言任务映射到目标意图/节点
        target_node_id = self._match_task_to_tig_node(task_description, verbose)
        
        if not target_node_id:
            print("❌ Failed to map task to TIG node")
            return []
        
        target_node = self.nodes_map[target_node_id]
        if verbose:
            print(f"🎯 Target node: {target_node_id} ({target_node.intent_label})")
        
        # 2. 使用Dijkstra算法规划路径
        return self.plan(start_node_id, target_node.intent_label)

    def _match_task_to_tig_node(self, task_description: str, verbose: bool = False) -> Optional[str]:
        """
        使用LLM将自然语言任务映射到最合适的TIG节点
        
        Args:
            task_description: 用户任务描述
            verbose: 是否打印详细信息
        
        Returns:
            最匹配的节点ID
        """
        # 构建候选节点信息
        candidates_info = []
        for node_id, node in self.nodes_map.items():
            candidates_info.append({
                "node_id": node_id,
                "intent_label": node.intent_label,
                "capabilities": node.capabilities,
                "ui_description": node.ui_description
            })
        
        # 构建LLM提示
        prompt = f"""Given a user task and a list of TIG (Task Intent Graph) nodes, identify which node best matches the user's goal.

User Task: {task_description}

Available TIG Nodes:
{json.dumps(candidates_info, indent=2, ensure_ascii=False)}

Instructions:
1. Analyze the user's task intent
2. Compare with each node's intent_label, capabilities, and ui_description
3. Select the node that BEST matches the task goal
4. If no node matches well, select the most related one

Return ONLY a JSON object with this format:
{{{{
    "reasoning": "Brief explanation of why this node matches the task",
    "selected_node_id": "the_node_id"
}}}}"""

        if verbose:
            print(f"\n🔍 Matching task to TIG nodes...")
        
        try:
            response = self.llm_client.run(prompt)
            
            # 解析JSON响应
            # 处理可能的markdown代码块包装
            response_clean = response.strip()
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            if response_clean.startswith("```"):
                response_clean = response_clean[3:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3]
            
            result = json.loads(response_clean.strip())
            
            if verbose:
                print(f"💭 Reasoning: {result.get('reasoning', 'N/A')}")
            
            selected_id = result.get("selected_node_id")
            
            # 验证节点ID是否存在
            if selected_id and selected_id in self.nodes_map:
                return selected_id
            else:
                print(f"⚠️ LLM returned invalid node_id: {selected_id}")
                return None
                
        except Exception as e:
            print(f"❌ Error in LLM matching: {e}")
            return None

    def _build_graph(self, edges: List[TIGEdge]) -> Dict:
        """构建图的邻接表"""
        adj = {}
        for edge in edges:
            if edge.source_id not in adj:
                adj[edge.source_id] = []
            # 将边对象本身存储起来，以便返回路径时包含 action_signature
            adj[edge.source_id].append((edge.target_id, edge))
        return adj


# ============= CLI 测试接口 =============
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="TIG Planner - 从自然语言任务生成路径")
    parser.add_argument("--tig_path", type=str, required=True, help="TIG JSON文件路径")
    parser.add_argument("--start_node", type=str, required=True, help="起始节点ID")
    parser.add_argument("--task", type=str, required=True, help="自然语言任务描述")
    parser.add_argument("--verbose", action="store_true", help="打印详细信息")
    
    args = parser.parse_args()
    
    # 加载TIG
    print(f"📂 Loading TIG from: {args.tig_path}")
    with open(args.tig_path, 'r', encoding='utf-8') as f:
        tig_data = json.load(f)
    
    # 转换为数据类
    nodes = [
        TIGNode(
            id=n["id"],
            intent_label=n["intent_label"],
            capabilities=n["capabilities"],
            ui_description=n["ui_description"]
        )
        for n in tig_data["nodes"]
    ]
    
    edges = [
        TIGEdge(
            source_id=e["source_id"],
            target_id=e["target_id"],
            action_signature=e["action_signature"],
            cost=e.get("cost", 1.0)
        )
        for e in tig_data["edges"]
    ]
    
    print(f"✅ Loaded {len(nodes)} nodes, {len(edges)} edges\n")
    
    # 初始化Planner
    planner = TIGPlanner(nodes, edges)
    
    # 执行规划
    path = planner.plan_from_natural_language(
        start_node_id=args.start_node,
        task_description=args.task,
        verbose=args.verbose
    )
    
    # 输出结果
    if path:
        print(f"\n✅ Generated Plan ({len(path)} steps):")
        for i, edge in enumerate(path, 1):
            print(f"  {i}. {edge.action_signature}")
            print(f"     {edge.source_id} → {edge.target_id}")
    else:
        print("\n❌ No path found")
