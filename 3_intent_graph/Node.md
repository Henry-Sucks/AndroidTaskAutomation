# 2026/01/06

You are a system architect designing a Task Intent Graph (TIG) for a GUI Agent.
Input 1: A list of Functional Clusters from a raw User Transition Graph (UTG).
Input 2: Connections between these clusters observed in the UTG.

**Goal:**
Construct a high-level TIG that represents the *business logic* flow, independent of specific UI widgets.

**Rules:**
1. **Merge Redundancy:** If multiple clusters serve the same core intent (e.g., "Home Page" and "Genre List" both serve "Discovery"), merge them into one TIG Node (e.g., "Discovery_State").
2. **Abstract Actions:** Label the edges with the user's intent (e.g., "Confirm", "Select_Item", "Search"), not "Click".
3. **Ignore Noise:** Ignore back-buttons, ads, or login interruptions unless they are critical flows.

**Input Data:**
Clusters:
- Cluster_01: Music Player Interface (Play, Pause, Seek)
- Cluster_02: Search Results List
- Cluster_03: Home Page Recommendations
- Cluster_04: Artist Profile (similar to Home Page, just list of songs)

Connections:
- Cluster_03 -> Cluster_02 (via Search Bar)
- Cluster_02 -> Cluster_01 (via Song Click)
- Cluster_03 -> Cluster_04 (via Artist Icon)
- Cluster_04 -> Cluster_01 (via Song Click)

**Output Format (JSON):**
Produce the TIG nodes and edges.



# 2026/01/07

第一步：节点抽象——意图归一化
并不是每一个 UTG 簇都有资格成为 TIG 节点。只有代表“关键业务状态”的簇才会被保留，且功能相似的簇会被合并。

输入： UTG 中所有簇的 ClusterSummary (由之前的 VLM 生成)。
LLM处理：
将簇的描述映射到领域本体 (Domain Ontology)
```
Cluster A (首页推荐) -> Browse_Mode
Cluster B (歌单详情) -> Browse_Mode (或者 List_View)
Cluster C (全屏播放) -> Playback_Mode
```
问题：抽象的依据是什么？
操作：
Merge (合并): 如果 Cluster A 和 Cluster B 被映射到了同一个 TIG 意图（如都是浏览），则在 TIG 中将它们合并为一个节点。
Discard (丢弃): 如果某个簇是“广告弹窗”或“加载中”，则标记为噪音，不生成 TIG 节点。


第二步：边抽象 (Edge Abstraction) —— 动作语义化
逻辑：UTG 的边是具体的点击 (Click bounds=[x,y])，TIG 的边必须是语义动作 (Action Play(song)).

1. 遍历：检查 UTG 中跨越簇的连接 (Inter-cluster edges)。
2. 聚合：如果从 Cluster A 到 Cluster B 有 10 条边（比如点击不同的歌曲都能跳转），在 TIG 中只生成一条有向边。
3. 语义化：
分析触发跳转的 UI 元素的属性（文本、图标）。
UI Event: Click "Play All" icon.
TIG Edge: Action = Initiate_Playback, Type = Batch.


第三步：
拓扑清洗
逻辑： 移除回路和无效跳转。
自环移除： TIG 关注状态的改变。如果在 UTG 中，用户在“搜索簇”内点击了“下一页”，状态依然是“搜索簇”，这种边通常在 TIG 中被忽略（或作为节点内部属性）。
双向边处理： “返回”操作（Back）通常不记录在 TIG 的主流程中，除非它是业务逻辑的一部分（如“取消订单”）。



# 2026/01/08

输入：当前节点summary+从该节点出的edge的summary
输出：是什么？



```py
class TIGNode:
    id: str  # hash_id
    intent_label: str
    mapped_utg_ids: List[str]
    capabilities: Set[str]


class TIGEdge:
    source_tig_id: str
    target_tig_id: str
    action_signature: str    # e.g., "Play(item_id)"
    description: str
```


