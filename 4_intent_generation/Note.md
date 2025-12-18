# intent生成部分
这是我实际的操作：在对UTG进行簇类划分之后，我遍历地对UTG中所有state进行分析，具体分析过程是：给出state截图以及所在cluster的context，然后总结出用户到达这个页面能够/需要完成什么任务（intent）；然后由于簇内规模较小，直接使用BFS计算从所有簇的入点到该页面可能的path，以及从该页面到簇所有出点可能的path。
用户任务进来后，做以下的RAG：将用户拆分成几个不同cluster中的子任务，然后生成路径：到达第一个cluster->到达cluster中执行任务的页面->到达第二个cluster->到达cluster中执行任务的页面，返回执行动作序列。

## 第一步：Cluster-Aware Intent Generation (簇感知的意图生成)
```py
# 核心输入：已经分好簇的 UTG 节点，以及该节点所属的 Cluster Summary
# Cluster Summary 例子："支付与订单结算模块，包含选择优惠券、确认金额和输入密码。"

def generate_cluster_aware_intent(node, cluster_summary):
    
    prompt = f"""
    You are an AI agent analyzing a specific functional module (Cluster) of a mobile App.
    
    Context Info:
    - Current Cluster Function: {cluster_summary} (This is the "Big Picture" of where we are)
    - Current Page Screenshot: <image_input>
    
    Please analyze this page and output structured JSON:
    
    1. "Page_Description": <Describe UI elements briefly>
    2. "Atomic_Intent": <What specifically can the user DO on this page? e.g., 'Input payment password', 'Select a voucher'>
    3. "Cluster_Contribution": <How does this page contribute to the Cluster's goal? e.g., 'Finalize the transaction', 'Authenticate user'>
    
    Constraint: Keep intents distinct. 'Atomic' is micro-action, 'Cluster' is the sub-goal.
    """
    
    response = vlm_model.generate(prompt, image=node.screenshot)
    return parse_json(response)
```

## 第二步：Intra-Cluster Path Generation (生成簇内路径)
```py
import networkx as nx

def generate_intra_cluster_paths(utg_graph, clusters, intent_database):
    """
    为每一个 Intent 生成从“簇入口”出发的路径
    """
    local_skills_library = [] # 这就是你的 Local Vector DB 的数据源

    for cluster_id, nodes in clusters.items():
        # 1. 【关键】自动识别当前簇的“入口节点列表”
        entry_nodes = identify_entry_nodes(utg_graph, cluster_id)
        # 能不能利用语义选择最合理的入口呢？

        # 如果没有明显的外部入口（比如孤岛簇），可能需要人工指定或选中心性最高的节点
        if not entry_nodes:
            entry_nodes = [get_central_node(nodes)]

        # 创建簇的子图 (Subgraph)，只包含簇内节点和边
        cluster_subgraph = utg_graph.subgraph(nodes)

        # 2. 遍历该簇内的所有 Intent
        relevant_intents = [i for i in intent_database if i['cluster_id'] == cluster_id]

        for intent in relevant_intents:
            target_node = intent['node_id']
            best_path = None
            min_length = float('inf')

            # 3. 寻找从【任意入口】到【目标Intent】的最短路径
            # 这里不需要 LLM BFS，因为簇通常较小，普通 BFS 足够快且准确
            for start_node in entry_nodes:
                try:
                    path = nx.shortest_path(cluster_subgraph, source=start_node, target=target_node)
                    if len(path) < min_length:
                        min_length = len(path)
                        best_path = path
                except nx.NetworkXNoPath:
                    continue
            
            # 4. 如果找到了路径，转换成 Action 序列并保存
            if best_path:
                action_sequence = convert_nodes_to_actions(best_path, utg_graph)
                
                # 构建最终的 RAG 条目
                skill_entry = {
                    "key_intent": intent['atomic_intent'],   # 向量检索的 Key
                    "cluster_id": cluster_id,
                    "start_node_type": "entry_point",        # 标记这是从门口开始的
                    "value_trajectory": action_sequence,     # 向量检索的 Value (操作序列)
                    "entry_node_id": best_path[0]            # 记录入口，用于“对齐”
                }
                local_skills_library.append(skill_entry)

    return local_skills_library

def identify_entry_nodes(full_graph, current_cluster_id):
    """
    逻辑：遍历全图，找到所有 (u, v)，其中 u 不属于当前簇，v 属于当前簇。
    v 就是入口节点。
    """
    entries = set()
    for u, v in full_graph.edges():
        if get_cluster_id(u) != current_cluster_id and get_cluster_id(v) == current_cluster_id:
            entries.add(v)
    return list(entries)
```




```py
import networkx as nx

def generate_intra_cluster_paths(utg_graph, clusters, intent_goal):
    local_skills_library = []

    for cluster_id, nodes in clusters.items():
        # 0. 构建子图
        cluster_subgraph = utg_graph.subgraph(nodes).copy() # Copy一份以免修改原图

        # 1. 利用语义，选取合适的开始节点

        # 2. 使用BFS算出最短路径

        # 3. 输出：cluster_id：{intent： intent_path}
```







我的困境在哪里？
我现在的做法：
输入：UTG，每个节点（状态）进行了分簇；每个功能分簇含有自己的summary信息；每个状态拥有对应的屏幕截图和xml文件；与此同时，每条边（操作）含有对应的动作类型和组件截图
输出是什么？输出是：每个功能分簇含有自己的summary信息后，还拥有属于这个功能簇中的intent的集合<->簇内的操作序列？

分簇环节：是否还需要进行更高一步的合并/抽象？
输入：自动化探索工具得到的UTG，节点（状态）包含对应的截图/XML，边（操作）包含操作类型、操作的元素（图中的坐标/XML元素）
原先的输出是：将utg中每个节点进行分簇，每个节点增添一个属性cluster_id
但是考虑节点的重复探索、状态爆炸等因素，在之后是否要添加更高一步的合并/抽象？





# 2025/12/18

Local Index的结构化形式：
```py
LocalIndex = {
    cluster_id: {
        "summary": "簇功能描述",
        "atomic_tasks": [
            {
                "intent": "点击冬眠按钮",
                "action_sequence": [
                    {
                        "node_id": "A1C5F507783DEBFC9DA68759B6C2EAD4",
                        "element": {
                            "xpath": "...",
                            "bounds": "[696,654][864,744]",
                            "text": "冬眠",
                            "type": "android.view.ViewGroup"
                        },
                        "action_type": "CLICK"
                    }
                ],
                "preconditions": [
                    "当前在页面 X",
                    "按钮可见"
                ],
                "postconditions": [
                    "页面跳转到 Y"
                ],
                "confidence": 0.95  # 可选，用于排序候选
            },
            ...
        ]
    },
    ...
}
```


ok，任务已经定好，开始实现！

