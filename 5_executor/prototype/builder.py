import json
import sys
import os
from typing import List, Dict, Set, Tuple
from collections import deque
from itertools import combinations

# 添加父目录到 sys.path，使得可以导入 clients 模块
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from clients.llm_client import LLMClient

# =========================================================
# 1. IO
# =========================================================

def load_tig(path: str) -> Dict:
    """
    读取 TIG JSON 文件。
    Args:
        path: tig.json 路径
    Returns:
        TIG 数据结构（dict）
    """
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_app_description(path: str) -> str:
    """
    读取 App 自然语言简介。
    Args:
        path: 文本文件路径
    Returns:
        纯文本字符串
    """
    with open(path, 'r', encoding='utf-8') as f:
        return f.read().strip()

def save_json(obj: Dict, path: str):
    """
    保存结果为 JSON 文件。
    Args:
        obj: dict 对象
        path: 输出路径
    """
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

# =========================================================
# 2. TIG -> capability graph
# =========================================================

def build_capability_index(tig: Dict) -> Dict[str, Set[str]]:
    """
    构建能力到 TIG 节点的索引。
    Returns:
        {capability: set(node_id)}
    """
    capability_index = {}
    
    for node in tig.get('nodes', []):
        node_id = node.get('id')
        capabilities = node.get('capabilities', [])
        
        for capability in capabilities:
            if capability not in capability_index:
                capability_index[capability] = set()
            capability_index[capability].add(node_id)
    
    return capability_index

def build_capability_graph(tig: Dict) -> Dict[str, Set[str]]:
    """
    构建能力图：节点为 capability，边表示能力共现或可达。
    Returns:
        {capability: set(connected_capabilities)}
    """
    # 首先构建节点 ID 到能力的映射
    node_capabilities = {}
    for node in tig.get('nodes', []):
        node_id = node.get('id')
        capabilities = set(node.get('capabilities', []))
        node_capabilities[node_id] = capabilities
    
    # 初始化能力图
    capability_graph = {}
    all_capabilities = set()
    
    # 收集所有能力
    for caps in node_capabilities.values():
        all_capabilities.update(caps)
    
    for cap in all_capabilities:
        capability_graph[cap] = set()
    
    # 根据节点内能力共现和边连接关系建立能力图
    # 1. 同一节点内的能力相连
    for caps in node_capabilities.values():
        caps_list = list(caps)
        for i in range(len(caps_list)):
            for j in range(i + 1, len(caps_list)):
                capability_graph[caps_list[i]].add(caps_list[j])
                capability_graph[caps_list[j]].add(caps_list[i])
    
    # 2. 根据边的连接关系连接能力
    for edge in tig.get('edges', []):
        source_id = edge.get('source')
        target_id = edge.get('target')
        
        source_caps = node_capabilities.get(source_id, set())
        target_caps = node_capabilities.get(target_id, set())
        
        # 源能力和目标能力相连
        for source_cap in source_caps:
            for target_cap in target_caps:
                capability_graph[source_cap].add(target_cap)
                capability_graph[target_cap].add(source_cap)
    
    return capability_graph

# =========================================================
# 3. Graph traversal -> candidate ability sets
# =========================================================

# def traverse_capability_graph(graph: Dict[str, Set[str]], max_path_length: int = 3, max_candidates: int = 1000) -> List[Set[str]]:
#     """
#     遍历能力图，生成候选能力集合。
#     Args:
#         graph: capability adjacency graph
#         max_path_length: 最大路径长度，控制组合大小
#         max_candidates: 最大候选集合数量，防止组合爆炸
#     Returns:
#         候选能力集合列表
#     """
#     candidates = []
#     visited = set()
    
#     # 优化策略：只从部分节点开始，并限制总候选数
#     start_nodes = list(graph.keys())
    
#     # 对每个节点进行 BFS 遍历
#     for start_cap in start_nodes:
#         if len(candidates) >= max_candidates:
#             break
            
#         # BFS 遍历
#         queue = deque([(start_cap, {start_cap}, 0)])  # 添加深度跟踪
#         local_visited = set()
        
#         while queue and len(candidates) < max_candidates:
#             current_cap, path_set, depth = queue.popleft()
            
#             # 添加当前路径的能力集合作为候选
#             path_tuple = tuple(sorted(path_set))
#             if path_tuple not in visited:
#                 visited.add(path_tuple)
#                 # 只保留有一定规模的能力集合（2个或以上能力）
#                 if len(path_set) >= 2:
#                     candidates.append(path_set.copy())
            
