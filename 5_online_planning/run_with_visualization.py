"""
完整流程：从用户任务到可视化
"""
import os
import json
from online_planner import GlobalPlanner, LocalMatcher, _load_global_index, _load_local_index
from visualize import ActionVisualizer, visualize_from_log


def run_task_with_visualization(user_task: str, output_dir: str = "output"):
    """
    运行完整流程：任务规划 + 本地匹配 + 可视化
    
    Args:
        user_task: 用户自然语言任务
        output_dir: 输出目录
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    utg_folder = os.path.join(base_dir, "utg", "NetEase Cloud Music")
    
    # 创建输出目录
    output_path = os.path.join(base_dir, output_dir)
    os.makedirs(output_path, exist_ok=True)
    
    # 1. 加载索引
    print("=" * 60)
    print("步骤 1: 加载Global和Local索引...")
    global_index = _load_global_index(base_dir)
    local_index = _load_local_index(base_dir)
    print(f"已加载 {len(global_index)} 个cluster的全局索引")
    print(f"已加载 {len(local_index)} 个cluster的本地索引")
    
    # 2. 全局规划
    print("\n" + "=" * 60)
    print(f"步骤 2: 全局规划 - 将任务拆解为子任务")
    print(f"用户任务: {user_task}")
    planner = GlobalPlanner(global_index)
    plan = planner.plan(user_task)
    
    print(f"\n拆解得到 {len(plan.sub_tasks)} 个子任务:")
    for i, sub in enumerate(plan.sub_tasks, 1):
        print(f"  [{i}] cluster={sub.cluster_id} | {sub.sub_task}")
    
    # 3. 本地匹配
    print("\n" + "=" * 60)
    print("步骤 3: 本地匹配 - 为每个子任务找到具体动作")
    matcher = LocalMatcher(local_index)
    plan = matcher.enrich_task_plan(plan)
    
    for i, sub in enumerate(plan.sub_tasks, 1):
        print(f"\n子任务 {i}:")
        print(f"  cluster_id: {sub.cluster_id}")
        print(f"  sub_task: {sub.sub_task}")
        print(f"  matched_intent: {sub.matched_intent}")
        print(f"  actions: {len(sub.actions)} 步")
    
    # 4. 可视化每个子任务
    print("\n" + "=" * 60)
    print("步骤 4: 可视化生成...")
    visualizer = ActionVisualizer(utg_folder)
    
    results = []
    for i, sub in enumerate(plan.sub_tasks, 1):
        if not sub.matched_intent or not sub.actions:
            print(f"  跳过子任务 {i} (无匹配或无动作)")
            continue
        
        output_file = f"subtask_{i}_cluster_{sub.cluster_id}.png"
        output_full = os.path.join(output_path, output_file)
        
        print(f"\n  生成子任务 {i} 的可视化...")
        success = visualizer.visualize_actions(
            cluster_id=sub.cluster_id,
            matched_intent=sub.matched_intent,
            output_path=output_full
        )
        
        if success:
            results.append({
                "subtask_index": i,
                "cluster_id": sub.cluster_id,
                "sub_task": sub.sub_task,
                "matched_intent": sub.matched_intent,
                "num_actions": len(sub.actions),
                "visualization": output_full
            })
            print(f"    ✓ 已保存: {output_full}")
        else:
            print(f"    ✗ 生成失败")
    
    # 5. 保存结果摘要
    summary_path = os.path.join(output_path, "summary.json")
    summary = {
        "original_task": user_task,
        "num_subtasks": len(plan.sub_tasks),
        "num_visualized": len(results),
        "subtasks": results
    }
    
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 60)
    print(f"完成! 共生成 {len(results)} 个可视化结果")
    print(f"输出目录: {output_path}")
    print(f"摘要文件: {summary_path}")
    print("=" * 60)
    
    return results


def visualize_from_log_file(log_file_path: str, output_dir: str = None):
    """
    从日志文件生成可视化
    
    Args:
        log_file_path: 日志文件路径(.txt或.md)
        output_dir: 输出目录，默认为日志文件同目录下的output文件夹
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    utg_folder = os.path.join(base_dir, "utg", "NetEase Cloud Music")
    
    # 读取日志文件
    with open(log_file_path, "r", encoding="utf-8") as f:
        log_text = f.read()
    
    # 确定输出目录
    if output_dir is None:
        log_dir = os.path.dirname(log_file_path)
        output_dir = os.path.join(log_dir, "output_visualization")
    
    print(f"日志文件: {log_file_path}")
    print(f"输出目录: {output_dir}")
    
    # 生成可视化
    return visualize_from_log(log_text, utg_folder, output_dir)


if __name__ == "__main__":
    import sys
    
    # 支持命令行参数：从日志文件生成可视化
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
        output_dir = sys.argv[2] if len(sys.argv) > 2 else None
        
        print("=" * 80)
        print("从日志文件生成可视化")
        print("=" * 80)
        visualize_from_log_file(log_file, output_dir)
    else:
        # 默认测试：运行完整流程
        tasks = [
            "播放推荐歌曲并查看歌曲详情",
            "搜索'周杰伦'的歌曲并播放，然后添加到我的收藏夹",
        ]
        
        for i, task in enumerate(tasks, 1):
            print(f"\n\n{'#' * 80}")
            print(f"测试任务 {i}: {task}")
            print('#' * 80)
            
            output_dir = f"output/task_{i}"
            run_task_with_visualization(task, output_dir)
