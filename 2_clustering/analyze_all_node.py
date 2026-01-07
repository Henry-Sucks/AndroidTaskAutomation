"""
分析UTG中所有节点（state）的功能描述

使用VLM分析每个节点的截图，生成结构化的功能描述
输出格式：node_analysis.json
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# 导入客户端
import sys
sys.path.append(str(Path(__file__).parent.parent / "3_context_summarization"))
from clients.vlm_client import VLMClient

# 导入prompt
from prompt import prompt_for_node


class NodeAnalyzer:
    """UTG节点分析器"""
    
    def __init__(self, utg_path: str, max_workers: int = 6):
        """
        初始化分析器
        
        Args:
            utg_path: UTG文件路径 (utg.js)
            max_workers: 并行处理的线程数
        """
        self.utg_path = Path(utg_path)
        self.utg_folder = self.utg_path.parent
        self.max_workers = max_workers
        
        # 数据结构
        self.nodes: List[Dict] = []
        self.node_map: Dict[str, Dict] = {}
        
        # VLM客户端
        self.vlm_client = VLMClient()
        
        # 分析结果
        self.analysis_results: Dict[str, Dict] = {}
        
        # 统计信息
        self.stats = {
            'total_nodes': 0,
            'analyzed_nodes': 0,
            'failed_nodes': 0,
            'skipped_nodes': 0  # 没有截图的节点
        }
        
        print(f"初始化节点分析器: {self.utg_path}")
        print(f"  并行线程数: {self.max_workers}")
    
    # =========================================================================
    # 数据加载
    # =========================================================================
    
    def load_utg_data(self):
        """加载UTG数据"""
        print("\n=== 加载UTG数据 ===")
        
        with open(self.utg_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取nodes数组
        nodes_match = re.search(r'var\s+nodes\s*=\s*(\[.*?\]);', content, re.DOTALL)
        if not nodes_match:
            raise ValueError("无法从UTG文件中提取nodes数据")
        
        nodes_str = nodes_match.group(1)
        nodes_str = self._js_to_python(nodes_str)
        
        try:
            self.nodes = eval(nodes_str)
            self.node_map = {n['id']: n for n in self.nodes}
            self.stats['total_nodes'] = len(self.nodes)
            print(f"✓ 加载 {len(self.nodes)} 个节点")
        except Exception as e:
            print(f"解析nodes失败: {e}")
            raise
    
    def _js_to_python(self, js_str: str) -> str:
        """JavaScript转Python"""
        js_str = re.sub(r'\}\s*\{', '}, {', js_str)
        js_str = js_str.replace('null', 'None')
        js_str = re.sub(r'(\w+):', r"'\1':", js_str)
        return js_str
    
    # =========================================================================
    # 核心分析逻辑
    # =========================================================================
    
    def analyze_all_nodes(self, use_parallel: bool = True):
        """
        分析所有节点
        
        Args:
            use_parallel: 是否使用并行处理
        """
        print("\n=== 开始分析节点 ===")
        
        if use_parallel:
            self._analyze_parallel()
        else:
            self._analyze_sequential()
        
        print("\n=== 分析完成 ===")
        self._print_statistics()
    
    def _analyze_sequential(self):
        """串行分析"""
        for i, node in enumerate(self.nodes):
            node_id = node['id']
            
            if (i + 1) % 10 == 0:
                print(f"进度: {i+1}/{len(self.nodes)} ({(i+1)/len(self.nodes)*100:.1f}%)")
            
            result = self._analyze_node(node)
            if result:
                self.analysis_results[node_id] = result
    
    def _analyze_parallel(self):
        """并行分析"""
        print(f"使用 {self.max_workers} 个线程并行处理")
        
        processed_count = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_node = {
                executor.submit(self._analyze_node, node): node 
                for node in self.nodes
            }
            
            for future in as_completed(future_to_node):
                node = future_to_node[future]
                node_id = node['id']
                processed_count += 1
                
                try:
                    result = future.result()
                    if result:
                        self.analysis_results[node_id] = result
                    
                    if processed_count % 10 == 0:
                        print(f"进度: {processed_count}/{len(self.nodes)} "
                              f"({processed_count/len(self.nodes)*100:.1f}%) - "
                              f"已分析: {self.stats['analyzed_nodes']}")
                        
                except Exception as e:
                    print(f"节点 {node_id} 分析异常: {e}")
                    self.stats['failed_nodes'] += 1
    
    def _analyze_node(self, node: Dict) -> Optional[Dict]:
        """
        分析单个节点
        
        Returns:
            分析结果字典，如果失败则返回None
        """
        node_id = node['id']
        image_file = node.get('image', '')
        
        # 检查是否有截图
        if not image_file:
            self.stats['skipped_nodes'] += 1
            return None
        
        image_path = self.utg_folder / "states" / image_file
        if not image_path.exists():
            print(f"  警告: 截图不存在 - {image_path}")
            self.stats['skipped_nodes'] += 1
            return None
        
        try:
            # 调用VLM分析
            result = self.vlm_client.run(
                prompt=prompt_for_node,
                image_url=str(image_path)
            )
            
            response_content = result.get('content', '')
            
            # 解析JSON响应
            analysis = self._parse_json_response(response_content)
            
            # 添加节点元信息
            analysis['node_id'] = node_id
            analysis['image_file'] = image_file
            analysis['activity'] = node.get('activity', '')
            
            self.stats['analyzed_nodes'] += 1
            
            return analysis
            
        except Exception as e:
            print(f"  节点 {node_id} 分析失败: {e}")
            self.stats['failed_nodes'] += 1
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
    
    def save_results(self, output_filename: str = "node_analysis.json"):
        """保存分析结果"""
        output_path = self.utg_folder / output_filename
        
        print(f"\n=== 保存结果到 {output_path} ===")
        
        # 准备输出数据
        output_data = {
            'metadata': {
                'utg_file': self.utg_path.name,
                'total_nodes': self.stats['total_nodes'],
                'analyzed_nodes': self.stats['analyzed_nodes'],
                'failed_nodes': self.stats['failed_nodes'],
                'skipped_nodes': self.stats['skipped_nodes']
            },
            'nodes': self.analysis_results
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 保存成功: {len(self.analysis_results)} 个节点分析结果")
    
    def _print_statistics(self):
        """打印统计信息"""
        print("\n" + "=" * 60)
        print("分析统计信息")
        print("=" * 60)
        print(f"总节点数: {self.stats['total_nodes']}")
        print(f"成功分析: {self.stats['analyzed_nodes']} "
              f"({self.stats['analyzed_nodes']/self.stats['total_nodes']*100:.1f}%)")
        print(f"跳过节点: {self.stats['skipped_nodes']} (无截图)")
        print(f"失败节点: {self.stats['failed_nodes']}")
        print("=" * 60)


# =============================================================================
# 命令行接口
# =============================================================================

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="UTG节点分析工具")
    parser.add_argument("utg_path", help="UTG文件路径 (utg.js)")
    parser.add_argument("--workers", type=int, default=5,
                        help="并行线程数，默认: 5")
    parser.add_argument("--output", default="node_analysis.json",
                        help="输出文件名，默认: node_analysis.json")
    parser.add_argument("--sequential", action="store_true",
                        help="使用串行模式（不并行）")
    
    args = parser.parse_args()
    
    # 创建分析器
    analyzer = NodeAnalyzer(
        utg_path=args.utg_path,
        max_workers=args.workers
    )
    
    # 加载数据
    analyzer.load_utg_data()
    
    # 执行分析
    analyzer.analyze_all_nodes(use_parallel=not args.sequential)
    
    # 保存结果
    analyzer.save_results(output_filename=args.output)
    
    print("\n处理完成！")


if __name__ == "__main__":
    main()
