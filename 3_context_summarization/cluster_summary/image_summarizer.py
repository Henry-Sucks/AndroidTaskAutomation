# summarizer.py

from clients.vlm_client import VLMClient

# 固定 Prompt 模板 —— 已根据你的要求写好
IMAGE_PROMPT_TEMPLATE = """
You are a UI Perception Specialist. Your goal is to analyze a mobile app screenshot and describe its **functional affordance** concisely.
Do not describe colors or styles. Focus on:
1. **Main Header/Title**: What is the page name?
2. **Primary Action**: What is the main thing a user can do here? (e.g., "Enter password", "Select a date", "View list").
3. **State**: Is there a specific state? (e.g., "Loading", "Empty State", "Editing Mode").

[Image Attachment]

Analyze this screenshot.
Output a JSON object:
{
  "page_title": "String (detected header)",
  "primary_function": "String (e.g., 'User profile settings')",
  "key_elements": ["List of top 3 most important button labels or input fields"],
  "visual_clues": "String (Any icons or states not visible in text, e.g., 'Trash icon indicates delete mode', 'Toggle is ON')"
}
"""

class ImageSummarizer:
    """
    负责对单张 UI 截图生成功能性描述。
    """

    def __init__(self, model="qwen3-vl-flash"):
        self.client = VLMClient(model=model)

    def summarize(self, image_url_or_path, extra_note=None, enable_thinking=False):
        """
        调用视觉大模型，对图片进行 UI 功能分析。
        
        参数：
            image_url_or_path: 支持 URL 或 data:image;base64、本地路径（如果 VLMClient 支持）
            extra_note: 附加说明，如 "Point type: entry_point"
            enable_thinking: 是否启用模型思考
        
        返回：
            一个字符串（通常为 JSON 文本）
        """

        # 附加信息，如果有的话
        if extra_note:
            prompt = IMAGE_PROMPT_TEMPLATE + f"\n\nAdditional note: {extra_note}\n"
        else:
            prompt = IMAGE_PROMPT_TEMPLATE

        output = self.client.run(
            prompt=prompt,
            image_url=image_url_or_path,
            enable_thinking=enable_thinking
        )

        return output["content"]
    

class 