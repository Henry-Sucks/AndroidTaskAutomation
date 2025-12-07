**进行簇功能的总结**
python run.py


# 对UTG预处理的部分
**cluster_summary**
**node_desc**
package_names = ['com.tencent.hm.qqmusic']
graph_dir = "C:\\Projects\\KG-RAG-GUI-Agent\\utg graph"
cluster_info = "xxx"

for node in utg_clustered.js:
    image_path = xxx
    xml_path = xxx (暂时不使用)

    get 对应cluster信息
    get package信息
    vlm -> 理解


**edge_desc**
1. 预加载数据
package_names = ['com.tencent.hm.qqmusic']
graph_dir = "C:\\Projects\\KG-RAG-GUI-Agent\\utg graph"
2. 【关键】预先加载生成好的簇功能摘要，用于辅助生成跨簇边的语义
cluster_summaries = load_json("cluster_intent_summaries.json") 

for edge in utg_clustered.edges:
    # 1. 获取基础节点与操作信息
    src_node_id = edge.source
    tgt_node_id = edge.target
    action_metadata = edge.events # 包含点击坐标、组件类型(bounds, class)
    
    src_img = get_image(src_node_id)
    tgt_img = get_image(tgt_node_id)
    
    # 2. 获取分簇归属
    src_cluster_id = get_cluster_id(src_node_id)
    tgt_cluster_id = get_cluster_id(tgt_node_id)

    # =================================================
    # 情况 A: 簇内边 (Intra-cluster Edge)
    # 目标：描述“在这个页面做了什么具体操作”
    # 服务于：Local RAG (执行层)
    # =================================================
    if src_cluster_id == tgt_cluster_id:
        
        # VLM 关注点：源图片 + 操作位置 (Visual Grounding)
        # Prompt: "在当前页面，点击坐标 [x,y] 处的 [按钮文本] 会发生什么？"
        description = vlm -> understand_atomic_action(src_img, action_metadata)
        
        # Output 示例: "点击播放按钮", "输入搜索关键词", "向上滑动列表"
        save_to_local_index(edge_id, description, src_cluster_id)

    # =================================================
    # 情况 B: 簇间边 (Inter-cluster Edge) -> 也就是你的“路由跳转”
    # 目标：描述“这次跳转是为了进入哪个功能区域”
    # 服务于：Global Routing (规划层)
    # =================================================
    else:
        # 获取目标簇的高层语义（这是这一步能够成功的关键 context）
        target_cluster_intent = cluster_summaries[tgt_cluster_id]
        
        # VLM 关注点：源图片(出发点) + 目标图片(目的地) + 目标簇摘要(语境)
        # Prompt: "用户点击这个按钮从当前页跳转到了一个新的功能区（描述为：{target_cluster_intent}）。
        #          请生成一个简短的导航意图描述。"
        description = vlm -> summarize_routing_intent(src_img, tgt_img, target_cluster_intent)
        
        # Output 示例: "进入个人中心", "前往设置页面", "跳转到订单结算流程"
        save_to_global_routing_index(src_cluster_id, tgt_cluster_id, description, action_metadata)


# RAG部分
## Phase 1: 任务拆解与初始化 (Task Decomposition & Initialization)
```py
decompose_task(instruction, summaries)
输入： 复杂的用户指令 Intent。
辅助输入： Global_Index 中的所有簇功能摘要（作为 LLM 的工具清单）。
处理： 调用 LLM 将 Intent 拆解为可执行的子目标列表。输出： task_queue = [T_1, T_2, ..., T_N]。
```

## Phase 2: 路由与序列生成 (Hierarchical RAG Engine)
```py
def get_next_action_sequence(sub_task, current_state):
    # 1. 定位 (Localization)
    current_cluster_id = localize(current_state) # 识别当前页面属于哪个簇
    
    # 2. 双流检索 (Dual Retrieval)
    
    # 2.1 簇内检索 (Local Hit Search)
    # RAG 检索 Key: sub_task (向量化)
    # Filter: 仅搜索 cluster_id == current_cluster_id 的条目
    local_result, local_score = vector_db.search(
        index="Local_Index", 
        query=sub_task, 
        filter={"cluster_id": current_cluster_id}, 
        threshold=0.85
    )

    # 3. 决策逻辑 (Decision Logic)
    if local_score > 0.8: # 假设阈值0.8
        # 分支 A：簇内命中 (Local Hit)
        print(f"Decision: Execute task within Cluster {current_cluster_id}")
        # 获取完整的簇内操作轨迹
        retrieved_sequence = local_result.trajectory
        
        # 4. 起点对齐 (Alignment)
        # 簇内路径通常从簇的入口节点 (Entry Node) 开始
        entry_node_id = retrieved_sequence[0].source_node_id 
        if not is_node_matched(current_state, entry_node_id):
            # 插入“归位”序列，例如：[Back, Back, ...] 或 NavigateToEntry(current_cluster_id)
            print("Action: Prepending Reset to Entry Node.")
            reset_sequence = generate_reset_sequence(current_state, entry_node_id)
            return reset_sequence + retrieved_sequence
        
        # 如果已对齐，直接返回
        return retrieved_sequence
    
    else:
        # 分支 B：跨簇路由 (Global Routing)
        # 2.2 全局检索目标簇
        # RAG 检索 Key: sub_task (向量化)
        target_cluster_info, global_score = vector_db.search(
            index="Global_Index", 
            query=sub_task, 
            top_k=1 
        )
        target_cluster_id = target_cluster_info.cluster_id

        if current_cluster_id == target_cluster_id:
             # 特殊情况：意图匹配当前簇，但没有现成的路径。
             # 此时可降级为 VLM 探索 (VLM Exploration) 或返回失败。
             print("Decision: Target is here, but RAG failed. Fallback to VLM exploration.")
             return vlm_fallback_explore(current_state, sub_task)
        
        # 3.2 规划跳转路径
        # 在简化的 Cluster Graph 上跑 BFS/Dijkstra
        next_hop_cluster = cluster_graph.find_next_hop(current_cluster_id, target_cluster_id)
        
        # 3.3 检索跳转动作序列 (Transition Trajectory)
        # 检索 Key: next_hop_cluster 的意图 summary
        # Filter: source_cluster_id == current_cluster_id AND target_cluster_id == next_hop_cluster
        transition_record = vector_db.search(
            index="Global_Index",
            query=next_hop_cluster.intent_summary, # 用目标簇的意图作为检索Key
            filter={"source_cluster": current_cluster_id, "target_cluster": next_hop_cluster}
        )
        
        print(f"Decision: Routing {current_cluster_id} -> {next_hop_cluster}")
        # 返回跳转动作（通常是单步，但我们用序列格式保持一致）
        return transition_record.transition_sequence

    # 4. 最终失败/未知
    return "FAILURE_NO_SEQUENCE_FOUND"
```


## Phase 3: 动态执行与任务管理 (Execution & Task Management)
（暂缓实现）