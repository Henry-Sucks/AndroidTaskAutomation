# 2025/11/30

给自己留了一些坑：没有处理好原UTG中的重点、重边

我想干什么？写出edge_desc!
应该很简单：根据utg.js中的内容，构造


intent生成阶段
KG-RAG的工作似乎只是分析当前页面


intent generation
修改：对每个node：生成intent-页面内容-页面坐标键值对（是否需要bbox的context？大模型能否做到这一点？是否需要辅助？）


# 2025/12/18

整理进度：现在到哪了？？？什么都不想干啊！
现在的问题是，不知道该怎么生成Global Index和Local Index

Global Index
给定当前簇 + 目标簇，告诉你下一步该去哪一个簇

Local Index 
Local Index = 簇内“子任务 / 原子技能”的库
```py
Local Index L(c) = { τ1, τ2, ..., τn }

τ = (pre, actions, post)
```
pre：执行前状态条件（语义 + UI 结构）
actions：操作序列（click / input / scroll）
post：执行后达到的稳定状态


那就先实现Local Index吧！

# 2025/1/5

现在的问题是什么？

我首先将得到的UTG分簇，分簇后对UTG的每一个边进行总结，总结出这条边（操作）能完成的任务。
然后，根据用户的自然语言任务
首先，为给其UTG的分簇结果，以及总结出的每个簇能干的任务，将用户任务分解成每个簇中能够完成的子任务；然后再在簇中利用相似性匹配，匹配到哪一条边能够完成这个子任务；从而合并成一个操作序列

目前的问题是：
1. 太多簇中有相似功能的原子任务，导致没有办法区分
2. 目前输入只含有用户的自然语言任务，而不包含当前用户所在的界面（状态），这也应该是重要的一部分

在语义空间里极度相似，但在可执行空间里完全不同
抹掉了区分它们的唯一信息源：UI 状态————不应该吗？我需要剥离出其状态，KG-RAG是这么做的


条件化
(NL 任务, 当前 UI 状态)
→ 当前状态下“可推进任务意图”
→ 当前状态下可执行的 action
→ 执行 → 新状态
→ 循环


新建一层？
任务意图层（Task Intent Graph）← 高阶规划在这里
功能能力层（Cluster Capability Layer） ← 你现有 UTG 分簇就在这里
执行层（State-Action UTG）


关注小论文！————任务迁移！

第一步：
正确的高阶规划（你要的那种）：
```
T1: 进入音乐 App
T2: 进入可输入搜索词的上下文
T3: 得到歌曲结果列表
T4: 消费目标歌曲
T5: 对该内容执行“收藏”
```

第二步：
在每一个高阶子目标Ti下：
你做的不是：“选哪个 cluster 当下一个节点”
而是：“哪些 cluster 能支持我完成当前子目标？”
这是 1 对多的关系，本来就不该唯一

第三步：

```
给定当前状态 s0：

while 任务未完成:
    1. 在 s_t 条件下，生成接下来 K 个子目标
       (K 很小，比如 2~3)
    2. 执行第一个子目标
    3. 到达新状态 s_{t+1}
    4. 检查是否需要修正高阶规划
```


```
Input: (NL task, initial state s0)

s = s0
while not task_done:
    summary = StateSummary(s)

    subgoals = HighLevelPlan(NL task, summary)
        # 只生成接下来 1~K 个

    Ti = subgoals[0]

    target_states = S(Ti)   # 由 cluster + UTG 推导

    path = PlanPath(s, target_states)

    if path not found:
        trigger replanning / revise subgoals
    else:
        execute path
        s = new state
```



核心思路是分成了三层；滚动式规划：没完成一步，重新审视高层规划：决定是否要重新规划，或者保留；

现在任务：知道这个知识图谱该怎么搞，同时思考与任务迁移的联系和使用！

形式?
```
{
  "domain": "Music_Streaming",
  "nodes": [
    {"id": "S1", "label": "Search_Interface", "essential_elements": ["search_bar"]},
    {"id": "S2", "label": "Result_List", "essential_elements": ["list_item", "song_title"]}
  ],
  "edges": [
    {"from": "S1", "to": "S2", "intent": "Execute_Search", "required_input": "query"}
  ]
}
```

簇语义蒸馏 (Cluster Semantic Distillation)
跨簇连接剪枝 (Inter-cluster Link Pruning)
路径逻辑归一化 (Logical Path Normalization)
领域映射与验证 (Domain Mapping)


这一切是否建立在对UTG分簇的结果是非常理想化的？就是簇之间功能边界非常明显，簇和簇之间几乎没有重合的功能。
那么面对现实的情况：簇之间很可能有相同的功能，如在音乐软件中很多不同的界面都可以触发搜索功能，如何在TIG中体现这种相同性与不同性？有些分簇结果导致簇之间功能重合较高、区分不大，TIG能否准确地察觉出问题并进行适当的合并？



# 2025/01/12

两个方向：memory+执行；对新应用的指导；


第二个方向：对新应用的指导
模块1：Functional Prototype Library（跨应用）
模块2：Task Generator（指导性任务生成器）
模块 3：Guided Exploration Loop（指导式探索）

第一步：如何定义prototype？
⟨功能语义，前置能力条件，能力子图⟩

功能语义："Play a selected song"
前置条件（不是页面，而是“能力可达状态”）：
```
Precondition:
- A track item is visible
- Play_Song capability is available
```

能力子图（从 TIG 中截取）:
所有能完成该功能的最小能力闭包