```py
def generate_tig_from_utg(utg_nodes: List[UTGNode], utg_edges: List[UTGEdge]):
    print(">>> Phase 1: Analyzing Node Intents...")
    node_analysis_map = {}

    for u_node in utg_nodes:
        # 1. 收集上下文：当前节点摘要 + 所有出边的动作摘要
        # 理由："我能干什么" 决定了 "我是什么"
        out_edges = [e for e in utg_edges if e.id in u_node.outgoing_edge_ids]
        edge_summaries = [e.summary for e in out_edges]

        # 2. LLM 调用：生成语义单元
        # Input: Node Summary + Edge Summaries
        # Output: { "intent_label": "Search_Mode", "capabilities": ["Input_Query", ...] }
        semantic_info = llm_analyze_semantics(u_node.summary, edge_summaries)

        node_analysis_map[u_node.id] = semantic_info


    print(">>> Phase 2: Merging Nodes...")
    tig_nodes_dict = {} # Intent_Label -> TIGNode

    for u_node_id, info in node_analysis_map.items():
        label = info['intent_label']
        
        # 如果是噪音（如广告、加载中），则跳过
        if label == "NOISE":
            continue
        

        # 这个地方是否可以更鲁棒一些：让大模型决定是否合并？或者引入相似度机制？
        # 留个不同入口吧，可以直接合并，后面可以添加大模型判断的机制
        if label not in tig_nodes_dict:
            # 创建新的 TIG 节点
            tig_nodes_dict[label] = TIGNode(
                id=f"TIG_{label.upper()}",
                intent_label=label,
                mapped_utg_ids=[],
                capabilities=set()
            )
        
        # 将物理节点归并到逻辑节点中
        tig_node = tig_nodes_dict[label]
        tig_node.mapped_utg_ids.append(u_node_id)
        tig_node.capabilities.update(info['capabilities'])



    # -------------------------------------------------
    # 阶段 3: 边抽象与连接 (Edge Abstraction)
    # 遍历所有 UTG 边，建立 TIG 节点之间的连接
    # -------------------------------------------------
    print(">>> Phase 3: Constructing Edges...")

    final_tig_edges = []
    seen_connections = set()    # 用于去重 (Source, Target, Action)

    for u_edge in utg_edges:
        # 1. 查找归属的 TIG 节点
        source_tig = lookup_tig_node(u_edge.source_id, ...)
        target_tig = lookup_tig_node(u_edge.target_id, ...)

        if not source_tig or not target_tig:
            continue

        # 2. 生成动作签名 (Action Signature)
        # e.g., "Toggle(PlayState)", "Scroll(Down)", "Navigate(Settings)"
        action_sig, action_type = llm_analyze_action(u_edge.summary, source_tig, target_tig)

        # =====================================================
        # [关键修改] 自环处理逻辑
        # =====================================================
        if source_tig.id == target_tig.id:
            # 情况 A: 重要的功能性自环 -> 添加到节点能力中
            if action_type == "FUNCTIONAL_INTERACTION":
                # 不生成边，而是增强节点的 capability
                # 例如：在 Playback 节点中添加 "Toggle_Play" 能力
                source_tig.capabilities.add(action_sig)
                print(f"  [Capability] Added {action_sig} to Node {source_tig.id}")
            
            # 情况 B: 纯导航/噪音自环 -> 丢弃
            elif action_type == "NAVIGATION_NOISE":
                continue
                
            # 情况 C: 极其特殊的状态突变 (可选) -> 只有极少数情况保留为边
            # 例如：点击"编辑"进入了"编辑模式"，虽然还在当前页，但逻辑状态变了
            # 这种通常建议在 Phase 1 节点抽象时就拆分为两个不同节点

        # =====================================================
        # 非自环处理逻辑 (正常的跳转边)
        # =====================================================
        else:
            connection_key = (source_tig.id, target_tig.id, action_sig)
            if connection_key not in seen_connections:
                new_edge = TIGEdge(
                    source=source_tig.id, target=target_tig.id, 
                    action=action_sig
                )
                final_tig_edges.append(new_edge)
                seen_connections.add(connection_key)


    # -------------------------------------------------
    # 返回最终图结构
    # -------------------------------------------------
    return {
        "nodes": list(tig_nodes_dict.values()),
        "edges": final_tig_edges
    }        

```