# 4_online_planning 模块流程总结

## 概述

本模块实现了一个基于**任务意图图（TIG, Task Intent Graph）**的在线规划系统，用于Android应用的自动化任务执行。整体架构采用**分层规划**思想，将高层任务规划和底层UI交互分离。

---

## 核心组件

### 1. TIGAgent (agent.py) - 任务执行代理

**职责**：总控制器，协调整个任务执行流程

**核心流程**：
1. **初始化阶段**
   - 加载TIG图数据（节点和边）
   - 初始化Grounder（界面定位器）
   - 初始化Planner（路径规划器）

2. **执行循环** (`execute_task`方法)
   ```
   Step 1: 感知与锚定 (Grounding)
           └─ 通过Grounder将当前UI截图映射到TIG节点
   
   Step 2: 全局路径规划 (High-Level Planning)
           └─ 如无计划或需重新规划，使用Planner生成高层动作序列
   
   Step 3: 目标检测
           └─ 检查计划是否执行完成
   
   Step 4: 动作执行 (Action Execution)
           └─ 将抽象动作翻译为具体UI操作
   
   Step 5: 异常处理
           └─ 执行失败时触发重新规划
   ```

**关键特性**：
- 支持自然语言任务描述（如"播放周杰伦的音乐"）
- 执行失败时自动重新锚定和规划
- 最大步数保护（默认10步）

---

### 2. TIGGrounder (grounder.py) - 界面定位器

**职责**：将实时UI截图映射到TIG中的预定义节点

**工作流程**：

```
截图输入
  ↓
VLM分析 → 生成UI功能描述
  ↓
文本转Embedding → 语义向量
  ↓
遍历TIG所有节点 → 计算相似度分数
  ├─ 语义相似度 (70%)：余弦相似度
  └─ 关键词匹配 (30%)：Intent + Capabilities
  ↓
返回最高分节点（需 >= 阈值0.65）
```

**核心方法**：

1. **`ground(screenshot_path, xml_path)`**
   - 输入：截图路径（可选XML层级文件）
   - 输出：匹配的TIGNode或None
   - 流程：截图分析 → Embedding → 相似度匹配

2. **`_analyze_screenshot(screenshot_path)`**
   - 使用VLM分析截图生成UI功能描述
   - 关注：主要意图、交互元素、可用能力

3. **`_text_to_embedding(text)`**
   - 调用阿里云DashScope Embedding API
   - 支持本地缓存（避免重复API调用）
   - Fallback：API失败时使用hash-based embedding

4. **`_compute_similarity_score(ui_embedding, node)`**
   - 混合打分机制：
     - 语义向量相似度：70%
     - 关键词匹配：30%（Intent标签 + Capabilities）

**技术亮点**：
- ✅ **缓存优化**：基于文本hash的本地embedding缓存
- ✅ **鲁棒性**：API失败时自动降级到hash方法
- ✅ **混合匹配**：语义理解 + 关键词匹配提高准确率

---

### 3. TIGPlanner (planner.py) - 路径规划器

**职责**：在TIG图上规划从当前节点到目标节点的最短路径

**核心方法**：

1. **`plan(start_node_id, target_intent)`**
   - 使用Dijkstra算法计算最短路径
   - 支持边权重（cost字段）
   - 返回：TIGEdge对象列表（动作序列）

2. **`plan_from_natural_language(start_node_id, task_description)`**
   - 自然语言任务 → LLM理解 → 目标节点ID
   - 调用`plan`方法完成路径规划
   - 流程：
     ```
     用户任务 "播放周杰伦的音乐"
       ↓
     LLM分析任务意图 + TIG所有节点信息
       ↓
     选择最匹配的目标节点 (如: TIG_PLAYBACK_CONTROL)
       ↓
     Dijkstra算法规划路径
       ↓
     返回动作序列: [Search(Jay Chou), SelectSong(), Play()]
     ```

3. **`_match_task_to_tig_node(task_description)`**
   - 构建LLM提示词，包含所有TIG节点信息
   - LLM返回JSON：`{reasoning, selected_node_id}`
   - 验证节点ID有效性

**算法细节**：
- **Dijkstra最短路径**：优先队列 + 访问标记
- **优先级队列**：`(累积成本, 当前节点, 路径历史)`
- **终止条件**：到达任意目标意图的节点

---

## 数据结构

### TIGNode（TIG节点）
```python
@dataclass
class TIGNode:
    id: str                    # 节点唯一标识
    intent_label: str          # 意图标签 (如 "SEARCH", "PLAYBACK")
    mapped_utg_ids: List[str]  # 映射的原始UTG状态ID
    capabilities: List[str]    # 该界面支持的动作列表
    ui_description: str        # UI功能描述文本
    embedding: np.ndarray      # 节点的语义向量（用于grounding）
```

### TIGEdge（TIG边）
```python
@dataclass
class TIGEdge:
    source_id: str         # 起始节点ID
    target_id: str         # 目标节点ID
    action_signature: str  # 抽象动作 (如 "Search(query)")
    cost: float           # 边权重（默认1.0）
```

