import os
import json
from typing import Optional, List
from grounder import TIGGrounder, TIGNode
from planner import TIGPlanner, TIGEdge
from clients.vlm_client import VLMClient
from clients.llm_client import LLMClient


class TIGAgent:
    """
    TIG-based Agent: 使用任务意图图进行跨应用导航和任务执行
    """
    
    def __init__(self, tig_file_path: str, vlm_client: VLMClient = None, llm_client: LLMClient = None):
        """
        初始化TIG Agent
        
        Args:
            tig_file_path: TIG JSON文件路径
            vlm_client: 视觉语言模型客户端
            llm_client: LLM客户端
        """
        # 1. 初始化Grounder（会自动加载TIG数据）
        self.grounder = TIGGrounder(
            tig_path=tig_file_path,
            vlm_client=vlm_client,
            llm_client=llm_client
        )
        
        # 2. 初始化Planner（路径规划器，复用grounder的TIG数据）
        with open(tig_file_path, 'r', encoding='utf-8') as f:
            tig_data = json.load(f)
        
        # 构建TIGEdge对象列表
        tig_edges = [
            TIGEdge(
                source_id=e["source"],
                target_id=e["target"],
                action_signature=e["action"],
                cost=e.get("cost", 1.0)
            )
            for e in tig_data["edges"]
        ]
        
        self.planner = TIGPlanner(
            tig_nodes=self.grounder.tig_nodes,
            tig_edges=tig_edges,
            llm_client=llm_client
        )
        
        self.tig_file_path = tig_file_path

    def execute_task(self, app_driver, task_description: str, max_steps: int = 10, verbose: bool = True):
        """
        执行任务：支持自然语言描述（例如 "播放一首歌"）
        
        Args:
            app_driver: App驱动器（提供截图和控制接口）
            task_description: 自然语言任务描述
            max_steps: 最大执行步数
            verbose: 是否打印详细信息
        """
        print(f"🎯 Task: {task_description}")
        print(f"📁 TIG: {self.tig_file_path}\n")

        current_plan: Optional[List[TIGEdge]] = None
        plan_index = 0

        for step in range(max_steps):
            print(f"\n--- Step {step + 1}/{max_steps} ---")
            
            # --- Step 1: 感知与锚定 (Grounding) ---
            current_screenshot = app_driver.capture_screenshot()
            current_xml = app_driver.get_xml_hierarchy() if hasattr(app_driver, 'get_xml_hierarchy') else None
            
            # 将当前界面锚定到TIG节点
            current_tig_node = self.grounder.ground(
                screenshot_path=current_screenshot,
                xml_path=current_xml,
                verbose=verbose
            )
            
            if not current_tig_node:
                print("⚠️ Unknown state, triggering exploration to find a known anchor...")
                # TODO: 可以在这里回退到 ReAct 模式进行局部探索
                return False

            # --- Step 2: 全局路径规划 (High-Level Planning) ---
            # 如果没有当前计划或需要重新规划，生成新路径
            if current_plan is None or plan_index >= len(current_plan):
                print(f"\n🗺️ Planning path from current state...")
                current_plan = self.planner.plan_from_natural_language(
                    start_node_id=current_tig_node.id,
                    task_description=task_description,
                    verbose=verbose
                )
                
                if not current_plan:
                    print(f"❌ No path found from {current_tig_node.intent_label} to task goal")
                    return False
                
                plan_index = 0
                print(f"\n📋 Generated plan with {len(current_plan)} steps")

            # --- Step 3: 检查是否已到达目标 ---
            # 如果计划已执行完，说明到达目标
            if plan_index >= len(current_plan):
                print(f"\n✅ Success! Task '{task_description}' completed!")
                return True

            # --- Step 4: 执行下一步抽象动作 (Action Execution) ---
            next_edge = current_plan[plan_index]
            print(f"\n🔨 Executing step {plan_index + 1}/{len(current_plan)}: {next_edge.action_signature}")
            print(f"   {next_edge.source_id} → {next_edge.target_id}")
            
            success = self._execute_abstract_action(app_driver, next_edge.action_signature)
            
            if not success:
                print("❌ Action execution failed, re-grounding and replanning...")
                current_plan = None  # 触发重新规划
                continue
            
            plan_index += 1
            
            # 等待UI更新
            import time
            time.sleep(2)
        
        print(f"\n❌ Failed to complete task within {max_steps} steps")
        return False
    
    def _execute_abstract_action(self, driver, action_sig: str) -> bool:
        """
        执行抽象动作
        
        将抽象的 "Search(query)" 翻译成具体的UI操作
        
        Args:
            driver: App驱动器
            action_sig: 动作签名，如 "Navigate(Settings)"
            
        Returns:
            是否执行成功
        """
        # TODO: 使用 LLM 或语义匹配找到当前页面对应的 UI 元素并操作
        print(f"🚧 TODO: Ground action '{action_sig}' to UI element and execute")
        
        # 临时实现：返回True以继续流程
        return True


def main():
    """测试TIG Agent"""
    import argparse
    
    parser = argparse.ArgumentParser(description='TIG Agent for task execution')
    parser.add_argument('--tig', type=str, required=True,
                        help='Path to TIG JSON file')
    parser.add_argument('--task', type=str, required=True,
                        help='Natural language task description (e.g., "播放一首歌")')
    parser.add_argument('--screenshot', type=str, required=True,
                        help='Path to current screenshot (for testing)')
    parser.add_argument('--max_steps', type=int, default=10,
                        help='Maximum steps to execute (default: 10)')
    parser.add_argument('--verbose', action='store_true',
                        help='Print verbose output')
    
    args = parser.parse_args()
    
    # 创建一个简单的模拟驱动器用于测试
    class MockDriver:
        def __init__(self, screenshot_path):
            self.screenshot_path = screenshot_path
            
        def capture_screenshot(self):
            return self.screenshot_path
        
        def get_xml_hierarchy(self):
            return None
    
    # 初始化Agent
    agent = TIGAgent(tig_file_path=args.tig)
    
    # 创建模拟驱动器
    driver = MockDriver(args.screenshot)
    
    # 执行任务
    success = agent.execute_task(
        app_driver=driver,
        task_description=args.task,
        max_steps=args.max_steps,
        verbose=args.verbose
    )
    
    if success:
        print("\n🎉 Task completed successfully!")
    else:
        print("\n😞 Task failed")


if __name__ == '__main__':
    main()