#             # 限制路径长度和扩展次数
#             if depth < max_path_length and len(path_set) < max_path_length:
#                 neighbors = list(graph.get(current_cap, set()))
#                 # 限制每层扩展的邻居数量，避免过度膨胀
#                 for neighbor in neighbors[:10]:  # 最多扩展10个邻居
#                     new_path_set = path_set | {neighbor}
#                     new_path_tuple = tuple(sorted(new_path_set))
#                     if new_path_tuple not in visited and new_path_tuple not in local_visited:
#                         local_visited.add(new_path_tuple)
#                         queue.append((neighbor, new_path_set, depth + 1))
    
#     # 按能力集合大小排序，优先保留中等规模的组合
#     candidates.sort(key=lambda x: (len(x), sorted(x)))
    
#     return candidates[:max_candidates]

def traverse_capability_graph(graph: Dict[str, Set[str]],
                              min_co_occurrence: int = 2,
                              max_candidates: int = 1000) -> List[Set[str]]:
    """
    高频共现子图 + 最小闭包策略生成候选能力集合
    
    Args:
        graph: capability adjacency graph
        min_co_occurrence: 能力对共现阈值
        max_candidates: 最大候选数
    Returns:
        候选能力集合列表（每个集合 >= 2 个能力）
    """

    # =========================
    # Step 1: 统计能力对共现频率
    # =========================
    co_occurrence = {}  # (cap1, cap2) -> count
    for cap, neighbors in graph.items():
        for n in neighbors:
            key = tuple(sorted([cap, n]))
            co_occurrence[key] = co_occurrence.get(key, 0) + 1

    # =========================
    # Step 2: 构建高频能力图
    # =========================
    dense_graph = {cap: set() for cap in graph.keys()}
    for (cap1, cap2), count in co_occurrence.items():
        if count >= min_co_occurrence:
            dense_graph[cap1].add(cap2)
            dense_graph[cap2].add(cap1)

    # =========================
    # Step 3: 找连通子图（connected components）
    # =========================
    visited = set()
    candidates = []

    for cap in dense_graph.keys():
        if cap not in visited:
            # BFS / DFS 找到该连通分量
            component = set()
            stack = [cap]
            while stack:
                node = stack.pop()
                if node not in component:
                    component.add(node)
                    visited.add(node)
                    stack.extend(dense_graph[node] - component)
            # 只保留至少两个能力的子图
            if len(component) >= 2:
                candidates.append(component)

    # =========================
    # Step 4: 最小闭包裁剪（可选）
    # =========================
    # 对每个候选子图，尝试删除非必要能力
    # 删除后仍可完成功能 → 删除
    # 这里留给后续实现或规则/LLM辅助
    # for comp in candidates:
    #     comp = minimal_closure(comp, ...)

    # =========================
    # Step 5: 限制总候选数
    # =========================
    candidates = candidates[:max_candidates]

    return candidates



# =========================================================
# 4. Minimal closure extraction
# =========================================================

def minimal_closure(candidate_set: Set[str], tig_caps: Set[str]) -> List[str]:
    """
    从候选能力集合中提取最小能力闭包
    Args:
        candidate_set: 候选能力集合
        tig_caps: TIG 中所有能力
    Returns:
        最小能力闭包
    """
    # 仅保留 TIG 中存在的能力
    minimal_set = candidate_set & tig_caps
    
    return list(minimal_set)

# =========================================================
# 5. LLM 抽象与合并接口
# =========================================================

