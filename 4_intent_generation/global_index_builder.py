"""
===========================================================
Global Index Construction for Cluster-level Task Routing
===========================================================

目标
----
构建 Global Index，用于支持：
- 跨功能簇（cluster）的任务路由
- 长任务（long-horizon task）的高层规划
- 与 Local Index 协同，实现任务拼接

Global Index 的核心形式是：
    G = (V_cluster, E_transition)

其中：
    - V_cluster: 功能簇节点（带语义摘要）
    - E_transition: 簇间可达关系（带语义/操作摘要）

-----------------------------------------------------------
设计原则
--------
1. Global Index 不关心具体 GUI 操作
2. 抽象“为什么能跳过去”，而不是“点了哪里”
3. 支持多入口、多出口、不对称跳转
4. 为 Planner 提供稳定、低噪声的路由图
===========================================================
"""

from typing import List, Dict, Any, Tuple
from collections import defaultdict


class ClusterNode:
    """
    Global Index 中的一个功能簇节点
    """

    def __init__(
        self,
        cluster_id: str,
        summary: str,
        entry_states: List[str],
        exit_states: List[str]
    ):
        """
        summary:
            - 该簇的功能语义摘要
            - 例如：'Wi-Fi settings page'

        entry_states / exit_states:
            - 用于执行阶段的起点/终点对齐
        """
        self.cluster_id = cluster_id
        self.summary = summary
        self.entry_states = entry_states
        self.exit_states = exit_states

class ClusterTransition:
    """
    簇间的一条有向跳转边
    """

    def __init__(
        self,
        src_cluster: str,
        dst_cluster: str,
        trigger_summary: str,
        support_states: List[Tuple[str, str]]
    ):
        """
        trigger_summary:
            - 语义层面的跳转原因
            - 如：'click network option'

        support_states:
            - 支撑该跳转的 (src_state, dst_state)
            - 用于执行时回溯
        """
        self.src_cluster = src_cluster
        self.dst_cluster = dst_cluster
        self.trigger_summary = trigger_summary
        self.support_states = support_states

class GlobalIndex:
    """
    全局簇级路由图
    """

    def __init__(self):
        self.clusters: Dict[str, ClusterNode] = {}
        self.transitions: Dict[str, List[ClusterTransition]] = defaultdict(list)

class GlobalIndexBuilder:
    """
    从 clustered UTG 构建 Global Index
    """

    def __init__(self, utg):
        """
        utg:
            - nodes: state_id -> UIState
            - edges: (src_state, action, dst_state)
            - 每个 state 已标注 cluster_id
        """
        self.utg = utg


    def build_cluster_nodes(
        self,
        cluster_infos: Dict[str, Dict[str, Any]]
    ) -> Dict[str, ClusterNode]:
        """
        为每个 cluster 构建 ClusterNode

        cluster_infos:
            - 来自 cluster_info.json
            - 包含 entry_points / exit_points / summary
        """

        clusters = {}

        for cid, info in cluster_infos.items():
            clusters[cid] = ClusterNode(
                cluster_id=cid,
                summary=info.get("summary", ""),
                entry_states=info.get("entry_points", []),
                exit_states=info.get("exit_points", [])
            )

        return clusters
    
    def extract_cross_cluster_edges(self):
        """
        从 UTG 中提取所有跨 cluster 的边

        输出：
            Dict[(src_cluster, dst_cluster)] -> List[(src_state, action, dst_state)]
        """

        cross_edges = defaultdict(list)

        # TODO:
        # 遍历 utg.edges
        # 如果 src.cluster_id != dst.cluster_id
        #   收集该边作为跨簇候选

        return cross_edges

    def summarize_transition(
        self,
        edges: List[Tuple[str, Any, str]]
    ) -> str:
        """
        将一组跨簇边抽象为一个跳转语义

        设计思路：
        - 多条边往往语义等价（如多个按钮都能进入子页）
        - 抽象成稳定、可泛化的触发描述
        """

        # TODO:
        # 1. 利用 action target 的 text / resource-id
        # 2. 利用 src_state 的 semantic
        # 3. 可调用 LLM 进行摘要

        return "placeholder_transition"
    

    def build_transitions(
        self,
        cross_edges
    ) -> Dict[str, List[ClusterTransition]]:
        """
        将跨簇边构建为 Global Index 中的跳转关系
        """

        transitions = defaultdict(list)

        for (src_c, dst_c), edges in cross_edges.items():
            summary = self.summarize_transition(edges)

            transitions[src_c].append(
                ClusterTransition(
                    src_cluster=src_c,
                    dst_cluster=dst_c,
                    trigger_summary=summary,
                    support_states=[(e[0], e[2]) for e in edges]
                )
            )

        return transitions
    
    def build(
        self,
        cluster_infos: Dict[str, Dict[str, Any]]
    ) -> GlobalIndex:
        """
        主流程：
            clustered UTG
                ↓
            cluster nodes
                ↓
            cross-cluster edges
                ↓
            transition abstraction
                ↓
            Global Index
        """

        global_index = GlobalIndex()

        global_index.clusters = self.build_cluster_nodes(cluster_infos)

        cross_edges = self.extract_cross_cluster_edges()
        global_index.transitions = self.build_transitions(cross_edges)

        return global_index



