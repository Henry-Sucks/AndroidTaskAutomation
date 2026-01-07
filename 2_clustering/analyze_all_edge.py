"""
分析UTG中所有边（edge）的语义转换

使用VLM分析每条边的交互语义，生成结构化的转换描述
输出格式：edge_analysis.json
"""

import json
import re
import os
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image, ImageDraw

# 导入客户端
import sys
sys.path.append(str(Path(__file__).parent.parent / "3_context_summarization"))
from clients.vlm_client import VLMClient

# 导入prompt
from prompt import prompt_for_edge


class EdgeAnalyzer:
    """UTG边分析器"""
    
    def __init__(self, utg_path: str, max_workers: int = 5):
        """
        初始化分析器
        
        Args:
            utg_path: UTG文件路径 (utg.js 或 utg_clustered.js)
            max_workers: 并行处理的线程数
        """
        self.utg_path = Path(utg_path)
        self.utg_folder = self.utg_path.parent
        self.max_workers = max_workers
        
        # 数据结构
        self.nodes: Dict[str, Dict] = {}
        self.edges: List[Dict] = []
        
        # VLM客户端
        self.vlm_client = VLMClient()
        
        # 分析结果
        self.analysis_results: Dict[str, Dict] = {}
        
        # 统计信息
        self.stats = {
            'total_edges': 0,
            'analyzed_edges': 0,
            'failed_edges': 0,
            'skipped_edges': 0  # 没有截图的边
        }
        
        print(f"初始化边分析器: {self.utg_path}")
        print(f"  并行线程数: {self.max_workers}")
    
    # =========================================================================
    # 数据加载（参考 local_index_builder.py）
    # =========================================================================
    
    def load_utg_data(self):
        """加载UTG数据"""
        print("\n=== 加载UTG数据 ===")
        
        js_text = self._read_utg_js(self.utg_path)
        
        # 加载节点
        self.nodes = self._load_nodes(js_text)
        print(f"✓ 加载 {len(self.nodes)} 个节点")
        
        # 加载边
        self.edges = self._load_edges(js_text)
        self.stats['total_edges'] = len(self.edges)
        print(f"✓ 加载 {len(self.edges)} 条边")
    
    def _read_utg_js(self, path: Path) -> str:
        """读取UTG JavaScript文件"""
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def _extract_js_array_for_var(self, js_text: str, var_name: str) -> str:
        """提取JavaScript变量数组内容"""
        pattern = rf"var\s+{var_name}\s*=\s*\[([\s\S]*?)\];"
        m = re.search(pattern, js_text)
        if not m:
            return ""
        return m.group(1)
    
    def _iter_object_blocks(self, array_inner_text: str) -> List[str]:
        """解析JavaScript对象块"""
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
    
    def _js_object_to_json(self, obj_text: str) -> str:
        """将JS风格对象转换为JSON"""
        s = obj_text
        # 去除尾随逗号
        s = re.sub(r',\s*}', '}', s)
        s = re.sub(r',\s*]', ']', s)
        # 为键添加引号
        s = re.sub(r'([,{]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', s)
        return s
    
    def _load_nodes(self, js_text: str) -> Dict[str, Dict]:
        """从UTG中解析节点"""
        inner = self._extract_js_array_for_var(js_text, 'nodes')
        nodes = {}
        
        for block in self._iter_object_blocks(inner):
            json_text = self._js_object_to_json(block)
            try:
                obj = json.loads(json_text)
                node_id = obj.get('id')
                if node_id:
                    nodes[node_id] = obj
            except Exception as e:
                print(f"  警告: 节点解析失败 - {e}")
        
        return nodes
    
    def _load_edges(self, js_text: str) -> List[Dict]:
        """从UTG中解析边"""
        inner = self._extract_js_array_for_var(js_text, 'edges')
        edges = []
        
        for block in self._iter_object_blocks(inner):
            json_text = self._js_object_to_json(block)
            try:
                obj = json.loads(json_text)
                
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
            except Exception as e:
                print(f"  警告: 边解析失败 - {e}")
        
        return edges
    
    # =========================================================================
    # 核心分析逻辑
    # =========================================================================
    
    def analyze_all_edges(self, use_parallel: bool = True):
        """
        分析所有边
        
        Args:
            use_parallel: 是否使用并行处理
        """
        print("\n=== 开始分析边 ===")
        
        if use_parallel:
            self._analyze_parallel()
        else:
            self._analyze_sequential()
        
        print("\n=== 分析完成 ===")
        self._print_statistics()
    
    def _analyze_sequential(self):
        """串行分析"""
        for i, edge in enumerate(self.edges):
            edge_id = edge['id']
            
            if (i + 1) % 10 == 0:
                print(f"进度: {i+1}/{len(self.edges)} ({(i+1)/len(self.edges)*100:.1f}%)")
            
            result = self._analyze_edge(edge)
            if result:
                self.analysis_results[edge_id] = result
    
    def _analyze_parallel(self):
        """并行分析"""
        print(f"使用 {self.max_workers} 个线程并行处理")
        
        processed_count = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_edge = {
                executor.submit(self._analyze_edge, edge): edge 
                for edge in self.edges
            }
            
            for future in as_completed(future_to_edge):
                edge = future_to_edge[future]
                edge_id = edge['id']
                processed_count += 1
                
                try:
                    result = future.result()
                    if result:
                        self.analysis_results[edge_id] = result
                    
                    if processed_count % 10 == 0:
                        print(f"进度: {processed_count}/{len(self.edges)} "
                              f"({processed_count/len(self.edges)*100:.1f}%) - "
                              f"已分析: {self.stats['analyzed_edges']}")
                        
                except Exception as e:
                    print(f"边 {edge_id} 分析异常: {e}")
                    self.stats['failed_edges'] += 1
    
    def _analyze_edge(self, edge: Dict) -> Optional[Dict]:
        """
        分析单条边
        
        Returns:
            分析结果字典，如果失败则返回None
        """
        edge_id = edge['id']
        from_node_id = edge.get('from')
        to_node_id = edge.get('to')
        
        # 检查节点是否存在
        if from_node_id not in self.nodes or to_node_id not in self.nodes:
            print(f"  警告: 边 {edge_id} 的节点不存在")
            self.stats['skipped_edges'] += 1
            return None
        
        from_node = self.nodes[from_node_id]
        to_node = self.nodes[to_node_id]
        
        # 获取截图路径
        from_image = from_node.get('image', '')
        to_image = to_node.get('image', '')
        
        if not from_image or not to_image:
            self.stats['skipped_edges'] += 1
            return None
        
        from_image_path = self.utg_folder / "states" / from_image
        to_image_path = self.utg_folder / "states" / to_image
        
        if not from_image_path.exists() or not to_image_path.exists():
            print(f"  警告: 截图不存在 - {edge_id}")
            self.stats['skipped_edges'] += 1
            return None
        
        try:
            # 创建带红框的组合图片
            combined_image_path = self._create_marked_combined_image(
                str(from_image_path), str(to_image_path), edge
            )
            
            if not combined_image_path:
                self.stats['skipped_edges'] += 1
                return None
            
            # 构建prompt
            action_types = edge.get('action_types', ['CLICK'])
            interaction_type = action_types[0] if action_types else 'CLICK'
            
            # 使用 prompt_for_edge，替换 {interaction_type}
            prompt = prompt_for_edge.replace('{interaction_type}', interaction_type)
            
            # 调用VLM分析
            result = self.vlm_client.run(
                prompt=prompt,
                image_url=combined_image_path,
                enable_thinking=False
            )
            
            # 清理临时文件
            if os.path.exists(combined_image_path):
                os.remove(combined_image_path)
            
            response_content = result.get('content', '')
            
            # 解析JSON响应
            analysis = self._parse_json_response(response_content)
            
            # 添加边元信息
            analysis['edge_id'] = edge_id
            analysis['from_node'] = from_node_id
            analysis['to_node'] = to_node_id
            analysis['interaction_type'] = interaction_type
            analysis['element_text'] = edge.get('text', '')
            analysis['element_type'] = edge.get('type', '')
            analysis['bounds'] = edge.get('bounds', '')
            
            self.stats['analyzed_edges'] += 1
            
            return analysis
            
        except Exception as e:
            print(f"  边 {edge_id} 分析失败: {e}")
            self.stats['failed_edges'] += 1
            return None
    
    def _create_marked_combined_image(self, from_image_path: str, 
                                     to_image_path: str, edge: Dict) -> Optional[str]:
        """
        创建带红框标记的组合图片（参考 local_index_builder.py）
        
        Returns:
            临时图片路径，如果失败则返回None
        """
        try:
            # 打开图片
            from_img = Image.open(from_image_path)
            to_img = Image.open(to_image_path)
            
            # 确保两张图片高度一致
            max_height = max(from_img.height, to_img.height)
            if from_img.height < max_height:
                new_from = Image.new('RGB', (from_img.width, max_height), (255, 255, 255))
                new_from.paste(from_img, (0, 0))
                from_img = new_from
            if to_img.height < max_height:
                new_to = Image.new('RGB', (to_img.width, max_height), (255, 255, 255))
                new_to.paste(to_img, (0, 0))
                to_img = new_to
            
            # 在from_img上绘制红框
            bounds_str = edge.get('bounds', '')
            if bounds_str:
                bounds = self._parse_bounds(bounds_str)
                if bounds:
                    draw = ImageDraw.Draw(from_img)
                    x1, y1, x2, y2 = bounds
                    # 绘制红色边框（粗线）
                    for i in range(5):  # 5像素粗细
                        draw.rectangle(
                            [x1-i, y1-i, x2+i, y2+i],
                            outline='red'
                        )
            
            # 拼接图片（左右排列）
            combined_width = from_img.width + to_img.width
            combined_img = Image.new('RGB', (combined_width, max_height), (255, 255, 255))
            combined_img.paste(from_img, (0, 0))
            combined_img.paste(to_img, (from_img.width, 0))
            
            # 保存临时文件
            temp_path = self.utg_folder / f"temp_edge_{edge['id']}.jpg"
            combined_img.save(temp_path, quality=95)
            
            return str(temp_path)
            
        except Exception as e:
            print(f"  创建组合图片失败: {e}")
            return None
    
    def _parse_bounds(self, bounds_str: str) -> Optional[tuple]:
        """
        解析bounds字符串
        例如: "[696,654][864,744]" -> (696, 654, 864, 744)
        """
        if not bounds_str:
            return None
        
        try:
            # 尝试多种格式
            # 格式1: "[x1,y1][x2,y2]"
            match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
            if match:
                x1, y1, x2, y2 = map(int, match.groups())
                return (x1, y1, x2, y2)
            
            # 格式2: "x1,y1,x2,y2"
            parts = bounds_str.replace('[', '').replace(']', '').split(',')
            if len(parts) == 4:
                x1, y1, x2, y2 = map(int, parts)
                return (x1, y1, x2, y2)
        
        except Exception:
            pass
        
        return None
    
    def _parse_json_response(self, response: str) -> Dict:
        """解析VLM的JSON响应"""
        try:
            clean_str = response.strip()
            
            # 移除Markdown代码块
            if '```json' in clean_str:
                start = clean_str.find('```json') + 7
                end = clean_str.find('```', start)
                if end != -1:
                    clean_str = clean_str[start:end].strip()
            elif '```' in clean_str:
                start = clean_str.find('```') + 3
                end = clean_str.find('```', start)
                if end != -1:
                    clean_str = clean_str[start:end].strip()
            
            # 找到JSON对象的边界
            first_brace = clean_str.find('{')
            if first_brace == -1:
                raise ValueError("响应中没有找到JSON对象")
            
            # 找到匹配的右括号
            brace_count = 0
            last_brace = -1
            for i in range(first_brace, len(clean_str)):
                if clean_str[i] == '{':
                    brace_count += 1
                elif clean_str[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        last_brace = i
                        break
            
            if last_brace == -1:
                raise ValueError("JSON对象不完整")
            
            json_str = clean_str[first_brace:last_brace+1]
            return json.loads(json_str)
            
        except json.JSONDecodeError as e:
            print(f"  JSON解析失败: {e}")
            print(f"  原始响应前200字符: {response[:200]}")
            raise
        except Exception as e:
            print(f"  解析错误: {e}")
            raise
    
    # =========================================================================
    # 结果输出
    # =========================================================================
    
    def save_results(self, output_filename: str = "edge_analysis.json"):
        """保存分析结果"""
        output_path = self.utg_folder / output_filename
        
        print(f"\n=== 保存结果到 {output_path} ===")
        
        # 准备输出数据
        output_data = {
            'metadata': {
                'utg_file': self.utg_path.name,
                'total_edges': self.stats['total_edges'],
                'analyzed_edges': self.stats['analyzed_edges'],
                'failed_edges': self.stats['failed_edges'],
                'skipped_edges': self.stats['skipped_edges']
            },
            'edges': self.analysis_results
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 保存成功: {len(self.analysis_results)} 条边分析结果")
    
    def _print_statistics(self):
        """打印统计信息"""
        print("\n" + "=" * 60)
        print("分析统计信息")
        print("=" * 60)
        print(f"总边数: {self.stats['total_edges']}")
        print(f"成功分析: {self.stats['analyzed_edges']} "
              f"({self.stats['analyzed_edges']/self.stats['total_edges']*100:.1f}%)")
        print(f"跳过边: {self.stats['skipped_edges']} (无截图或节点不存在)")
        print(f"失败边: {self.stats['failed_edges']}")
        print("=" * 60)


# =============================================================================
# 命令行接口
# =============================================================================

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="UTG边分析工具")
    parser.add_argument("utg_path", help="UTG文件路径 (utg.js 或 utg_clustered.js)")
    parser.add_argument("--workers", type=int, default=5,
                        help="并行线程数，默认: 5")
    parser.add_argument("--output", default="edge_analysis.json",
                        help="输出文件名，默认: edge_analysis.json")
    parser.add_argument("--sequential", action="store_true",
                        help="使用串行模式（不并行）")
    
    args = parser.parse_args()
    
    # 创建分析器
    analyzer = EdgeAnalyzer(
        utg_path=args.utg_path,
        max_workers=args.workers
    )
    
    # 加载数据
    analyzer.load_utg_data()
    
    # 执行分析
    analyzer.analyze_all_edges(use_parallel=not args.sequential)
    
    # 保存结果
    analyzer.save_results(output_filename=args.output)
    
    print("\n处理完成！")


if __name__ == "__main__":
    main()