def llm_summarize_capabilities(candidate: Set[str], llm_client: LLMClient, app_description: str) -> Tuple[str, str]:
    """
    将能力集合抽象为功能原型。
    输入：
        candidate: 能力集合
        llm_client: LLM 客户端
        app_description: 应用描述
    输出：
        name: 功能原型名称
        description: 自然语言功能描述
    说明：
        - 调用大模型 API 生成 name 与 intent
        - 提供能力列表 + 应用描述作为 prompt
    """
    capabilities_str = ", ".join(sorted(candidate))
    
    prompt = f"""Based on the following app description and capability list, generate a functional prototype for this music app.

App Description:
{app_description}

Capabilities:
{capabilities_str}

Please generate:
1. A concise prototype name (2-3 words)
2. A brief functional description (1-2 sentences)

Format your response as:
Name: [prototype name]
Description: [functional description]"""
    
    try:
        response = llm_client.run(prompt, temperature=0.7, max_tokens=200)
        
        # 解析响应
        lines = response.strip().split('\n')
        name = ""
        description = ""
        
        for line in lines:
            if line.startswith("Name:"):
                name = line.replace("Name:", "").strip()
            elif line.startswith("Description:"):
                description = line.replace("Description:", "").strip()
        
        # 如果解析失败，使用默认值
        if not name:
            name = "_".join(sorted(candidate)[:3])  # 取前 3 个能力组合
        if not description:
            description = f"Prototype combining capabilities: {capabilities_str}"
        
        return name, description
    except Exception as e:
        print(f"LLM 调用出错: {e}")
        name = "_".join(sorted(candidate)[:3])
        description = f"Prototype combining capabilities: {capabilities_str}"
        return name, description

def llm_merge_prototypes(prototypes: List[Dict], llm_client: LLMClient) -> List[Dict]:
    """
    合并语义相似的功能原型，并裁剪非必要能力。
    输入：
        prototypes: 初步生成的 prototype 列表
        llm_client: LLM 客户端
    输出：
        合并后的 prototype 列表
    说明：
        - 调用大模型判断两个候选是否等价
        - 保留最小必要能力闭包
    """
    if len(prototypes) <= 1:
        return prototypes
    
    merged = []
    used_indices = set()
    
    for i, proto1 in enumerate(prototypes):
        if i in used_indices:
            continue
        
        merged_proto = {
            "name": proto1["name"],
            "intent": proto1["intent"],
            "definition": proto1["definition"],
            "core_capabilities": proto1["core_capabilities"].copy(),
            "supporting_tig_nodes": proto1["supporting_tig_nodes"].copy()
        }
        
        # 检查与其他 prototype 的相似性
        for j in range(i + 1, len(prototypes)):
            if j in used_indices:
                continue
            
            proto2 = prototypes[j]
            
            prompt = f"""Compare these two functional prototypes and determine if they are semantically similar or equivalent:

Prototype 1:
Name: {proto1['name']}
Definition: {proto1['definition']}
Capabilities: {', '.join(proto1['core_capabilities'])}

Prototype 2:
Name: {proto2['name']}
Definition: {proto2['definition']}
Capabilities: {', '.join(proto2['core_capabilities'])}

Answer with only 'Yes' (if similar/equivalent) or 'No' (if different)."""
            
            try:
                response = llm_client.run(prompt, temperature=0.3, max_tokens=10)
                if "yes" in response.lower():
                    # 合并两个 prototype
                    merged_proto["core_capabilities"] = list(set(merged_proto["core_capabilities"]) | set(proto2["core_capabilities"]))
                    merged_proto["supporting_tig_nodes"] = list(set(merged_proto["supporting_tig_nodes"]) | set(proto2["supporting_tig_nodes"]))
                    used_indices.add(j)
            except Exception as e:
                print(f"LLM 比较出错: {e}")
        
        merged.append(merged_proto)
    
    return merged

# =========================================================
# 6. 构造 Prototype 对象
# =========================================================

def build_prototype(
    intent: str,
    core_capabilities: List[str],
    supporting_nodes: Set[str],
    definition: str = ""
) -> Dict:
    """
    构造一个完整的功能原型对象。
    Args:
        intent: 功能原型名称或 intent
        core_capabilities: 核心能力闭包
        supporting_nodes: 支持该功能的 TIG 节点集合
        definition: 功能描述
    Returns:
        Prototype 字典
    """
    return {
        "name": intent,
        "intent": intent,
        "definition": definition or f"Functional prototype for {intent}",
        "preconditions": [
            "required_capabilities_available"
        ],
        "postconditions": [
            "functional_goal_achieved"
        ],
        "core_capabilities": core_capabilities,
        "supporting_tig_nodes": list(supporting_nodes)
    }

# =========================================================
# 7. 主流程
# =========================================================

