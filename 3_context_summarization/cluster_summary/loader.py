import json
import os
import re

class ClusterDataLoader:
    def __init__(self, cluster_info_path, utg_clustered_path, image_root):
        self.cluster_info = self._load_json(cluster_info_path)
        self.nodes = self._load_nodes(utg_clustered_path)
        self.node_map = {n["id"]: n for n in self.nodes}

        self.image_root = image_root

    def _load_json(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
        

    # def _load_nodes(self, path):
    #     """
    #     utg_clustered.js 内容如下：
    #     var nodes = [ ... ]
    #     所以需要去掉前缀再做 json.loads
    #     """
    #     raw = open(path, "r", encoding="utf-8").read()
    #     raw = raw.replace("var nodes = ", "").strip().rstrip(";")
    #     return json.loads(raw)

    def _load_nodes(self, path):
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        
        # 尝试直接解析（如果是纯JSON）
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        
        # 如果是JavaScript文件，提取nodes数组
        # 匹配 patterns like: var nodes = [...]; or nodes = [...];
        nodes_match = re.search(r'nodes\s*=\s*(\[.*?\]);', raw, re.DOTALL)
        if nodes_match:
            nodes_text = nodes_match.group(1)
            try:
                return json.loads(nodes_text)
            except json.JSONDecodeError:
                # 可能需要进一步清理JavaScript格式
                pass
    
        # 如果以上都失败，尝试更复杂的JavaScript到JSON转换
        return self._parse_js_array(raw, 'nodes')

    def _parse_js_array(self, js_text, array_name):
        """从JavaScript文件中提取指定的数组"""
        # 匹配数组内容
        pattern = rf'{array_name}\s*=\s*(\[.*?\]);'
        match = re.search(pattern, js_text, re.DOTALL)
        
        if not match:
            raise ValueError(f"在文件中找不到 {array_name} 数组")
        
        array_text = match.group(1)
        
        # 清理JavaScript格式（移除尾随逗号等）
        array_text = re.sub(r',\s*\]', ']', array_text)  # 移除尾随逗号
        array_text = re.sub(r',\s*}', '}', array_text)   # 对象内的尾随逗号
        
        # 转换单引号为双引号（但要注意字符串内的单引号）
        array_text = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", r'"\1"', array_text)
        
        try:
            return json.loads(array_text)
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            print(f"错误位置附近的内容: {array_text[max(0, e.pos-50):e.pos+50]}")
            raise
    

    def get_cluster_ids(self):
        return list(self.cluster_info["clusters"].keys())

    def get_cluster(self, cluster_id):
        return self.cluster_info["clusters"][cluster_id]

    def get_node(self, node_id):
        return self.node_map.get(node_id, None)
    
    def node_to_image_path(self, node_info):
        filename = node_info["image"]
        path = os.path.join(self.image_root, filename)
        print(path)
        return path if os.path.exists(path) else None