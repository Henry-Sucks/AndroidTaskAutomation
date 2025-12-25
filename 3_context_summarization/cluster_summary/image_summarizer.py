from clients.vlm_client import VLMClient
from .prompts import VLM_DISCRIMINATIVE_PROMPT
import json

class ImageSummarizer:
    """
    负责单张截图的语义提取，强调'差异化'特征。
    """

    def __init__(self, model="qwen3-vl-flash"):
        self.client = VLMClient(model=model)

    def summarize(self, package_name: str, image_path: str, extra_context: str = None) -> dict:
        """
        生成带有 Scope 和 Unique Features 的单图摘要。
        """
        try:
            # 1. 构造 Prompt，注入 App 名称上下文
            full_prompt = VLM_DISCRIMINATIVE_PROMPT + f"\nApp Context: {package_name}"
            
            if extra_context:
                full_prompt += f"\nNote: {extra_context}"
            
            full_prompt += "\n\nPlease analyze the screenshot and provide a JSON response following the format above."

            # 2. 调用 VLM 进行图像分析
            response = self.client.run(prompt=full_prompt, image_url=image_path)
            
            # 3. 处理响应内容
            if isinstance(response, dict) and 'content' in response:
                content = response['content']
            else:
                content = str(response)
            
            # 4. 尝试解析JSON响应
            try:
                # 尝试直接解析JSON
                result = json.loads(content)
                
                # 验证必要字段是否存在
                required_fields = ["page_title", "primary_function", "functional_scope", "unique_visual_features", "visible_actions"]
                for field in required_fields:
                    if field not in result:
                        result[field] = "Not provided"
                        
                return result
                
            except json.JSONDecodeError:
                # 如果无法解析为JSON，尝试从文本中提取信息
                return self._extract_info_from_text(content, package_name)
                
        except Exception as e:
            print(f"VLM调用失败: {e}")
            return self._create_error_response(str(e), package_name, image_path)

    def _extract_info_from_text(self, content: str, package_name: str) -> dict:
        """
        从非JSON文本响应中提取信息
        """
        # 基于关键词提取信息的简单策略
        lines = content.split('\n')
        
        result = {
            "page_title": "Unknown Screen",
            "primary_function": "Screen interaction",
            "functional_scope": f"{package_name} functionality",
            "unique_visual_features": "Visual elements visible in screenshot",
            "visible_actions": []
        }
        
        # 尝试从文本中提取信息
        for line in lines:
            line = line.strip()
            if line:
                # 查找可能的UI元素或功能描述
                if any(keyword in line.lower() for keyword in ['button', 'click', 'tap', 'menu', 'search', 'input']):
                    result["visible_actions"].append(line[:50])  # 截断长文本
        
        # 将原始响应作为备用信息
        result["raw_response"] = content[:200] if len(content) > 200 else content
        
        return result

    def _create_error_response(self, error_msg: str, package_name: str, image_path: str) -> dict:
        """
        创建错误响应
        """
        return {
            "page_title": "Analysis Error",
            "primary_function": "Failed to analyze",
            "functional_scope": f"Error analyzing {package_name} screen",
            "unique_visual_features": f"Error: {error_msg}",
            "visible_actions": [],
            "error": error_msg,
            "image_path": image_path
        }