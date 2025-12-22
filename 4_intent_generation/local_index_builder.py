# local_index_builder.py
"""
构建簇内 Local Index 的框架
每个簇内的原子任务（atomic task）包含：
- intent: 原子任务的自然语言描述
- action_sequence: 执行动作序列
- preconditions: 执行前状态要求
- postconditions: 执行后状态
- bfs_paths: 从簇入点到该节点的备选路径
"""

import json
import os
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image, ImageDraw
from clients.vlm_client import VLMClient

class LocalIndexBuilder:
    def __init__(self, utg_folder_path):
        # 保存utg文件夹路径
        self.utg_folder_path = utg_folder_path
        
        # 构建文件路径
        cluster_info_path = os.path.join(utg_folder_path, "cluster_info.json")
        utg_path = os.path.join(utg_folder_path, "utg_clustered.js")
        
        # 加载簇信息
        self.cluster_info = self._load_cluster_info(cluster_info_path)
        # 建立节点到簇的映射
        self.node_to_cluster = self._build_node_to_cluster_map(self.cluster_info)
        # 加载节点信息
        self.nodes = self._load_nodes(utg_path)
        # 加载边信息
        self.edges = self._load_edges(utg_path)
        # 为边添加簇信息
        self._annotate_edges_with_cluster()
        
        # 初始化VLM客户端
        self.vlm_client = VLMClient()
        
        # 用于存储每个簇的 local index
        self.local_index = {}

    def _load_json(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _load_cluster_info(self, path):
        """加载 cluster_info.json"""
        return self._load_json(path)
    
    def _build_node_to_cluster_map(self, cluster_info):
        """从 cluster_info.json 构建 node_id → cluster_id 的映射"""
        mapping = {}
        clusters = cluster_info.get("clusters", {})
        for cid, c in clusters.items():
            for nid in c.get("nodes", []):
                mapping[nid] = str(cid)
        return mapping
    
    def _read_utg_js(self, path):
        """读取 UTG JavaScript 文件"""
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _extract_js_array_for_var(self, js_text, var_name):
        """提取 JavaScript 变量数组内容"""
        import re
        pattern = rf"var\s+{var_name}\s*=\s*\[([\s\S]*?)\];"
        m = re.search(pattern, js_text)
        if not m:
            return ""
        return m.group(1)
    
    def _iter_object_blocks(self, array_inner_text):
        """解析 JavaScript 对象块"""
        blocks = []
        depth = 0
        start = -1
        in_string = False
        string_quote = ''
        escape = False
        
        for i, ch in enumerate(array_inner_text):
            if in_string:
                if escape:
                    escape = False
                elif ch == '\\':
                    escape = True
                elif ch == string_quote:
                    in_string = False
            else:
                if ch in ('"', "'"):
                    in_string = True
                    string_quote = ch
                elif ch == '{':
                    if depth == 0:
                        start = i
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0 and start != -1:
                        blocks.append(array_inner_text[start:i+1])
                        start = -1
        return blocks
    
    def _js_object_to_json(self, obj_text):
        """将 JS 风格对象转换为 JSON"""
        import re
        s = obj_text
        # 去除尾随逗号
        s = re.sub(r',\s*}', '}', s)
        s = re.sub(r',\s*]', ']', s)
        # 为键添加引号
        s = re.sub(r'([,{]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', s)
        return s
    
    def _load_nodes(self, utg_js_path):
        """从 utg_clustered.js 中解析节点"""
        js_text = self._read_utg_js(utg_js_path)
        inner = self._extract_js_array_for_var(js_text, 'nodes')
        nodes = {}
        
        for block in self._iter_object_blocks(inner):
            json_text = self._js_object_to_json(block)
            try:
                obj = json.loads(json_text)
                nid = obj.get('id')
                if nid:
                    nodes[nid] = obj
            except Exception:
                # 兜底解析
                nid = None
                for line in block.splitlines():
                    line = line.strip()
                    if line.startswith('id:'):
                        nid = line.split(':', 1)[1].strip().strip(',').strip('"\'')
                if nid:
                    nodes[nid] = {"id": nid}
        return nodes
    
    def _load_edges(self, utg_js_path):
        """从 utg_clustered.js 中解析边"""
        js_text = self._read_utg_js(utg_js_path)
        inner = self._extract_js_array_for_var(js_text, 'edges')
        edges = []
        
        for block in self._iter_object_blocks(inner):
            json_text = self._js_object_to_json(block)
            try:
                obj = json.loads(json_text)
            except Exception:
                # 兜底解析
                obj = {}
                for line in block.splitlines():
                    line = line.strip()
                    if ':' not in line:
                        continue
                    k, v = line.split(':', 1)
                    k = k.strip()
                    v = v.strip().rstrip(',')
                    if v.startswith('"') or v.startswith("'"):
                        v = v.strip('"\'')
                        obj[k] = v
                    else:
                        try:
                            obj[k] = json.loads(v)
                        except Exception:
                            obj[k] = v
            
            # 构建边对象
            edge = {
                'id': obj.get('id'),
                'from': obj.get('from'),
                'to': obj.get('to'),
                'hash_id': obj.get('hash_id') or obj.get('hashId'),
                'bounds': obj.get('bounds', ''),
                'xpath': obj.get('xpath', ''),
                'actions': obj.get('actions', []),
                'text': obj.get('text', ''),
                'type': obj.get('type', ''),
                'action_types': obj.get('action_types', [])
            }
            edges.append(edge)
        return edges
    
    def _annotate_edges_with_cluster(self):
        """为边添加簇信息"""
        for e in self.edges:
            from_id = e.get('from')
            to_id = e.get('to')
            e['from_cluster'] = self.node_to_cluster.get(from_id)
            e['to_cluster'] = self.node_to_cluster.get(to_id)

    def get_edges_in_cluster(self, cluster_id):
        """
        获取簇内边
        """
        return [e for e in self.edges if e["from_cluster"] == cluster_id and e["to_cluster"] == cluster_id]

    def get_outgoing_edges(self, node_id, edges):
        """
        获取从指定节点出发的簇内边
        """
        return [e for e in edges if e["from"] == node_id]
    
    def build_local_index(self):
        """
        主入口：为每个簇构建 Local Index
        """
        for cluster_id, cluster in self.cluster_info["clusters"].items():
            # print(f"Processing cluster {cluster_id}...")
            # 可以选择只处理特定簇进行测试
            # if cluster_id == "95":  # 取消注释以只处理特定簇
                # 1. 获取簇内节点和边
                cluster_nodes = cluster["nodes"]
                cluster_edges = self.get_edges_in_cluster(cluster_id)
                
                # 2. 遍历簇内节点，生成原子任务（并行处理）
                task_params = []
                for node_id in cluster_nodes:
                    node_info = self.nodes[node_id]
                    # 获取从该节点出发的边（簇内）
                    outgoing_edges = self.get_outgoing_edges(node_id, cluster_edges)
                    for edge in outgoing_edges:
                        task_params.append((node_info, edge, cluster))
                
                # 使用线程池并行生成原子任务
                atomic_tasks = []
                with ThreadPoolExecutor(max_workers=4) as executor:
                    future_to_params = {executor.submit(self.generate_atomic_task, *params): params for params in task_params}
                    for future in as_completed(future_to_params):
                        try:
                            atomic_task = future.result()
                            atomic_tasks.append(atomic_task)
                        except Exception as e:
                            print(f"Error generating atomic task: {e}")
                
                # 3. 将生成的 atomic tasks 存入 Local Index
                self.local_index[cluster_id] = atomic_tasks

        return self.local_index

    def generate_atomic_task(self, node_info, edge_info, cluster):
        """
        生成一个原子任务
        """
        # 1. 使用统一VLM分析生成 intent, preconditions, postconditions
        vlm_analysis = self.analyze_task_with_vlm(node_info, edge_info, cluster)
        intent = vlm_analysis.get('intent', 'Navigate in the app')
        preconditions = vlm_analysis.get('preconditions', [])
        postconditions = vlm_analysis.get('postconditions', [])
        
        # 2. action_sequence: 基于 edge_info 构造动作序列
        action_sequence = self.build_action_sequence(edge_info)
        
        # 5. 路径信息：从簇入点到该节点的路径，以及从该节点到簇出点的路径
        bfs_paths = self.build_bfs_paths(cluster["entry_points"], node_info["id"], cluster)
        entry_paths = bfs_paths.get("entry_to_target", [])
        exit_paths = bfs_paths.get("target_to_exit", [])
        
        atomic_task = {
            "intent": intent,
            "action_sequence": action_sequence,
            "preconditions": preconditions,
            "postconditions": postconditions,
            "entry_paths": entry_paths,
            "exit_paths": exit_paths
        }
        
        return atomic_task

    # ---------------- Helper Methods ----------------

    def analyze_task_with_vlm(self, node_info, edge_info, cluster):
        """
        使用统一VLM调用生成intent、preconditions和postconditions
        在触发前状态图片上标记红框，并与触发后状态拼接后输入VLM
        """
        try:
            # 构建状态图片路径（从节点信息中获取）
            from_node_id = edge_info['from']
            to_node_id = edge_info['to']
            
            # 并行获取图片路径
            def get_image_path(node_id):
                """并行获取单个节点的图片路径"""
                node_info = self.nodes.get(node_id, {})
                image_name = node_info.get('image', '')
                if image_name:
                    image_path = os.path.join(self.utg_folder_path, "states", image_name)
                    if os.path.exists(image_path):
                        return image_path
                return None
            
            # 使用线程池并行获取两个图片路径
            with ThreadPoolExecutor(max_workers=2) as executor:
                future_from = executor.submit(get_image_path, from_node_id)
                future_to = executor.submit(get_image_path, to_node_id)
                
                from_image_path = future_from.result()
                to_image_path = future_to.result()
            
            if not from_image_path or not to_image_path:
                print("Warning: Could not find state images for VLM analysis.")
                # 如果找不到图片，使用文本描述
                action_types = edge_info.get('action_types', ['CLICK'])
                text = edge_info.get('text', '')
                element_type = edge_info.get('type', 'element')
                
                return {
                    'intent': f"Perform {action_types[0]} action on {element_type} with text '{text}' to navigate from state {from_node_id} to {to_node_id}",
                    'preconditions': [f"Currently at state {from_node_id}", "Target element is visible and interactive"],
                    'postconditions': [f"Successfully navigated to state {to_node_id}", "UI updated to new state"]
                }
            
            # 创建带红框标记的组合图片
            combined_image_path = self._create_marked_combined_image(
                from_image_path, to_image_path, edge_info
            )
            
            if not combined_image_path:
                print("Warning: Could not create combined image for VLM analysis.")
                return {
                    'intent': f"Navigate from {from_node_id} to {to_node_id}",
                    'preconditions': [f"Currently at state {from_node_id}"],
                    'postconditions': [f"Successfully navigated to state {to_node_id}"]
                }
            
            # 构建VLM prompt
            action_types = edge_info.get('action_types', ['CLICK'])
            text = edge_info.get('text', '')
            element_type = edge_info.get('type', 'element')
            
            # 获取前后状态的描述
            from_node_desc = self._get_node_description(node_info)
            to_node_info = self.nodes.get(to_node_id, {})
            to_node_desc = self._get_node_description(to_node_info)
            
            # 获取cluster摘要信息
            cluster_summary = self._get_cluster_summary(cluster)
            
            prompt = f"""Please analyze this mobile app UI interaction and provide a comprehensive task analysis.

Context:
- Action type: {action_types[0] if action_types else 'CLICK'}
- Target element type: {element_type}
- Target element text: "{text}"
- The red box in the left image shows the element being interacted with
- The right image shows the resulting state after the interaction

State Information:
- Current state (left image): {from_node_desc}
- Resulting state (right image): {to_node_desc}

Cluster Context:
- This interaction belongs to: {cluster_summary}

Please provide the following analysis in JSON format:

{{
  "intent": "A single sentence describing the user's goal or what they are trying to achieve",
  "preconditions": ["List of conditions that must be met before this action can be performed"],
  "postconditions": ["List of expected outcomes after this action is completed"]
}}

Focus on:
- Intent: User-friendly description of the goal, not technical details
- Preconditions: What state/conditions are needed for this action to be possible
- Postconditions: What changes or outcomes result from this action

Provide only the JSON object, no additional text."""
            
            # 调用VLM
            result = self.vlm_client.run(
                prompt=prompt,
                image_url=combined_image_path,
                enable_thinking=False
            )
            
            # 清理临时文件
            if os.path.exists(combined_image_path):
                os.remove(combined_image_path)
            
            # 解析VLM返回的JSON
            content = result.get('content', '').strip()
            if content:
                try:
                    # 尝试解析JSON
                    import re
                    # 提取JSON部分（去除可能的额外文本）
                    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                        parsed_result = json.loads(json_str)
                        return {
                            'intent': parsed_result.get('intent', f"Interact with {element_type} to navigate in the app"),
                            'preconditions': parsed_result.get('preconditions', [f"Currently at {from_node_desc}", "Target element is available"]),
                            'postconditions': parsed_result.get('postconditions', [f"Successfully navigated to {to_node_desc}"])
                        }
                except Exception as parse_error:
                    print(f"Failed to parse VLM JSON response: {parse_error}")
            
            # Fallback if JSON parsing fails
            return {
                'intent': f"Interact with {element_type} to navigate in the app",
                'preconditions': [f"Currently at {from_node_desc}", "Target element is visible and interactive"],
                'postconditions': [f"Successfully navigated to {to_node_desc}"]
            }
            
        except Exception as e:
            print(f"Error in unified VLM analysis: {e}")
            # fallback到简单描述
            action_type = edge_info.get('action_types', ['CLICK'])[0] if edge_info.get('action_types') else 'CLICK'
            text = edge_info.get('text', '')
            return {
                'intent': f"Perform {action_type} action on element with text '{text}'",
                'preconditions': ["Element is visible and interactive", "App is in correct state"],
                'postconditions': ["Action completed successfully", "UI updated appropriately"]
            }

    def summarize_intent(self, node_info, edge_info, cluster):
        """
        利用 VLM 生成原子任务的自然语言描述
        在触发前状态图片上标记红框，并与触发后状态拼接后输入VLM
        """
        try:
            # 构建状态图片路径（从节点信息中获取）
            from_node_id = edge_info['from']
            to_node_id = edge_info['to']
            
            # 从节点信息中获取图片路径
            from_image_path = None
            to_image_path = None
            
            # 获取from节点的图片路径
            from_node_info = self.nodes.get(from_node_id, {})
            from_image_name = from_node_info.get('image', '')
            if from_image_name:
                # 图片在states目录下
                from_image_path = os.path.join(self.utg_folder_path, "states", from_image_name)
                if not os.path.exists(from_image_path):
                    from_image_path = None
            
            # 获取to节点的图片路径
            to_node_info = self.nodes.get(to_node_id, {})
            to_image_name = to_node_info.get('image', '')
            if to_image_name:
                # 图片在states目录下
                to_image_path = os.path.join(self.utg_folder_path, "states", to_image_name)
                if not os.path.exists(to_image_path):
                    to_image_path = None
            
            if not from_image_path or not to_image_path:
                # 如果找不到图片，使用文本描述
                action_types = edge_info.get('action_types', ['CLICK'])
                text = edge_info.get('text', '')
                element_type = edge_info.get('type', 'element')
                
                return f"Perform {action_types[0]} action on {element_type} with text '{text}' to navigate from state {from_node_id} to {to_node_id}"
            
            # 创建带红框标记的组合图片
            combined_image_path = self._create_marked_combined_image(
                from_image_path, to_image_path, edge_info
            )
            
            if not combined_image_path:
                return f"Navigate from {from_node_id} to {to_node_id}"
            
            # 构建VLM prompt
            action_types = edge_info.get('action_types', ['CLICK'])
            text = edge_info.get('text', '')
            element_type = edge_info.get('type', 'element')
            
            # 获取前后状态的描述
            from_node_desc = self._get_node_description(node_info)
            to_node_info = self.nodes.get(to_node_id, {})
            to_node_desc = self._get_node_description(to_node_info)
            
            # 获取cluster摘要信息
            cluster_summary = self._get_cluster_summary(cluster)
            
            prompt = f"""Please analyze this mobile app UI interaction and generate a concise intent description.

Context:
- Action type: {action_types[0] if action_types else 'CLICK'}
- Target element type: {element_type}
- Target element text: "{text}"
- The red box in the left image shows the element being interacted with
- The right image shows the resulting state after the interaction

State Information:
- Current state (left image): {from_node_desc}
- Resulting state (right image): {to_node_desc}

Cluster Context:
- This interaction belongs to: {cluster_summary}

Please provide a natural language description of what this interaction accomplishes, focusing on the user intent rather than technical details. Consider the state transition and cluster context to understand the broader user goal. Keep it concise and user-friendly.

Format your response as a single sentence describing the user's goal or what they are trying to achieve."""
            
            # 调用VLM
            result = self.vlm_client.run(
                prompt=prompt,
                image_url=combined_image_path,
                enable_thinking=False
            )
            
            # 清理临时文件
            if os.path.exists(combined_image_path):
                os.remove(combined_image_path)
            
            return result.get('content', '').strip() or f"Interact with {element_type} to navigate in the app"
            
        except Exception as e:
            print(f"Error generating intent with VLM: {e}")
            # fallback到简单描述
            action_type = edge_info.get('action_types', ['CLICK'])[0] if edge_info.get('action_types') else 'CLICK'
            text = edge_info.get('text', '')
            return f"Perform {action_type} action on element with text '{text}'"
    
    def _parse_bounds(self, bounds_str):
        """
        解析bounds字符串，支持多种格式
        例如: "[696,654][864,744]" -> (696, 654, 864, 744)
        """
        if not bounds_str:
            return None
        
        try:
            # 处理 "[x1,y1][x2,y2]" 格式
            if bounds_str.startswith('[') and '][' in bounds_str:
                parts = bounds_str.replace('[', '').replace(']', '').split('][')
                if len(parts) == 2:
                    x1, y1 = map(int, parts[0].split(','))
                    x2, y2 = map(int, parts[1].split(','))
                    return (x1, y1, x2, y2)
            
            # 处理其他可能的格式
            # "x1,y1,x2,y2"
            if ',' in bounds_str and '[' not in bounds_str:
                coords = list(map(int, bounds_str.split(',')))
                if len(coords) == 4:
                    return tuple(coords)
        
        except Exception:
            pass
        
        return None
    
    def _get_node_description(self, node_info):
        """
        提取节点描述信息，优先使用activity名称，其次使用其他可能的描述字段
        """
        if not node_info:
            return "Unknown state"
        
        # 尝试多个可能的描述字段
        desc_fields = ['activity', 'title', 'description', 'summary', 'name']
        for field in desc_fields:
            value = node_info.get(field, '')
            if value and value.strip():
                return value.strip()
        
        # 如果没有找到描述，使用节点ID
        node_id = node_info.get('id', 'unknown')
        return f"State {node_id[-8:]}"  # 使用ID的后8位简化显示
    
    def _get_cluster_summary(self, cluster):
        """
        提取cluster摘要信息，可以基于cluster的特征生成描述
        """
        if not cluster:
            return "General app functionality"
        
        # 如果cluster有summary字段直接使用
        if 'summary' in cluster:
            return cluster['summary']
        
        # 基于cluster大小和结构生成描述
        size = cluster.get('size', 0)
        entry_points = len(cluster.get('entry_points', []))
        exit_points = len(cluster.get('exit_points', []))
        
        if size == 0:
            return "Empty functionality cluster"
        elif size < 5:
            return "Small feature cluster with limited functionality"
        elif size < 20:
            return "Medium-sized feature cluster"
        elif size < 100:
            return "Large functional area with multiple related features"
        else:
            return "Major app section with extensive functionality"
    
    def _create_marked_combined_image(self, from_image_path, to_image_path, edge_info):
        """
        创建带红框标记的组合图片（前状态+后状态）
        """
        try:
            # 加载图片
            from_img = Image.open(from_image_path)
            to_img = Image.open(to_image_path)
            
            # 在from_img上画红框
            bounds = self._parse_bounds(edge_info.get('bounds', ''))
            if bounds:
                from_img_copy = from_img.copy()
                draw = ImageDraw.Draw(from_img_copy)
                x1, y1, x2, y2 = bounds
                
                # 画红框，线宽为3
                for i in range(3):
                    draw.rectangle([x1-i, y1-i, x2+i, y2+i], outline='red', width=1)
            else:
                from_img_copy = from_img.copy()
            
            # 调整图片大小以便拼接
            max_height = max(from_img_copy.height, to_img.height)
            from_img_resized = from_img_copy.resize((int(from_img_copy.width * max_height / from_img_copy.height), max_height))
            to_img_resized = to_img.resize((int(to_img.width * max_height / to_img.height), max_height))
            
            # 水平拼接图片
            combined_width = from_img_resized.width + to_img_resized.width
            combined_img = Image.new('RGB', (combined_width, max_height), 'white')
            combined_img.paste(from_img_resized, (0, 0))
            combined_img.paste(to_img_resized, (from_img_resized.width, 0))
            
            # 保存临时文件
            temp_path = f"temp_combined_{edge_info.get('hash_id', 'unknown')}.png"
            combined_img.save(temp_path)
            
            return temp_path
            
        except Exception as e:
            print(f"Error creating combined image: {e}")
            return None

    def build_action_sequence(self, edge_info):
        """
        根据边信息构造动作序列
        """
        sequence = []
        
        # 根据实际边结构构建动作序列
        element_info = {
            "xpath": edge_info.get("xpath", ""),
            "bounds": edge_info.get("bounds", ""),
            "text": edge_info.get("text", ""),
            "type": edge_info.get("type", "")
        }
        
        # 使用 action_types 或默认为 CLICK
        action_types = edge_info.get("action_types", [])
        if not action_types:
            action_types = ["CLICK"]
        
        for action_type in action_types:
            step = {
                "node_id": edge_info["from"],
                "element": element_info,
                "action_type": action_type.upper()
            }
            sequence.append(step)
        
        return sequence

    def build_preconditions(self, node_info, edge_info):
        """
        构建前置条件（现在主要作为fallback，实际使用analyze_task_with_vlm）
        - 当前节点状态
        - 可操作组件可用
        """
        return [f"当前在节点 {node_info['id']} 页面", "组件可点击/可交互"]

    def build_postconditions(self, edge_info):
        """
        构建后置条件（现在主要作为fallback，实际使用analyze_task_with_vlm）
        - 执行后到达目标节点
        """
        return [f"页面跳转到节点 {edge_info['to']}"]

    def build_bfs_paths(self, entry_points, target_node_id, cluster):
        """
        从簇入点 BFS 到目标节点的最短路径
        以及从目标节点到簇出点的最短路径
        如果有多个，则返回多条路径的数组
        用于原子任务拼接
        
        返回格式为包含边详细信息的对象数组:
        [
            {
                "from": "node_id_1",
                "to": "node_id_2",
                "possible_actions": [edge_info1, edge_info2, ...]
            },
            ...
        ]
        """
        # 获取cluster_id用于后续边查询
        cluster_id = None
        for cid, c in self.cluster_info["clusters"].items():
            if c == cluster:
                cluster_id = cid
                break
        
        if not cluster_id:
            return {"entry_to_target": [], "target_to_exit": []}
        
        cluster_edges = self.get_edges_in_cluster(cluster_id)
        
        # 辅助函数：将节点路径转换为边路径
        def convert_node_path_to_edge_path(node_path):
            """将节点路径转换为边路径格式"""
            if len(node_path) < 2:
                return []
            
            edge_path = []
            for i in range(len(node_path) - 1):
                from_node = node_path[i]
                to_node = node_path[i + 1]
                
                # 找到所有从 from_node 到 to_node 的边
                possible_edges = [
                    e for e in cluster_edges 
                    if e["from"] == from_node and e["to"] == to_node
                ]
                
                if possible_edges:
                    # 构建动作信息
                    possible_actions = []
                    for edge in possible_edges:
                        element_info = {
                            "xpath": edge.get("xpath", ""),
                            "bounds": edge.get("bounds", ""),
                            "text": edge.get("text", ""),
                            "type": edge.get("type", "")
                        }
                        
                        action_types = edge.get("action_types", [])
                        if not action_types:
                            action_types = ["CLICK"]
                        
                        for action_type in action_types:
                            action = {
                                "node_id": from_node,
                                "element": element_info,
                                "action_type": action_type.upper()
                            }
                            possible_actions.append(action)
                    
                    edge_path.append({
                        "from": from_node,
                        "to": to_node,
                        "possible_actions": possible_actions
                    })
            
            return edge_path
        
        # 1. 从簇入点到目标节点的路径
        entry_to_target_paths = []
        if entry_points and target_node_id in cluster.get("nodes", []):
            visited = set()
            queue = deque()
            
            for entry in entry_points:
                if entry == target_node_id:
                    entry_to_target_paths.append([])  # 入点即目标，路径为空
                else:
                    queue.append((entry, [entry]))
            
            while queue:
                current_node, path = queue.popleft()
                if current_node == target_node_id:
                    entry_to_target_paths.append(convert_node_path_to_edge_path(path))
                    continue
                if current_node in visited:
                    continue
                visited.add(current_node)
                
                neighbors = [e["to"] for e in self.get_outgoing_edges(current_node, cluster_edges)]
                for n in neighbors:
                    if n not in visited:
                        queue.append((n, path + [n]))
        
        # 2. 从目标节点到簇出点的路径
        target_to_exit_paths = []
        exit_points = cluster.get("exit_points", [])
        
        if exit_points and target_node_id in cluster.get("nodes", []):
            visited = set()
            queue = deque()
            
            # 检查目标节点是否就是出点
            for exit_point in exit_points:
                if target_node_id == exit_point:
                    target_to_exit_paths.append([])  # 目标即出点，路径为空
            
            # 从目标节点开始BFS到出点
            if target_node_id not in exit_points:
                queue.append((target_node_id, [target_node_id]))
                
                while queue:
                    current_node, path = queue.popleft()
                    if current_node in exit_points:
                        target_to_exit_paths.append(convert_node_path_to_edge_path(path))
                        continue
                    if current_node in visited:
                        continue
                    visited.add(current_node)
                    
                    neighbors = [e["to"] for e in self.get_outgoing_edges(current_node, cluster_edges)]
                    for n in neighbors:
                        if n not in visited:
                            queue.append((n, path + [n]))
        
        return {
            "entry_to_target": entry_to_target_paths,
            "target_to_exit": target_to_exit_paths
        }

# ---------------- Example Usage ----------------
if __name__ == "__main__":
    # 测试用例
    builder = LocalIndexBuilder(
        utg_folder_path="utg/NetEase Cloud Music"
    )
    
    print(f"Loaded {len(builder.nodes)} nodes")
    print(f"Loaded {len(builder.edges)} edges")
    print(f"Found {len(builder.cluster_info['clusters'])} clusters")
    
    # 构建本地索引
    local_index = builder.build_local_index()
    
    # 输出简要统计
    for cluster_id, tasks in local_index.items():
        print(f"Cluster {cluster_id}: {len(tasks)} atomic tasks")
    
    # 可选：保存结果到utg文件夹内
    output_path = os.path.join(builder.utg_folder_path, "local_index.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(local_index, f, indent=2, ensure_ascii=False)
    print(f"Local index saved to: {output_path}")