---

## 完整工作流程示意

```
用户输入: "搜索周杰伦的音乐"
    ↓
┌─────────────────────────────────────┐
│  1. TIGAgent 初始化                 │
│     - 加载TIG图                     │
│     - 初始化Grounder & Planner      │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  2. Grounding（第一次）             │
│     截图 → VLM分析 → Embedding      │
│     → 匹配TIG节点                   │
│     结果: TIG_MAIN_MENU             │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  3. Planning（生成路径）            │
│     任务 → LLM理解 → 目标节点       │
│     TIG_MAIN_MENU → TIG_SEARCH      │
│     路径: [Navigate(Search),        │
│            Search(Jay Chou),        │
│            SelectSong()]            │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  4. 执行循环                        │
│     Step 1: 执行 Navigate(Search)   │
│     Step 2: Grounding确认状态       │
│     Step 3: 执行 Search(Jay Chou)   │
│     Step 4: Grounding确认状态       │
│     Step 5: 执行 SelectSong()       │
│     ...                             │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  5. 任务完成或异常处理              │
│     - 成功：计划执行完毕            │
│     - 失败：重新Grounding & 规划    │
│     - 超时：达到最大步数限制        │
└─────────────────────────────────────┘
```

---

## 技术特点

### 优势
1. **分层抽象**：高层TIG规划 + 底层UI操作分离，提高可维护性
2. **语义理解**：结合VLM和LLM理解界面和任务
3. **鲁棒性**：失败时自动重新规划，支持动态环境
4. **可扩展性**：通过扩展TIG图支持跨应用导航
5. **性能优化**：Embedding缓存、Dijkstra最短路径

### 关键技术栈
- **VLM (Visual Language Model)**：截图分析
- **LLM (Large Language Model)**：任务理解、节点匹配
- **Embedding API**：阿里云DashScope text-embedding-v4
- **算法**：Dijkstra最短路径、余弦相似度

---

## 当前状态与挑战

### 已完成 ✅
- Grounding结果相对稳定，可复现
- 完整的Agent-Grounder-Planner架构
- 支持自然语言任务输入
- Embedding缓存机制

### 存在问题 ⚠️
1. **Grounding准确率**：与预期结果差距较大
   - 原因：TIG生成质量需要改进
   - 方向：优化聚类算法、提高节点区分度

2. **路径连通性**：部分情况下定位到的两个节点间无有效路径
   - 原因：UTG探索不充分，TIG图不完整
   - 方向：改进探索策略、补全缺失边

3. **动作执行**：`_execute_abstract_action`方法未完整实现
   - 当前：仅返回True（占位符）
   - 需要：将抽象动作映射到具体UI元素并执行

### 改进方向 💡
- **基于Memory的优化**：记录历史执行轨迹，学习最优路径
- **TIG质量提升**：改进聚类和意图识别算法
- **混合策略**：TIG规划失败时降级到ReAct模式局部探索
- **完善动作执行器**：实现抽象动作到具体UI操作的映射

---

## 使用示例

### 1. 测试Grounding（界面定位）
```bash
python grounder.py --tig "utg/Music_Player/tig.json" \
                   --screenshot "test.jpeg" \
                   --threshold 0.65
```

### 2. 测试路径规划
```bash
python test_shortest_path.py --tig "utg/NetEase Cloud Music/tig.json" \
                              --start TIG_PLAYLIST_DISCOVERY \
                              --end TIG_SETTINGS_MENU
```

### 3. 完整任务执行
```bash
# 示例1：音乐播放器
python agent.py --tig "../3_intent_graph/utg/Music_Player/tig.json" \
                --task "打开设置" \
                --screenshot "test.jpeg" \
                --verbose

# 示例2：网易云音乐
python agent.py --tig "../3_intent_graph/utg/NetEase Cloud Music/tig.json" \
                --task "搜索周杰伦的音乐" \
                --screenshot "main_menu.jpeg" \
                --verbose
```

---

## 开发笔记

### 2026/01/08
- ❓ Grounding不太靠谱：变化大、准确率低 -> 必须要实现吗?有什么好方法?
- ❓ TIG是否需要继续合并？
- ✅ 现在grounding效果也算还是比较好,至少可以复现,结果比较稳定
- ⚠️ 和预先的结果差得比较大,这需要在TIG的生成上进一步的下功夫
- ⚠️ 定位到了两个之后,中间没有有效的路径:是UTG自身的原因吗?
- ISSTA 2025: Intention-Based GUI Test Migration for Mobile Apps using Large Language Models : GUI Test语境下的Migration：输入的是测试意图+GUI Event序列；
- 💡 **基于任务，基于memory。我认为也非常清晰。就以这个方向去实现！**


### 2026/01/12
第一步：给每个edge加上一个自然语言的pre_condition


---

## 相关模块

- **前置**：[3_intent_graph](../3_intent_graph/) - 生成TIG图
- **后续**：[5_online_planning](../5_online_planning/) - 可视化与增强版本
- **参考**：[3_context_summarization](../3_context_summarization/) - 上下文总结


