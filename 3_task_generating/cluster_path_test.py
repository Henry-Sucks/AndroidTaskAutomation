"""
UTG聚类路径测试工具
用于测试两个状态之间的最短路径查找功能
"""

import sys
import os
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from utg_loader import UTGLoader, UTGGraph


def find_shortest_path_with_clusters(graph: UTGGraph, start_state: str, end_state: str) -> Optional[List[Tuple[str, str, str]]]:
    """
    查找两个状态之间的最短路径，返回(state, cluster, event)的列表
    
    Args:
        graph: UTG图对象
        start_state: 起始状态ID
        end_state: 目标状态ID
        
    Returns:
        路径列表，每个元素是(state_id, cluster_id, event_str)的元组
        如果路径不存在则返回None
    """
    # 检查状态是否存在
    if start_state not in graph.states:
        print(f"错误: 起始状态 '{start_state}' 不存在")
        return None
    
    if end_state not in graph.states:
        print(f"错误: 目标状态 '{end_state}' 不存在")
        return None
    
    # 查找最短路径
    path = graph.get_shortest_path_states(start_state, end_state)
    
    if path is None:
        print(f"路径不存在: {start_state} -> {end_state}")
        return None
    
    # 构建带聚类信息和事件信息的路径
    path_with_clusters = []
    for i, state in enumerate(path):
        cluster = graph.state_to_cluster.get(state, "unknown_cluster")
        
        # 查找触发事件
        event_str = ""
        if i > 0:  # 不是起始状态
            prev_state = path[i-1]
            # 在state_graph中查找边的事件信息
            if graph.state_graph.has_edge(prev_state, state):
                edge_data = graph.state_graph[prev_state][state]
                event_data = edge_data.get('event_data', {})
                if event_data:
                    event_str = event_data.get('event_str', 'unknown_event')
                else:
                    event_str = edge_data.get('event_tag', 'unknown_event')
            else:
                event_str = 'unknown_event'
        
        path_with_clusters.append((state, cluster, event_str))
    
    return path_with_clusters


