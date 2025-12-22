from typing import List, Dict, Any
import json
import os

from clients.llm_client import LLMClient


class SubTask:
    """
    表示一个拆解后的子任务
    """
    def __init__(self, cluster_id: str, sub_task: str):
        self.cluster_id = cluster_id
        self.sub_task = sub_task
        self.actions: List[Dict[str, Any]] = []
        self.matched_intent: str = ""


class TaskPlan:
    """
    表示完整的任务规划结果
    """
    def __init__(self, original_task: str):
        self.original_task = original_task
        self.sub_tasks: List[SubTask] = []


class GlobalPlanner:
    """
    使用 Global Index + LLM
    将用户自然语言任务拆解为跨 cluster 的子任务
    """

    def __init__(self, global_index: Dict[str, Any]):
        self.global_index = global_index
        # 可以在这里缓存 cluster summary / supported intents

    def build_prompt(self, user_task: str) -> str:
        """
        构造给 LLM 的 prompt
        - 输入：用户任务 + global_index 的 summary / supported_intents
        - 输出：结构化 sub_tasks
        """
        cluster_blocks = []
        for cid, info in self.global_index.items():
            summary = info.get("summary", "")
            intents = info.get("supported_intents", [])
            cluster_blocks.append(
                f"Cluster ID: {cid}\nSummary: {summary}\nSupported Intents: {intents}"
            )

        format_instructions = (
            "You MUST reply in JSON. Do not include any extra text.\n"
            "Schema: {\"sub_tasks\": [ {\"cluster_id\": string, \"sub_task\": string} ]}"
        )

        prompt = (
            "You are a planner that decomposes a user task into sub tasks mapped to clusters.\n"
            f"User task: {user_task}\n\n"
            "Available clusters with summaries and supported intents:\n" + "\n---\n".join(cluster_blocks) + "\n\n"
            "Return the minimal ordered list of sub_tasks needed to accomplish the user task.\n"
            "Each sub_task should reference one cluster_id from above.\n"
            "Keep sub_tasks concise (one sentence).\n"
            + format_instructions
        )

        return prompt

    def parse_llm_output(self, llm_output: str) -> TaskPlan:
        """
        将 LLM 输出解析为 TaskPlan
        """
        try:
            data = json.loads(llm_output)
        except Exception:
            # 如果解析失败，返回空计划
            return TaskPlan(original_task="")

        plan = TaskPlan(original_task=data.get("original_task", ""))

        sub_tasks = data.get("sub_tasks", []) or []
        for item in sub_tasks:
            cid = item.get("cluster_id", "")
            desc = item.get("sub_task", "")
            if cid and desc:
                plan.sub_tasks.append(SubTask(cluster_id=cid, sub_task=desc))

        return plan

    def plan(self, user_task: str) -> TaskPlan:
        """
        对外接口
        """
        prompt = self.build_prompt(user_task)

        llm_client = LLMClient()
        system_prompt = (
            "You are a precise planner. Only output valid JSON. No markdown."
        )
        llm_output = llm_client.run(prompt=prompt, system_prompt=system_prompt)

        # 将用户任务填充到解析结果中
        task_plan = self.parse_llm_output(llm_output)
        if not task_plan.original_task:
            task_plan.original_task = user_task

        return task_plan


class LocalMatcher:
    """
    在指定 cluster 内，将 sub_task 匹配到具体 local intent
    并提取 action_sequence
    """

    def __init__(self, local_index: Dict[str, Any]):
        self.local_index = local_index
        # 可提前对 intent 文本做 embedding 缓存

    def encode_text(self, text: str):
        """
        将文本编码为向量（embedding）
        """
        import re

        # 简单分词：按非字母数字切分并转小写
        tokens = re.split(r"[^a-zA-Z0-9\u4e00-\u9fa5]+", text.lower())
        return {t for t in tokens if t}

    def similarity(self, vec1, vec2) -> float:
        """
        计算两个向量的相似度
        """
        if not vec1 or not vec2:
            return 0.0
        intersection = len(vec1 & vec2)
        union = len(vec1 | vec2)
        return intersection / union if union else 0.0

    def match_intent(self, cluster_id: str, sub_task: str) -> Dict[str, Any]:
        """
        在某个 cluster 内，为 sub_task 找到最匹配的 local intent
        """
        cluster_tasks = self.local_index.get(cluster_id, []) or []
        if not cluster_tasks:
            return {}

        query_vec = self.encode_text(sub_task)
        best = None
        best_score = -1.0

        for task in cluster_tasks:
            intent_text = task.get("intent", "")
            intent_vec = self.encode_text(intent_text)
            score = self.similarity(query_vec, intent_vec)
            if score > best_score:
                best_score = score
                best = task

        return best or {}

    def enrich_task_plan(self, task_plan: TaskPlan) -> TaskPlan:
        """
        为每个 SubTask 填充 actions
        """
        for sub_task in task_plan.sub_tasks:
            matched = self.match_intent(sub_task.cluster_id, sub_task.sub_task)
            if matched:
                sub_task.actions = matched.get("action_sequence", [])
                sub_task.matched_intent = matched.get("intent", "")

        return task_plan

