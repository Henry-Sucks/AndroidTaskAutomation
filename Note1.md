2025/11/11
来到了核心问题：怎样定义簇，以及簇内任务/簇间任务可以满足我的想法要求-》也是创新点之一！
要求：
任务的定义足够原子化，导致能够将任务分解成相应子任务-》什么形式，如何定义？
任务的定义足够抽象化，能够适应不同的UI变化-》如何定义任务的抽象化形式？
我需要聚类的原因是什么？
我是否只需要对多个格式相同的页面合并成一个抽象页面，这个页面包含了动态变化下可以触发的所有UI元素，这样定义任务时我可以以这样的形式：[抽象页面，元素，动作，执行功能]
这样是否能够完成子任务（抽象页面）之间的导航？
从审美上看似乎利用几何法比较合适
任务的颗粒度是可互动的元素与动作（element）？前置条件是什么？

2025/11/15
结合截图，看看效果！

2025/11/17
并不好，似乎永远无法调整到预期的状态？
怎么决定分簇的结果是好还是不好？分簇的效果不好！



新目标：找一找现有的、能够根据探索内容生成sub-task的工具，跑一跑效果？
注意：还没有解决的问题：ape_output.log的日志编码问题


2025/11/18
现在的困境：
1. 我怎样评判我的分簇结果？一个功能整合得比较集中、规模小的应用，是不是看不出分簇的效果？是不是只能在比较大型的上面去分簇？
2. 我怎样设计一个好的motivation？
KG-RAG举了一个好例子：番茄小说的隐私权政策藏得非常隐秘，需要在主页点击“我的”，然后点击右上角“更多”，然后点击“关于番茄”，然后点击“隐私政策与简明版”，才能打开。这在先前使用“逐步判断”的做法是难以做到的，因为大模型无法根据当前界面的语义信息去判断“隐私政策”这个任务的存在，需要有一个外部知识库去辅助判断。
因此，其做法是利用大模型总结每一个页面得到这个页面能够完成任务，然后利用RAG看看哪个任务最能够匹配任务的需求，然后利用导航机制，直接导航到这个页面并执行任务。
我针对其提出的问题是：其对任务的总结是完全依靠大模型的总结能力，那么一定能对用户任务匹配吗？用户任务如果需要拆解成子任务，那么以上的做法是否还适用？
我希望提出一个新方法：我首先将UTG分簇，然后在簇内的语境下总结每一个页面的功能/完成的任务，这样能否得到更细颗粒度的任务定义，是不是更有助于规划？
根据我的想法，我能否想到一个好的motivation？KG-RAG做不到，但我能做到的？

原先仅仅是通过页面去总结任务，没有更多的信息

有逻辑链的motivation：
任务类型,具体案例,歧义陷阱
客服入口歧义,“联系刚买的这家店的客服”,陷阱： 首页的“平台客服” vs 订单页的“商家客服”。图标一样，功能完全不同。
搜索范围歧义,“在我的收藏里搜索‘耳机’”,陷阱： 首页的“全局搜索” vs 收藏夹内的“局部搜索”。KG-RAG 容易调起全局搜索框。
支付方式管理,“删除这个自动续费服务的绑定卡”,陷阱： “钱包 -> 银行卡管理”（全局解绑） vs “订阅管理 -> 具体服务”（单项解绑）。
隐私权限设置,“关闭相册对微信的访问权限”,陷阱： APP内部的“隐私设置”（仅控制朋友圈可见性） vs 手机系统的“应用权限设置”。

下一步该做什么？


2025/11/20
我需要做三个事情：
1. 完成工具架构设计
2. 跑工具对比试验
3. 思考开题报告的三个创新点