def save_path_to_file(path_with_clusters: List[Tuple[str, str, str]], 
                     start_state: str, end_state: str, 
                     output_file: Optional[str] = None) -> str:
    """
    将路径保存到txt文件
    
    Args:
        path_with_clusters: 带聚类信息和事件信息的路径
        start_state: 起始状态
        end_state: 目标状态
        output_file: 输出文件路径，如果为None则自动生成
        
    Returns:
        实际使用的输出文件路径
    """
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"path_{start_state[:8]}_{end_state[:8]}_{timestamp}.txt"
    
    output_path = Path(output_file)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"最短路径分析结果\n")
        f.write(f"起始状态: {start_state}\n")
        f.write(f"目标状态: {end_state}\n")
        f.write(f"路径长度: {len(path_with_clusters)}\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("\n" + "="*50 + "\n")
        f.write("路径详情:\n\n")
        
        for i, (state, cluster, event_str) in enumerate(path_with_clusters):
            f.write(f"{state} : {cluster}\n")
            if i > 0 and event_str:  # 不是起始状态且有事件信息
                f.write(f"触发事件：{event_str}\n")
        
        f.write("\n" + "="*50 + "\n")
        f.write("路径摘要:\n")
        clusters_in_path = [cluster for _, cluster, _ in path_with_clusters]
        unique_clusters = list(dict.fromkeys(clusters_in_path))  # 保持顺序去重
        f.write(f"经过的聚类: {' -> '.join(unique_clusters)}\n")
        f.write(f"聚类数量: {len(unique_clusters)}\n")
        
        # 添加事件摘要
        events_in_path = [event_str for _, _, event_str in path_with_clusters if event_str]
        f.write(f"触发的事件数量: {len(events_in_path)}\n")
    
    print(f"路径已保存到: {output_path.absolute()}")
    return str(output_path)


def find_shortest_path_with_clusters_info(graph: UTGGraph, start_cluster: str, end_cluster: str) -> Optional[List[Tuple[str, List[str]]]]:
    """
    查找两个聚类之间的最短路径，返回(cluster, events)的列表
    
    Args:
        graph: UTG图对象
        start_cluster: 起始聚类ID
        end_cluster: 目标聚类ID
        
    Returns:
        路径列表，每个元素是(cluster_id, [event_strs])的元组
        如果路径不存在则返回None
    """
    # 检查聚类是否存在
    if start_cluster not in graph.clusters:
        print(f"错误: 起始聚类 '{start_cluster}' 不存在")
        return None
    
    if end_cluster not in graph.clusters:
        print(f"错误: 目标聚类 '{end_cluster}' 不存在")
        return None
    
    # 查找最短路径
    cluster_path = graph.get_shortest_path_clusters(start_cluster, end_cluster)
    
    if cluster_path is None:
        print(f"聚类路径不存在: {start_cluster} -> {end_cluster}")
        return None
    
    # 构建带事件信息的路径
    path_with_events = []
    for i, cluster in enumerate(cluster_path):
        events = []
        if i > 0:  # 不是起始聚类
            prev_cluster = cluster_path[i-1]
            # 在cluster_graph中查找边的事件信息
            if graph.cluster_graph.has_edge(prev_cluster, cluster):
                edge_data = graph.cluster_graph[prev_cluster][cluster]
                events = edge_data.get('events', [])
                
                # 获取详细的事件字符串
                event_strs = []
                for event_tag in events:
                    if event_tag in graph.events:
                        event_data = graph.events[event_tag]
                        event_str = event_data.get('event_str', event_tag)
                        event_strs.append(event_str)
                    else:
                        event_strs.append(event_tag)
                events = event_strs
        
        path_with_events.append((cluster, events))
    
    return path_with_events


def save_cluster_path_to_file(path_with_events: List[Tuple[str, List[str]]], 
                             start_cluster: str, end_cluster: str, 
                             output_file: Optional[str] = None) -> str:
    """
    将聚类路径保存到txt文件
    
    Args:
        path_with_events: 带事件信息的聚类路径
        start_cluster: 起始聚类
        end_cluster: 目标聚类
        output_file: 输出文件路径，如果为None则自动生成
        
    Returns:
        实际使用的输出文件路径
    """
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"cluster_path_{start_cluster[:8]}_{end_cluster[:8]}_{timestamp}.txt"
    
    output_path = Path(output_file)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"聚类最短路径分析结果\n")
        f.write(f"起始聚类: {start_cluster}\n")
        f.write(f"目标聚类: {end_cluster}\n")
        f.write(f"路径长度: {len(path_with_events)}\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("\n" + "="*50 + "\n")
        f.write("聚类路径详情:\n\n")
        
        for i, (cluster, events) in enumerate(path_with_events):
            if i > 0:  # 不是起始聚类，显示从上一个聚类到当前聚类的转换
                prev_cluster = path_with_events[i-1][0]
                f.write(f"{prev_cluster} -> {cluster}\n")
                
                if events:
                    for j, event_str in enumerate(events, 1):
                        f.write(f"possible_event{j}: {event_str}\n")
                else:
                    f.write("possible_event1: unknown_event\n")
                f.write("\n")
            else:
                # 起始聚类
                f.write(f"起始聚类: {cluster}\n\n")
        
        f.write("="*50 + "\n")
        f.write("路径摘要:\n")
        clusters_in_path = [cluster for cluster, _ in path_with_events]
        f.write(f"经过的聚类: {' -> '.join(clusters_in_path)}\n")
        f.write(f"聚类数量: {len(clusters_in_path)}\n")
        
        # 统计总事件数
        total_events = sum(len(events) for _, events in path_with_events)
        f.write(f"可能的转换事件总数: {total_events}\n")
    
    print(f"聚类路径已保存到: {output_path.absolute()}")
    return str(output_path)


def test_cluster_shortest_path(clustered_folder: str, start_cluster: str, end_cluster: str, 
                              output_file: Optional[str] = None, verbose: bool = True):
    """
    测试两个聚类之间的最短路径
    
    Args:
        clustered_folder: 聚类后的UTG文件夹路径
        start_cluster: 起始聚类ID
        end_cluster: 目标聚类ID
        output_file: 输出文件路径
        verbose: 是否显示详细信息
    """
    print(f"开始聚类路径查找测试...")
    print(f"UTG文件夹: {clustered_folder}")
    print(f"起始聚类: {start_cluster}")
    print(f"目标聚类: {end_cluster}")
    print("-" * 50)
    
    try:
        # 加载UTG数据
        if verbose:
            print("正在加载UTG数据...")
        
        loader = UTGLoader(clustered_folder)
        graph = loader.load_utg()
        
        if verbose:
            print(f"加载完成: {len(graph.states)} 个状态, {len(graph.clusters)} 个聚类")
        
        # 查找路径
        if verbose:
            print(f"正在查找聚类路径: {start_cluster} -> {end_cluster}")
        
        path_with_events = find_shortest_path_with_clusters_info(graph, start_cluster, end_cluster)
        
        if path_with_events is None:
            print("未找到聚类路径!")
            return None
        
        # 显示路径信息
        print(f"找到聚类路径! 长度: {len(path_with_events)}")
        
        if verbose:
            print("\n聚类路径详情:")
            for i, (cluster, events) in enumerate(path_with_events):
                if i > 0:  # 不是起始聚类
                    prev_cluster = path_with_events[i-1][0]
                    print(f"{prev_cluster} -> {cluster}")
                    if events:
                        for j, event_str in enumerate(events, 1):
                            print(f"  possible_event{j}: {event_str}")
                    else:
                        print(f"  possible_event1: unknown_event")
                    print()
                else:
                    print(f"起始聚类: {cluster}")
        
        # 保存到文件
        output_path = save_cluster_path_to_file(path_with_events, start_cluster, end_cluster, output_file)
        
        # 返回路径信息
        return {
            'path': path_with_events,
            'length': len(path_with_events),
            'output_file': output_path,
            'total_events': sum(len(events) for _, events in path_with_events)
        }
        
    except Exception as e:
        print(f"错误: {e}")
        return None


def test_shortest_path(clustered_folder: str, start_state: str, end_state: str, 
                      output_file: Optional[str] = None, verbose: bool = True):
    """
    测试两个状态之间的最短路径
    
    Args:
        clustered_folder: 聚类后的UTG文件夹路径
        start_state: 起始状态ID
        end_state: 目标状态ID
        output_file: 输出文件路径
        verbose: 是否显示详细信息
    """
    print(f"开始路径查找测试...")
    print(f"UTG文件夹: {clustered_folder}")
    print(f"起始状态: {start_state}")
    print(f"目标状态: {end_state}")
    print("-" * 50)
    
    try:
        # 加载UTG数据
        if verbose:
            print("正在加载UTG数据...")
        
        loader = UTGLoader(clustered_folder)
        graph = loader.load_utg()
        
        if verbose:
            print(f"加载完成: {len(graph.states)} 个状态, {len(graph.clusters)} 个聚类")
        
        # 查找路径
        if verbose:
            print(f"正在查找路径: {start_state} -> {end_state}")
        
        path_with_clusters = find_shortest_path_with_clusters(graph, start_state, end_state)
        
        if path_with_clusters is None:
            print("未找到路径!")
            return None
        
        # 显示路径信息
        print(f"找到路径! 长度: {len(path_with_clusters)}")
        
        if verbose:
            print("\n路径详情:")
            for i, (state, cluster, event_str) in enumerate(path_with_clusters):
                print(f"{i+1:2d}. {state} : {cluster}")
                if i > 0 and event_str:  # 不是起始状态且有事件信息
                    print(f"     触发事件：{event_str}")
        
        # 保存到文件
        output_path = save_path_to_file(path_with_clusters, start_state, end_state, output_file)
        
        # 返回路径信息
        return {
            'path': path_with_clusters,
            'length': len(path_with_clusters),
            'output_file': output_path,
            'clusters': [cluster for _, cluster, _ in path_with_clusters],
            'unique_clusters': list(dict.fromkeys([cluster for _, cluster, _ in path_with_clusters]))
        }
        
    except Exception as e:
        print(f"错误: {e}")
        return None


def test_multiple_paths(clustered_folder: str, test_cases: List[Tuple[str, str]], 
                       output_dir: str = "path_results"):
    """
    测试多个路径查找案例
    
    Args:
        clustered_folder: 聚类后的UTG文件夹路径
        test_cases: 测试用例列表，每个元素是(start_state, end_state)
        output_dir: 输出目录
    """
    print(f"开始批量路径测试，共 {len(test_cases)} 个测试用例")
    
    # 创建输出目录
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # 加载UTG数据
    loader = UTGLoader(clustered_folder)
    graph = loader.load_utg()
    
    results = []
    
    for i, (start_state, end_state) in enumerate(test_cases, 1):
        print(f"\n=== 测试用例 {i}/{len(test_cases)} ===")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_path / f"path_test_{i}_{timestamp}.txt"
        
        result = test_shortest_path(clustered_folder, start_state, end_state, 
                                  str(output_file), verbose=False)
        
        if result:
            results.append({
                'case_id': i,
                'start_state': start_state,
                'end_state': end_state,
                'success': True,
                'path_length': result['length'],
                'cluster_count': len(result['unique_clusters']),
                'output_file': result['output_file']
            })
        else:
            results.append({
                'case_id': i,
                'start_state': start_state,
                'end_state': end_state,
                'success': False,
                'path_length': 0,
                'cluster_count': 0,
                'output_file': None
            })
    
    # 生成汇总报告
    summary_file = output_path / f"batch_test_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("批量路径测试汇总报告\n")
        f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"UTG文件夹: {clustered_folder}\n")
        f.write(f"测试用例数: {len(test_cases)}\n")
        f.write(f"成功案例数: {sum(1 for r in results if r['success'])}\n")
        f.write(f"失败案例数: {sum(1 for r in results if not r['success'])}\n")
        f.write("\n" + "="*60 + "\n")
        f.write("详细结果:\n\n")
        
        for result in results:
            f.write(f"案例 {result['case_id']}: {result['start_state'][:8]}...-> {result['end_state'][:8]}...\n")
            f.write(f"  状态: {'成功' if result['success'] else '失败'}\n")
            if result['success']:
                f.write(f"  路径长度: {result['path_length']}\n")
                f.write(f"  聚类数量: {result['cluster_count']}\n")
                f.write(f"  输出文件: {result['output_file']}\n")
            f.write("\n")
    
    print(f"\n批量测试完成! 汇总报告: {summary_file}")
    return results


