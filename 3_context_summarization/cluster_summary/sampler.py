import random

class ClusterSampler:
    def __init__(self, loader, sample_size=3):
        self.loader = loader
        self.sample_size = sample_size

    def get_sample_nodes(self, cluster, selected_nodes=None):
        all_nodes = cluster["nodes"]
        
        # 如果没有传入已选节点，初始化为空集合
        if selected_nodes is None:
            selected_nodes = set()
        
        # 获取可用的节点（排除已选择的节点）
        available_nodes = [node for node in all_nodes if node not in selected_nodes]
        
        # 如果可用节点数量不足，返回所有可用节点
        sample_count = min(len(available_nodes), self.sample_size)
        
        if sample_count == 0:
            return []
        
        sampled_nodes = random.sample(available_nodes, sample_count)
        return sampled_nodes