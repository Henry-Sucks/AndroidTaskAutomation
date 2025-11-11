import json
import os
from typing import Dict, Any, Tuple, Optional
from pathlib import Path

class UTGCluster:
    """
    UTG聚类处理类，用于对states和events进行聚类分析
    """
    
    def __init__(self, input_folder: str):
        """
        初始化UTG聚类器
        
        Args:
            input_folder: 包含states和events子文件夹的输入目录
        """
        self.input_folder = Path(input_folder)
        self.states_folder = self.input_folder / "states"
        self.events_folder = self.input_folder / "events"
        self.output_folder = Path(f"{input_folder}_clustered")
        
        # 聚类相关属性
        self.state_clusters: Dict[str, str] = {}  # content_free_key -> cluster_id映射
        self.state_id_to_cluster: Dict[str, str] = {}  # state_id -> cluster_id映射
        self.cluster_counter = 0  # 聚类ID计数器
        
        # 验证输入文件夹结构
        self._validate_input_structure()
    
    def _validate_input_structure(self):
        """
        验证输入文件夹结构是否正确
        
        Raises:
            FileNotFoundError: 如果必要的文件夹不存在
        """
        if not self.input_folder.exists():
            raise FileNotFoundError(f"输入文件夹不存在: {self.input_folder}")
        if not self.states_folder.exists():
            raise FileNotFoundError(f"states文件夹不存在: {self.states_folder}")
        if not self.events_folder.exists():
            raise FileNotFoundError(f"events文件夹不存在: {self.events_folder}")
    
    def _create_output_structure(self):
        """
        创建输出文件夹结构
        """
        self.output_folder.mkdir(exist_ok=True)
        (self.output_folder / "states").mkdir(exist_ok=True)
        (self.output_folder / "events").mkdir(exist_ok=True)
    
    def _load_state_file(self, state_file_path: Path) -> Optional[Dict[str, Any]]:
        """
        加载state JSON文件
        
        Args:
            state_file_path: state文件路径
            
        Returns:
            解析后的state数据字典，如果文件无效则返回None
        """
        try:
            with open(state_file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    print(f"警告: 空文件 {state_file_path}")
                    return None
                
                data = json.loads(content)
                
                # 验证必要的属性
                if not isinstance(data, dict):
                    print(f"警告: 文件格式无效 {state_file_path} - 不是有效的JSON对象")
                    return None
                
                # 检查必要的state属性
                required_fields = ['state_str']
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    print(f"警告: 文件 {state_file_path} 缺少必要属性: {missing_fields}")
                    # 为缺少的字段提供默认值
                    for field in missing_fields:
                        if field == 'state_str':
                            data[field] = f"unknown_state_{state_file_path.stem}"
                
                return data
                
        except json.JSONDecodeError as e:
            print(f"错误: JSON解析失败 {state_file_path}: {e}")
            return None
        except Exception as e:
            print(f"错误: 读取文件失败 {state_file_path}: {e}")
            return None
    
    def _load_event_file(self, event_file_path: Path) -> Optional[Dict[str, Any]]:
        """
        加载event JSON文件
        
        Args:
            event_file_path: event文件路径
            
        Returns:
            解析后的event数据字典，如果文件无效则返回None
        """
        try:
            with open(event_file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    print(f"警告: 空文件 {event_file_path}")
                    return None
                
                data = json.loads(content)
                
                # 验证必要的属性
                if not isinstance(data, dict):
                    print(f"警告: 文件格式无效 {event_file_path} - 不是有效的JSON对象")
                    return None
                
                # 检查必要的event属性
                required_fields = ['event_str', 'start_state', 'stop_state']
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    print(f"警告: 文件 {event_file_path} 缺少必要属性: {missing_fields}")
                    # 为缺少的字段提供默认值
                    for field in missing_fields:
                        if field == 'event_str':
                            data[field] = f"unknown_event_{event_file_path.stem}"
                        elif field in ['start_state', 'stop_state']:
                            data[field] = "unknown_state"
                
                return data
                
        except json.JSONDecodeError as e:
            print(f"错误: JSON解析失败 {event_file_path}: {e}")
            return None
        except Exception as e:
            print(f"错误: 读取文件失败 {event_file_path}: {e}")
            return None
    
    def state_clustering(self, state_data: Dict[str, Any]) -> str:
        """
        对单个state进行聚类分析
        
        Args:
            state_data: state的JSON数据
            
        Returns:
            该state所属的cluster_id
        """
        # 获取用于聚类的键
        content_free_key = state_data.get("state_str_content_free", state_data.get("state_str", "unknown"))
        
        # 如果还没有为这个键分配聚类，则创建新的聚类
        if content_free_key not in self.state_clusters:
            cluster_id = content_free_key
            self.state_clusters[content_free_key] = cluster_id
            self.cluster_counter += 1
        else:
            cluster_id = self.state_clusters[content_free_key]
        
        # 同时维护state_id到cluster_id的映射
        state_id = state_data.get("state_str", "")
        if state_id:
            self.state_id_to_cluster[state_id] = cluster_id
            print(f"映射添加: {state_id} -> {cluster_id}")
        
        return cluster_id
    
    def event_clustering(self, event_data: Dict[str, Any]) -> Tuple[str, str]:
        """
        对单个event进行聚类分析，根据start_state和stop_state获取对应的cluster
        
        Args:
            event_data: event的JSON数据
            
        Returns:
            (start_cluster, stop_cluster)元组
        """
        start_state = event_data.get("start_state", "")
        stop_state = event_data.get("stop_state", "")
        
        # 根据state_id查找对应的cluster_id
        start_cluster = self._get_cluster_by_state_id(start_state)
        stop_cluster = self._get_cluster_by_state_id(stop_state)
        
        print(f"Event聚类: {start_state} -> {start_cluster}, {stop_state} -> {stop_cluster}")
        
        return start_cluster, stop_cluster
    
    def _get_cluster_by_state_id(self, state_id: str) -> str:
        """
        根据state_id获取对应的cluster_id
        
        Args:
            state_id: 状态ID
            
        Returns:
            对应的cluster_id，如果找不到则返回"unknown_cluster"
        """
        # 直接从映射中查找
        if state_id in self.state_id_to_cluster:
            return self.state_id_to_cluster[state_id]
        
        # 如果直接映射找不到，尝试通过加载对应的state文件来建立映射
        state_file_pattern = f"state_*{state_id}*.json"
        matching_files = list(self.states_folder.glob(state_file_pattern))
        
        if not matching_files:
            # 尝试更宽松的匹配
            for state_file in self.states_folder.glob("state_*.json"):
                state_data = self._load_state_file(state_file)
                if state_data and state_data.get("state_str") == state_id:
                    # 找到匹配的state文件，进行聚类
                    cluster_id = self.state_clustering(state_data)
                    return cluster_id
        else:
            # 找到匹配的文件，加载并进行聚类
            state_data = self._load_state_file(matching_files[0])
            if state_data:
                cluster_id = self.state_clustering(state_data)
                return cluster_id
        
        print(f"警告: 未找到state_id '{state_id}' 对应的聚类")
        return "unknown_cluster"
    
    def _process_states(self):
        """
        处理所有state文件并生成聚类结果
        """
        state_files = list(self.states_folder.glob("state_*.json"))
        processed_count = 0
        skipped_count = 0
        
        print(f"开始处理 {len(state_files)} 个state文件...")
        
        for state_file in state_files:
            # 加载state数据
            state_data = self._load_state_file(state_file)
            
            # 跳过无效文件
            if state_data is None:
                skipped_count += 1
                print(f"跳过无效的state文件: {state_file}")
                continue
            
            # 进行聚类
            cluster_id = self.state_clustering(state_data)
            
            # 生成输出数据
            output_data = {
                "state_str": state_data.get("state_str", ""),
                "state_cluster_id": cluster_id
            }
            
            # 保存到输出文件
            output_file = self.output_folder / "states" / state_file.name
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            processed_count += 1
        
        print(f"States处理完成: 成功处理 {processed_count} 个文件，跳过 {skipped_count} 个无效文件")
        print(f"建立了 {len(self.state_id_to_cluster)} 个state_id映射")
    
    def _process_events(self):
        """
        处理所有event文件并生成聚类结果
        """
        event_files = list(self.events_folder.glob("event_*.json"))
        processed_count = 0
        skipped_count = 0
        
        print(f"开始处理 {len(event_files)} 个event文件...")
        
        for event_file in event_files:
            # 加载event数据
            event_data = self._load_event_file(event_file)
            
            # 跳过无效文件
            if event_data is None:
                skipped_count += 1
                print(f"跳过无效的event文件: {event_file}")
                continue
            
            # 进行聚类
            start_cluster, stop_cluster = self.event_clustering(event_data)
            
            # 生成输出数据
            output_data = {
                "event_str": event_data.get("event_str", ""),
                "start_state": event_data.get("start_state", ""),
                "stop_state": event_data.get("stop_state", ""),
                "start_cluster": start_cluster,
                "stop_cluster": stop_cluster
            }
            
            # 保存到输出文件
            output_file = self.output_folder / "events" / event_file.name
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            processed_count += 1
        
        print(f"Events处理完成: 成功处理 {processed_count} 个文件，跳过 {skipped_count} 个无效文件")
    
    def process_clustering(self):
        """
        执行完整的聚类处理流程
        """
        print(f"开始处理UTG聚类: {self.input_folder}")
        
        # 创建输出文件夹结构
        self._create_output_structure()
        
        # 先处理states，建立聚类映射
        print("处理states聚类...")
        self._process_states()
        
        # 再处理events，使用已建立的聚类映射
        print("处理events聚类...")
        self._process_events()
        
        print(f"聚类处理完成，结果保存到: {self.output_folder}")
        print(f"共生成 {self.cluster_counter} 个聚类")

# 使用示例
if __name__ == "__main__":
    # 使用示例
    input_folder = r"c:\Projects\AndroidTaskAutomation\2_utg_clustering\utg\original_greedy_dfs_20251106_160351"
    
    clusterer = UTGCluster(input_folder)
    clusterer.process_clustering()