def get_sample_states(clustered_folder: str, count: int = 5) -> List[str]:
    """
    从UTG中获取示例状态ID
    
    Args:
        clustered_folder: 聚类后的UTG文件夹路径
        count: 获取的状态数量
        
    Returns:
        状态ID列表
    """
    loader = UTGLoader(clustered_folder)
    graph = loader.load_utg()
    
    states = list(graph.states.keys())
    return states[:count] if len(states) >= count else states


def interactive_path_test(clustered_folder: str):
    """
    交互式路径测试
    
    Args:
        clustered_folder: 聚类后的UTG文件夹路径
    """
    print("=== UTG 路径查找工具 ===")
    print("输入 'q' 退出程序")
    print("输入 'sample' 查看示例状态")
    
    loader = UTGLoader(clustered_folder)
    graph = loader.load_utg()
    
    while True:
        print(f"\n当前UTG: {len(graph.states)} 个状态, {len(graph.clusters)} 个聚类")
        
        start_state = input("请输入起始状态ID: ").strip()
        if start_state.lower() == 'q':
            break
        elif start_state.lower() == 'sample':
            sample_states = get_sample_states(clustered_folder, 10)
            print("示例状态ID:")
            for i, state in enumerate(sample_states, 1):
                cluster = graph.state_to_cluster.get(state, "unknown")
                print(f"  {i:2d}. {state} (cluster: {cluster})")
            continue
        
        end_state = input("请输入目标状态ID: ").strip()
        if end_state.lower() == 'q':
            break
        
        # 执行路径查找
        result = test_shortest_path(clustered_folder, start_state, end_state)
        
        if result:
            print(f"路径长度: {result['length']}")
            print(f"经过聚类: {' -> '.join(result['unique_clusters'])}")