我现在需要实现利用视觉大模型对prompt进行总结的功能：
针对每个cluster，我有以下信息：
cluster_info.json:
```
{
  "clusters": {
    "cluster_id": {
      "size": int,                           # 聚类大小
      "nodes": [node_id, ...],              # 节点列表
      "edges_inside_cluster": [...],        # 聚类内边
      "edges_from_other_clusters": [...],   # 来自其他聚类的边
      "edges_to_other_clusters": [...],     # 到其他聚类的边
      "entry_points": [node_id, ...],       # 入口点
      "exit_points": [node_id, ...],        # 出口点
      "center_point": [node_id]             # 中心点
    }
  }
}
```
而对于每个node_id，我有以下信息：
utg_clustered.js
```
var nodes = [
  {"id": "c4ffeafab883", "step": 1, "activity": "org.wikipedia.page.PageActivity", "image": "s0001.png", "xml": "s0001.xml", "cluster_id": "132", "cluster_color": "#65ded5"},
```
对于视觉大模型的调用，我有以下vlm_client.py：
```python
import os
from openai import OpenAI

class VLMClient:
    def __init__(self, api_key=None, base_url=None, model="qwen3-vl-flash"):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.model = model
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def run(self, prompt, image_url=None, enable_thinking=False, thinking_budget=81920):
        messages = []

        # 如果包含图片
        if image_url:
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    },
                    {"type": "text", "text": prompt},
                ],
            })
        else:
            messages.append({"role": "user", "content": prompt})

        # 发送请求
        extra_body = {}
        if enable_thinking:
            extra_body = {
                "enable_thinking": True,
                "thinking_budget": thinking_budget
            }

        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=False,
            extra_body=extra_body,
        )

        # 兼容 enable_thinking 的输出
        reply = completion.choices[0].message

        result = {
            "content": reply.get("content", ""),
            "reasoning": reply.get("reasoning_content", "") if enable_thinking else None
        }

        return result


# 示例用法
if __name__ == "__main__":
    client = VLMClient()
    output = client.run(
        prompt="Analyze this screenshot.",
        image_url="https://example.com/test.png",
        enable_thinking=True
    )
    print("=== Output ===")
    print(output["content"])
    if output["reasoning"]:
        print("\n=== Reasoning ===")
        print(output["reasoning"])
```python

我需要做的是：
1. 读取cluster_info.json，针对每个cluster，获取其entry_points, exit_points, center_point，以及随机获取的几个node
2. 针对每个point，读取对应的node信息，获取其image的路径
3. 利用视觉大模型（如qwen-vl）对image进行描述，得到文本描述

2025/11/22
目标：完成对cluster的总结功能
现在我要干什么？


我利用Lourain算法将自动化探索工具探索某一安卓APP后得到的UTG（UI State Transition Graph），得到了一系列“簇”。我将簇中重要的节点（入点、出点、中心点）加上随机的一些点抽取出来，利用vlm总结其截图，其结果如上json所示。
我如何根据该json结果，总结出该簇的功能描述？请给我Python代码。以上json对象的为results。


2025/11/24
需要完成的函数：
get_node_desc，得到每个state的描述
get_edges？
get_edge_desc_new：得到每个边的描述
convert_graph





