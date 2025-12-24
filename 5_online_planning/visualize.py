"""
可视化工具：将操作日志转化为带标注的截图序列
"""
import json
import os
import re
from typing import List, Dict, Any
from PIL import Image, ImageDraw, ImageFont


class ActionVisualizer:
    """将action序列可视化为标注的截图序列"""
    
    def __init__(self, utg_folder: str):
        """
        Args:
            utg_folder: UTG数据文件夹路径，例如 "utg/NetEase Cloud Music"
        """
        self.utg_folder = utg_folder
        self.states_folder = os.path.join(utg_folder, "states")
        
        # 加载数据
        self.local_index = self._load_json("local_index.json")
        self.utg_clustered = self._load_js("utg_clustered.js")
        # 便捷访问
        self.nodes = self.utg_clustered.get("nodes", [])
        self.edges = self.utg_clustered.get("edges", [])
        # 建立 node_id -> image 文件名映射
        self.node_image_map = {n.get("id", ""): n.get("image") for n in self.nodes}
        
    def _load_json(self, filename: str) -> Dict:
        """加载JSON文件"""
        path = os.path.join(self.utg_folder, filename)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _load_js(self, filename: str) -> Dict:
        """加载JS格式的UTG数据（支持 var nodes = [...]; var edges = [...]）"""
        def extract_js_array(src: str, var_name: str) -> str:
            # 定位到变量声明
            pattern = re.compile(rf"var\s+{re.escape(var_name)}\s*=\s*", re.MULTILINE)
            m = pattern.search(src)
            if not m:
                return ""
            i = m.end()
            # 找到第一个'['
            while i < len(src) and src[i] != '[':
                i += 1
            if i >= len(src):
                return ""
            start = i
            # 使用计数匹配对应的']'
            depth = 0
            while i < len(src):
                ch = src[i]
                if ch == '[':
                    depth += 1
                elif ch == ']':
                    depth -= 1
                    if depth == 0:
                        # 包含结束位置
                        end = i + 1
                        return src[start:end]
                i += 1
            return ""

        def js_array_to_json(array_str: str) -> List[Dict[str, Any]]:
            if not array_str:
                return []
            # 先尝试直接解析（nodes 通常是标准 JSON）
            try:
                return json.loads(array_str)
            except Exception:
                pass
            # 辅助：给未加引号的 key 补引号，并去掉尾随逗号
            s = array_str
            # 移除注释（简单处理 // ... 与 /* ... */）
            s = re.sub(r"//.*?$", "", s, flags=re.MULTILINE)
            s = re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)
            # 给未加引号的键补引号：在 { 或 , 后面出现的 key: 形式
            # 注意 Python 拼接相邻字符串的问题，使用单个原始字符串避免转义混乱
            s = re.sub(r"([\{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', s)
            # 去除对象或数组中尾随逗号
            s = re.sub(r",\s*([}\]])", r"\1", s)
            # 将单引号转双引号（尽量避免破坏内容，edges 通常是双引号，保守处理）
            # 仅替换属性值里的单引号：在冒号后、到下一个逗号/结束括号前的简单场景
            # 如仍失败，交给异常抛出
            try:
                return json.loads(s)
            except Exception as e:
                raise ValueError(f"无法解析JS数组为JSON: {e}")

        path = os.path.join(self.utg_folder, filename)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        nodes_str = extract_js_array(content, "nodes")
        edges_str = extract_js_array(content, "edges")

        nodes = js_array_to_json(nodes_str)
        edges = js_array_to_json(edges_str)

        return {"nodes": nodes, "edges": edges}
    
    def find_action_sequence(self, cluster_id: str, matched_intent: str) -> List[Dict[str, Any]]:
        """
        根据cluster_id和matched_intent找到对应的action_sequence
        
        Args:
            cluster_id: 簇ID
            matched_intent: 匹配的意图描述
            
        Returns:
            action_sequence列表
        """
        cluster_tasks = self.local_index.get(cluster_id, [])
        
        # 找到匹配的任务
        for task in cluster_tasks:
            if task.get("intent", "") == matched_intent:
                return task.get("action_sequence", [])
        
        return []
    
    def find_edge_by_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据action信息在UTG中找到对应的edge
        
        Args:
            action: 包含node_id, element, action_type的动作信息
            
        Returns:
            edge字典，包含from, to, bboxes等信息
        """
        node_id = action.get("node_id", "")
        element = action.get("element", {})
        bounds = element.get("bounds", "")
        action_type = action.get("action_type", "")
        
        # 在UTG的edges中查找
        edges = self.edges
        # 归一化动作类型匹配（同时兼容 actions 与 action_types，并做大小写忽略）
        action_norm = (action_type or "").strip().lower()
        
        for edge in edges:
            if edge.get("from") == node_id:
                # 检查bounds是否匹配
                if edge.get("bounds") == bounds:
                    # 动作类型匹配：优先 actions（一般为大写），其次 action_types（一般为小写）
                    edge_actions_upper = [str(a).strip().lower() for a in edge.get("actions", [])]
                    edge_action_types = [str(a).strip().lower() for a in edge.get("action_types", [])]
                    if not edge_actions_upper and not edge_action_types:
                        return edge
                    if action_norm in edge_actions_upper or action_norm in edge_action_types:
                        return edge
        
        return {}
    
    def parse_bounds(self, bounds_str: str) -> tuple:
        """
        解析bounds字符串，格式如 "[0,84][1080,297]"
        
        Returns:
            (x1, y1, x2, y2)
        """
        if not bounds_str:
            return (0, 0, 0, 0)
        
        import re
        matches = re.findall(r'\[(\d+),(\d+)\]', bounds_str)
        if len(matches) >= 2:
            x1, y1 = int(matches[0][0]), int(matches[0][1])
            x2, y2 = int(matches[1][0]), int(matches[1][1])
            return (x1, y1, x2, y2)
        
        return (0, 0, 0, 0)
    
    def annotate_screenshot(self, screenshot_path: str, bounds: str, action_type: str) -> Image:
        """
        在截图上标注触发组件（红框+文字）
        
        Args:
            screenshot_path: 截图路径
            bounds: 组件边界
            action_type: 动作类型
            
        Returns:
            标注后的PIL Image对象
        """
        # 加载截图
        img = Image.open(screenshot_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        
        # 解析bounds
        x1, y1, x2, y2 = self.parse_bounds(bounds)
        
        # 绘制红框
        if x1 > 0 or y1 > 0 or x2 > 0 or y2 > 0:
            draw.rectangle([x1, y1, x2, y2], outline="red", width=5)
            
            # 添加动作类型文字
            try:
                # 尝试加载中文字体
                font = ImageFont.truetype("msyh.ttc", 40)  # 微软雅黑
            except:
                # 如果加载失败，使用默认字体
                font = ImageFont.load_default()
            
            # 在红框上方绘制文字背景
            text_bbox = draw.textbbox((x1, y1 - 50), action_type, font=font)
            draw.rectangle(text_bbox, fill="red")
            draw.text((x1, y1 - 50), action_type, fill="white", font=font)
        
        return img
    
    def create_step_image(self, action: Dict[str, Any], edge: Dict[str, Any], 
                          step_num: int, total_steps: int) -> Image:
        """
        创建单步操作的图片（from页面 -> to页面，带标注）
        
        Args:
            action: 动作信息
            edge: 边信息
            step_num: 当前步骤号
            total_steps: 总步骤数
            
        Returns:
            拼接后的PIL Image对象
        """
        from_node = edge.get("from", "")
        to_node = edge.get("to", "")
        bounds = action.get("element", {}).get("bounds", "")
        action_type = action.get("action_type", "")
        
        # 解析图片文件名（优先使用 nodes 中的 image 字段）
        from_image_file = self.node_image_map.get(from_node) or f"{from_node}.jpeg"
        to_image_file = self.node_image_map.get(to_node) or f"{to_node}.jpeg"
        from_screenshot = os.path.join(self.states_folder, from_image_file)
        to_screenshot = os.path.join(self.states_folder, to_image_file)
        
        if not os.path.exists(from_screenshot) or not os.path.exists(to_screenshot):
            print(f"警告: 截图不存在 {from_node} 或 {to_node}")
            return None
        
        # 标注from页面
        from_img = self.annotate_screenshot(from_screenshot, bounds, action_type)
        to_img = Image.open(to_screenshot).convert("RGB")
        
        # 水平拼接
        width = from_img.width + to_img.width + 20  # 加间隔
        height = max(from_img.height, to_img.height) + 80  # 加顶部说明空间
        
        combined = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(combined)
        
        # 添加步骤说明
        try:
            font = ImageFont.truetype("msyh.ttc", 36)
        except:
            font = ImageFont.load_default()
        
        step_text = f"步骤 {step_num}/{total_steps}: {action_type}"
        draw.text((10, 10), step_text, fill="black", font=font)
        
        # 粘贴图片
        combined.paste(from_img, (0, 80))
        combined.paste(to_img, (from_img.width + 20, 80))
        
        # 添加箭头
        arrow_x = from_img.width + 10
        arrow_y = height // 2
        draw.text((arrow_x - 20, arrow_y), "→", fill="red", font=font)
        
        return combined
    
    def visualize_actions(self, cluster_id: str, matched_intent: str, 
                         output_path: str = "action_visualization.png") -> bool:
        """
        将完整的action序列可视化为长图
        
        Args:
            cluster_id: 簇ID
            matched_intent: 匹配的意图
            output_path: 输出图片路径
            
        Returns:
            是否成功
        """
        # 1. 获取action_sequence
        actions = self.find_action_sequence(cluster_id, matched_intent)
        
        if not actions:
            print(f"未找到匹配的action序列: cluster_id={cluster_id}, intent={matched_intent}")
            return False
        
        print(f"找到 {len(actions)} 个动作步骤")
        
        # 2. 为每个action创建图片
        step_images = []
        for i, action in enumerate(actions, 1):
            edge = self.find_edge_by_action(action)
            if not edge:
                print(f"警告: 未找到对应的edge，跳过步骤 {i}")
                continue
            
            img = self.create_step_image(action, edge, i, len(actions))
            if img:
                step_images.append(img)
        
        if not step_images:
            print("没有成功创建任何步骤图片")
            return False
        
        # 3. 纵向拼接所有步骤
        total_width = max(img.width for img in step_images)
        total_height = sum(img.height for img in step_images) + (len(step_images) - 1) * 20  # 加间隔
        
        final_image = Image.new("RGB", (total_width, total_height), "white")
        
        y_offset = 0
        for img in step_images:
            final_image.paste(img, (0, y_offset))
            y_offset += img.height + 20  # 间隔
        
        # 4. 保存
        # 直接保存到调用方指定路径（不要再拼接 utg_folder）
        final_image.save(output_path)
        print(f"可视化结果已保存到: {output_path}")
        
        return True


def parse_action_log(log_text: str) -> List[Dict[str, Any]]:
    """
    解析文本格式的action日志
    
    Args:
        log_text: 文本格式的日志
        
    Returns:
        子任务列表，每个包含 cluster_id, sub_task, matched_intent
    """
    subtasks = []
    
    lines = log_text.strip().split('\n')
    current_subtask = None
    
    for line in lines:
        # 匹配子任务头 [1] cluster_id=30
        subtask_match = re.match(r'^\[(\d+)\]\s+cluster_id=(\w+)', line)
        if subtask_match:
            if current_subtask:
                subtasks.append(current_subtask)
            current_subtask = {
                'index': int(subtask_match.group(1)),
                'cluster_id': subtask_match.group(2),
                'sub_task': '',
                'matched_intent': ''
            }
            continue
        
        if current_subtask:
            # 匹配 sub_task
            if line.strip().startswith('sub_task:'):
                current_subtask['sub_task'] = line.split('sub_task:', 1)[1].strip()
            
            # 匹配 matched_intent
            elif line.strip().startswith('matched_intent:'):
                current_subtask['matched_intent'] = line.split('matched_intent:', 1)[1].strip()
    
    # 添加最后一个
    if current_subtask:
        subtasks.append(current_subtask)
    
    return subtasks


def visualize_from_log(log_text: str, utg_folder: str, output_dir: str = "output"):
    """
    从文本日志生成可视化图片
    
    Args:
        log_text: 文本格式的日志
        utg_folder: UTG数据文件夹路径
        output_dir: 输出目录
        
    Returns:
        生成的图片路径列表
    """
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 解析日志
    subtasks = parse_action_log(log_text)
    
    if not subtasks:
        print("未能解析出任何子任务")
        return []
    
    print(f"解析得到 {len(subtasks)} 个子任务")
    
    # 创建可视化器
    visualizer = ActionVisualizer(utg_folder)
    
    # 为每个子任务生成可视化
    output_paths = []
    for subtask in subtasks:
        cluster_id = subtask['cluster_id']
        matched_intent = subtask['matched_intent']
        index = subtask['index']
        
        if not matched_intent:
            print(f"子任务 {index} 没有matched_intent，跳过")
            continue
        
        output_file = f"subtask_{index}_cluster_{cluster_id}.png"
        output_path = os.path.join(output_dir, output_file)
        
        print(f"\n生成子任务 {index} 的可视化...")
        print(f"  cluster_id: {cluster_id}")
        print(f"  matched_intent: {matched_intent[:60]}...")
        
        success = visualizer.visualize_actions(
            cluster_id=cluster_id,
            matched_intent=matched_intent,
            output_path=output_path
        )
        
        if success:
            output_paths.append(output_path)
            print(f"  ✓ 已保存: {output_path}")
        else:
            print(f"  ✗ 生成失败")
    
    print(f"\n完成! 共生成 {len(output_paths)} 个可视化结果")
    return output_paths


def main():
    """测试可视化工具"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    utg_folder = os.path.join(base_dir, "utg", "NetEase Cloud Music")
    
    # 测试1: 直接使用cluster_id和matched_intent
    print("=" * 60)
    print("测试1: 直接可视化")
    print("=" * 60)
    visualizer = ActionVisualizer(utg_folder)
    
    cluster_id = "35"
    matched_intent = "The user wants to switch from the 'Follow' tab to the 'Recommend' tab to view personalized music recommendations and trending content."
    
    visualizer.visualize_actions(
        cluster_id=cluster_id,
        matched_intent=matched_intent,
        output_path="test_visualization.png"
    )
    
    # 测试2: 从文本日志生成
    print("\n" + "=" * 60)
    print("测试2: 从文本日志生成可视化")
    print("=" * 60)
    
    log_text = """
Original task: 搜索"周杰伦"的歌曲并播放，然后添加到我的收藏夹。
[1] cluster_id=30
    sub_task: Search for songs by '周杰伦' within the app.
    matched_intent: The user is searching for music, artists, or songs within the app by interacting with the search bar.
    actions: 1 steps
      (1) CLICK @ C358B79A721B9728C928058B95FA360C
           xpath: /android.widget.FrameLayout/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.FrameLayout/android.widget.FrameLayout/android.widget.FrameLayout/androidx.drawerlayout.widget.DrawerLayout/android.widget.FrameLayout/android.widget.RelativeLayout/android.view.ViewGroup/androidx.viewpager.widget.ViewPager/androidx.recyclerview.widget.RecyclerView/android.widget.FrameLayout/android.widget.FrameLayout/android.widget.FrameLayout[0]/android.widget.LinearLayout/android.widget.LinearLayout/android.widget.ImageView
[2] cluster_id=26
    sub_task: Select and initiate playback of a specific song from the search results.
    matched_intent: The user is navigating through a playlist to select or view details of a specific song.
    actions: 1 steps
      (1) CLICK @ 93274F508507AB30DD95CF4AD31AF119
           xpath: /android.widget.FrameLayout/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.FrameLayout[3]/android.widget.FrameLayout/android.view.ViewGroup[0]/androidx.recyclerview.widget.RecyclerView/android.widget.LinearLayout[1]
[3] cluster_id=75
    sub_task: Add the currently playing song to your favorites or collection.
    matched_intent: The user wants to share the currently playing song with friends or other apps.     
    actions: 1 steps
      (1) CLICK @ 4CAB0F98A55165DD34B1F8E776E964B3
           xpath: /android.widget.FrameLayout/android.widget.FrameLayout/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.FrameLayout/android.widget.FrameLayout/android.widget.RelativeLayout/android.view.ViewGroup/androidx.appcompat.widget.LinearLayoutCompat/android.widget.LinearLayout/android.widget.FrameLayout/android.widget.LinearLayout/android.widget.RelativeLayout
"""
    
    output_dir = os.path.join(base_dir, "output_from_log")
    visualize_from_log(log_text, utg_folder, output_dir)


if __name__ == "__main__":
    main()