def get_sample_clusters(clustered_folder: str, count: int = 5) -> List[str]:
    """
    从UTG中获取示例聚类ID
    
    Args:
        clustered_folder: 聚类后的UTG文件夹路径
        count: 获取的聚类数量
        
    Returns:
        聚类ID列表
    """
    loader = UTGLoader(clustered_folder)
    graph = loader.load_utg()
    
    clusters = list(graph.clusters.keys())
    return clusters[:count] if len(clusters) >= count else clusters


if __name__ == "__main__":
    # 默认配置
    default_clustered_folder = r"c:\Projects\AndroidTaskAutomation\3_task_generating\utg\original_greedy_dfs_20251106_160351_clustered"
    
    # 测试状态路径
    print("=== 状态路径测试 ===")
    sample_states = ['3eb86e583b0b039963e5156f6e5cb88e', '452f9612b5c1354d9620ceaf4ceda19c']
    
    if len(sample_states) >= 2:
        print(f"找到 {len(sample_states)} 个状态，选择前2个进行测试:")
        for i, state in enumerate(sample_states[:5], 1):
            print(f"  {i}. {state}")
        
        # 使用前两个状态进行测试
        start_state = sample_states[0]
        end_state = sample_states[-1]  # 使用最后一个状态作为目标
        
        print(f"\n执行状态路径测试: {start_state} -> {end_state}")
        result = test_shortest_path(default_clustered_folder, start_state, end_state)
        
        if result:
            print(f"\n状态路径测试成功!")
            print(f"路径文件: {result['output_file']}")
        else:
            print(f"\n状态路径测试失败: 未找到路径")
    
    # 测试聚类路径
    print(f"\n\n=== 聚类路径测试 ===")
    print("获取示例聚类...")
    sample_clusters = get_sample_clusters(default_clustered_folder, 5)
    
    if len(sample_clusters) >= 2:
        print(f"找到 {len(sample_clusters)} 个聚类，选择前2个进行测试:")
        for i, cluster in enumerate(sample_clusters[:3], 1):
            print(f"  {i}. {cluster}")
        
        # 使用前两个聚类进行测试
        # start_cluster = sample_clusters[0]
        # end_cluster = sample_clusters[-1]  # 使用最后一个聚类作为目标
        start_cluster = "8f04900d6ff21a979472d1d41e0e1138"
        end_cluster = "80a5d093529b10172a7828c1c375d24b"
        
        print(f"\n执行聚类路径测试: {start_cluster} -> {end_cluster}")
        cluster_result = test_cluster_shortest_path(default_clustered_folder, start_cluster, end_cluster)
        
        if cluster_result:
            print(f"\n聚类路径测试成功!")
            print(f"聚类路径文件: {cluster_result['output_file']}")
            print(f"路径长度: {cluster_result['length']}")
            print(f"总事件数: {cluster_result['total_events']}")
        else:
            print(f"\n聚类路径测试失败: 未找到路径")
    
    # 可以取消注释来启动交互模式
    # interactive_path_test(default_clustered_folder)