def extract_prototypes(app_name: str, description_path: str, tig_path: str, output_path: str):
    """
    完整 Prototype 抽取流程。
    步骤：
    1. 读取 App 描述 + TIG
    2. 构建 capability graph 和索引
    3. 图算法遍历生成候选能力集合
    4. 提取最小能力闭包
    5. 调用 LLM 生成功能原型名称和描述
    6. 合并语义相似的 prototype
    7. 输出 prototype.json
    """
    print(f"[1/7] 读取应用数据...")
    # 读取输入
    tig = load_tig(tig_path)
    app_description = load_app_description(description_path)
    
    print(f"[2/7] 构建能力图和索引...")
    # 构建能力图和索引
    capability_index = build_capability_index(tig)
    capability_graph = build_capability_graph(tig)
    
    # 收集所有能力
    all_capabilities = set()
    for node in tig.get('nodes', []):
        all_capabilities.update(node.get('capabilities', []))
    
    print(f"[3/7] 遍历能力图生成候选能力集合...")
    # 遍历能力图生成候选能力集合
    # 限制候选数量防止组合爆炸，max_candidates 控制最大候选集合数
    candidates = traverse_capability_graph(capability_graph, max_candidates=500)
    print(f"    生成了 {len(candidates)} 个候选能力集合")
    
    print(f"[4/7] 提取最小能力闭包...")
    # 提取最小能力闭包
    minimal_closures = []
    for candidate in candidates:
        closure = minimal_closure(candidate, all_capabilities)
        if closure:  # 只保留非空闭包
            minimal_closures.append((set(closure), candidate))
    
    print(f"    提取了 {len(minimal_closures)} 个最小闭包")
    
    print(f"[5/7] 初始化 LLM 客户端...")
    # 初始化 LLM 客户端
    try:
        llm_client = LLMClient()
    except Exception as e:
        print(f"    警告：LLM 初始化失败 ({e})，使用默认 prototype")
        llm_client = None
    
    print(f"[6/7] 生成功能原型...")
    # 生成功能原型
    prototypes = []
    
    # 建立能力到节点的反向索引
    capability_to_nodes = {}
    for node in tig.get('nodes', []):
        node_id = node.get('id')
        for cap in node.get('capabilities', []):
            if cap not in capability_to_nodes:
                capability_to_nodes[cap] = set()
            capability_to_nodes[cap].add(node_id)
    
    for closure, original_candidate in minimal_closures:
        # 找到支持这个闭包的 TIG 节点
        supporting_nodes = set()
        for cap in closure:
            supporting_nodes.update(capability_to_nodes.get(cap, set()))
        
        if not supporting_nodes:
            continue
        
        # 如果有 LLM，使用 LLM 生成名称和描述
        if llm_client:
            try:
                name, description = llm_summarize_capabilities(closure, llm_client, app_description)
                prototype = build_prototype(name, list(closure), supporting_nodes, description)
            except Exception as e:
                print(f"    警告：LLM 调用失败 ({e})，使用默认名称")
                prototype = build_prototype(
                    "_".join(sorted(closure)[:2]),
                    list(closure),
                    supporting_nodes
                )
        else:
            # 如果没有 LLM，使用能力名称组合作为原型名称
            prototype = build_prototype(
                "_".join(sorted(closure)[:2]),
                list(closure),
                supporting_nodes
            )
        
        prototypes.append(prototype)
    
    print(f"    生成了 {len(prototypes)} 个初始功能原型")
    
    print(f"[7/7] 合并语义相似的原型...")
    # 合并语义相似的原型
    if llm_client:
        try:
            merged_prototypes = llm_merge_prototypes(prototypes, llm_client)
        except Exception as e:
            print(f"    警告：合并失败 ({e})，使用未合并的原型")
            merged_prototypes = prototypes
    else:
        merged_prototypes = prototypes
    
    print(f"    合并后得到 {len(merged_prototypes)} 个功能原型")
    
    # 保存结果
    result = {
        "app": app_name,
        "num_prototypes": len(merged_prototypes),
        "prototypes": merged_prototypes
    }
    
    save_json(result, output_path)
    print(f"\n✓ 功能原型已保存至: {output_path}")
    
    return result

# =========================================================
# 8. 脚本入口
# =========================================================

if __name__ == "__main__":
    import os
    
    # 设置路径（相对于脚本位置）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)
    
    app_name = "MusicApp"
    description_path = os.path.join(parent_dir, "app_description.txt")
    tig_path = os.path.join(parent_dir, "tig.json")
    output_path = os.path.join(parent_dir, "prototype.json")
    
    extract_prototypes(
        app_name=app_name,
        description_path=description_path,
        tig_path=tig_path,
        output_path=output_path
    )
