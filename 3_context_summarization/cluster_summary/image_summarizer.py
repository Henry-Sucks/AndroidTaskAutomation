# summarizer.py

from clients.vlm_client import VLMClient

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

    def summarize(self, package_name, image_url_or_path, extra_note=None, enable_thinking=False):
        """
        增强：将 package_name 加入 Prompt，提供 App 上下文。
        """

        # ---- 添加 App 名称信息 ----
        app_context_prompt = f"\nThis screenshot comes from the mobile application: **{package_name}**.\n"
        prompt = IMAGE_PROMPT_TEMPLATE + app_context_prompt

        # 附加说明
        if extra_note:
            prompt += f"\nAdditional note: {extra_note}\n"

        # 调用视觉模型
        output = self.client.run(
            prompt=prompt,
            image_url=image_url_or_path,
            enable_thinking=enable_thinking
        )

        return output["content"]