```
"edges": [
        {
            "events": [
                {
                    "actionId": "FF2CF59CF320C04D71EC81E128F8DBE2",
                    "eventName": "",
                    "from": "F8DD28A0553FA28CA3DC8DAD96E34EBB",
                    "to": "82F56A3FA9E1CB4BF5AB136F6C0BA7D1"
                },
                {
                    "actionId": "F7DFE2581E8DCA87061BCB61590325DE",
                    "eventName": "",
                    "from": "F8DD28A0553FA28CA3DC8DAD96E34EBB",
                    "to": "82F56A3FA9E1CB4BF5AB136F6C0BA7D1"
                }
            ],
            "from": "E01118D4F7581B7CBD1F3F29379330D9",
            "id": "E01118D4F7581B7CBD1F3F29379330D9#AB5F374865149EE1C08AC62E50FC7DEB",
            "label": "",
            "to": "AB5F374865149EE1C08AC62E50FC7DEB"
        },
        ....
    ]
"nodes": {
        "0102B1C11D0634BA3C8357270B648860": {
            "exactScenes": [
                {
                    "exactSceneId": "A1C5F507783DEBFC9DA68759B6C2EAD4",
                    "exactSceneVersion": [
                        "10.35.0"
                    ],
                    "home": 0,
                    "img": "A1C5F507783DEBFC9DA68759B6C2EAD4.jpeg",
                    "layout": "A1C5F507783DEBFC9DA68759B6C2EAD4.xml",
                    "level": 30002,
                    "sceneActionList": [],
                    "sceneId": "0102B1C11D0634BA3C8357270B648860",
                    "screenSize": "1080x2340",
                    "uiLabelScore": "0.0",
                    "uri": "com.tencent.qqmusic/.activity.base.FragmentActivityWithMinibar",
                    "widgetBlockList": {},
                    "widgetList": {
                        "A1C5F507783DEBFC9DA68759B6C2EAD4#06342C3E25C0012DF1967B26AF0CE06D": {
                            "actions": [
                                "CLICK"
                            ],
                            "bounds": "[60,2076][1020,2224]",
                            "isMarked": false,
                            "isNew": true,
                            "isWidget": false,
                            "text": "歌曲队列^^Worlds Collide (inspired by Arcane League of Legends) - JVKE^^播放",
                            "type": "android.view.ViewGroup",
                            "widgetBlockId": "/android.widget.FrameLayout/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.RelativeLayout/android.view.ViewGroup[1]",
                            "xpath": "/android.widget.FrameLayout/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.RelativeLayout/android.view.ViewGroup[1]/android.widget.FrameLayout[1]/android.view.ViewGroup/android.widget.FrameLayout/android.widget.FrameLayout/android.view.ViewGroup"
                        },
                        ...
                    }
                }
            ],
            "sceneVersions": [
                "10.35.0"
            ]
        },
        ...
    }
```



# 2025/11/25
现在已经有的：分好簇的utg，每簇都有入点、出点、中心点
我需要做的是：
cluster_summary：对每个簇进行总结
node_desc：对每个节点进行描述 + 簇总结的内容
edge_desc：对每个边进行描述 + 簇总结的内容
分为两种边：簇内部的边和簇外部的边


KG-RAG的做法：
intent_summary: 对intent进行总结：两个颗粒度：在当前页面、以及从应用层面的
生成什么？：Intent-页内操作
然后再通过算法得到：Intent-从开始页出发的操作序列（原先的start_node定义有猫腻！似乎是人给出的？）

我要做的：
intent_summary：总结在当前页面、在簇颗粒度下的总结
生成什么？：Intent-页内操作
然后：生成从簇的起点到该intent的操作序列    -》 簇内任务

簇间任务呢？我提取出跨簇的edge，进行总结

然后呢，得到的东西怎么进行RAG？输入：当前页面的信息（截图/XML）、用户任务（user intention）
第一步：
LLM 任务拆解器
输入： 用户复杂指令（User Instruction）。
辅助输入（可选但推荐）： 所有簇的功能摘要列表（Global-Index 的 Keys）。把这些作为“可选工具”喂给 LLM，让拆解出的子任务更“接地气”。
输出： 一个子任务列表 [Sub_Task_1, Sub_Task_2, ...]

第二步：路由与序列生成
Input: Current_Sub_Task， Current_State
1. 定位：识别当前属于哪个cluster id
2. 双流决策：判断当前Current_Sub_Task的语义是属于当前簇还是其他簇
3. 序列检索：
分支A：簇内命中（Local hit）
    Query：在Local_index中检索
    Output：获取一条完整的簇内操作轨迹
分支B：跨簇路由（Global Routing）
    Query: 在 Global_Index 中检索目标簇 ID。
    Pathfinding: 查找从 Current_Cluster 到 Target_Cluster 的路径。
    Output: 获取一条完整的跳转轨迹 (Transition Trajectory)。
4. 起点对齐？
检索出的轨迹通常有一个预设的 Start_Node（例如簇的入口）。
Check: 当前页面是否匹配轨迹的 Start_Node？
Action: 如果不匹配，先在序列头部插入一段“归位（Reset/Navigate）”动作，确保 Agent 走到起跑线上。