class TaskPipeline:
    """
    从用户任务 → 子任务 → 原子 action
    """

    def __init__(self, global_index: Dict[str, Any], local_index: Dict[str, Any]):
        self.global_planner = GlobalPlanner(global_index)
        self.local_matcher = LocalMatcher(local_index)

    def run(self, user_task: str) -> Dict[str, Any]:
        """
        完整流程入口
        """
        # Step 1: 高层规划（LLM）
        # task_plan = self.global_planner.plan(user_task)

        # Step 2: 本地语义匹配（embedding）
        # task_plan = self.local_matcher.enrich_task_plan(task_plan)

        # Step 3: 序列化输出
        # return self.serialize(task_plan)
        pass

    def serialize(self, task_plan: TaskPlan) -> Dict[str, Any]:
        """
        转成你定义的 JSON 格式
        """
        # TODO:
        # 构造 dict
        pass


class StateAnalyzer:
    """
    根据 current_node_id 判断当前所处的语义位置
    """

    def __init__(self, utg, node_to_cluster):
        self.utg = utg
        self.node_to_cluster = node_to_cluster

    def analyze(self, current_node_id: str) -> Dict:
        """
        输出当前状态的语义摘要
        """
        # TODO:
        # 1. 获取 cluster_id
        # 2. 获取该 node 在 cluster 中的角色：
        #    - entry node?
        #    - center node?
        #    - edge node?
        # 3. 可选：生成 node-level summary（VLM）
        return {
            "current_node": current_node_id,
            "current_cluster": "...",
            "node_role": "entry / internal / exit"
        }


def _load_global_index(base_dir: str) -> Dict[str, Any]:
    """加载 global_index.json"""
    path = os.path.join(base_dir, "utg", "NetEase Cloud Music", "global_index.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_local_index(base_dir: str) -> Dict[str, Any]:
    """加载 local_index.json"""
    path = os.path.join(base_dir, "utg", "NetEase Cloud Music", "local_index.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _print_plan(plan: TaskPlan, global_index: Dict[str, Any] | None = None) -> None:
    """打印规划结果，便于快速查看"""
    print(f"Original task: {plan.original_task}")
    if not plan.sub_tasks:
        print("No sub_tasks generated.")
        return
    for idx, sub_task in enumerate(plan.sub_tasks, start=1):
        print(f"[{idx}] cluster_id={sub_task.cluster_id} | sub_task={sub_task.sub_task}")
        if sub_task.actions:
            print(f"    actions: {len(sub_task.actions)} steps")
            # 只展示前2个动作预览
            for a_idx, act in enumerate(sub_task.actions[:2], start=1):
                action_type = act.get("action_type", "")
                node_id = act.get("node_id", "")
                print(f"      ({a_idx}) {action_type} @ {node_id}")
        else:
            print("    actions: <empty>")

        if global_index and sub_task.cluster_id in global_index:
            info = global_index[sub_task.cluster_id]
            summary = info.get("summary", "")
            supported_intents = info.get("supported_intents", [])
            intents_str = "; ".join(supported_intents) if isinstance(supported_intents, list) else str(supported_intents)
            print(f"    summary: {summary}")
            print(f"    supported_intents: {intents_str}")


def _print_action_plan(plan: TaskPlan) -> None:
    """打印包含匹配 intent 与动作详情的计划"""
    print(f"Original task: {plan.original_task}")
    if not plan.sub_tasks:
        print("No sub_tasks generated.")
        return
    for idx, sub_task in enumerate(plan.sub_tasks, start=1):
        print(f"[{idx}] cluster_id={sub_task.cluster_id}")
        print(f"    sub_task: {sub_task.sub_task}")
        if sub_task.matched_intent:
            print(f"    matched_intent: {sub_task.matched_intent}")
        if not sub_task.actions:
            print("    actions: <empty>")
            continue
        print(f"    actions: {len(sub_task.actions)} steps")
        for a_idx, act in enumerate(sub_task.actions, start=1):
            action_type = act.get("action_type", "")
            node_id = act.get("node_id", "")
            element = act.get("element", {})
            xpath = element.get("xpath", "")
            print(f"      ({a_idx}) {action_type} @ {node_id}")
            if xpath:
                print(f"           xpath: {xpath}")


if __name__ == "__main__":
    # 简单测试：加载 global_index 后调用 GlobalPlanner
    base_dir = os.path.dirname(os.path.abspath(__file__))
    global_index = _load_global_index(base_dir)
    local_index = _load_local_index(base_dir)

    sample_user_task = "搜索“周杰伦”的歌曲并播放，然后添加到我的收藏夹。"
    planner = GlobalPlanner(global_index)
    plan = planner.plan(sample_user_task)

    _print_plan(plan, global_index)

    matcher = LocalMatcher(local_index)
    plan = matcher.enrich_task_plan(plan)

    _print_action_plan(plan)


