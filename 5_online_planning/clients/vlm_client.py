import base64
import os
from openai import OpenAI
from clients.config import QWEN_VLM_API_KEY

class VLMClient:
    def __init__(self, api_key=None, base_url=None, model="qwen3-vl-flash"):
        self.api_key = api_key or QWEN_VLM_API_KEY
        self.base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.model = model
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _is_local_file(self, path):
        """检查是否为本地文件路径"""
        return os.path.exists(path) and os.path.isfile(path)

    def _image_to_base64(self, image_path):
        """将本地图片转换为base64编码"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            raise ValueError(f"无法读取图片文件: {e}")

    def run(self, prompt, image_url=None, enable_thinking=False, thinking_budget=81920):
        messages = []

        # 如果包含图片
        if image_url:
            # 检查是本地文件还是URL
            if self._is_local_file(image_url):
                # 本地文件：转换为base64
                base64_image = self._image_to_base64(image_url)
                image_content = {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    },
                }
            else:
                # 远程URL：直接使用
                image_content = {
                    "type": "image_url",
                    "image_url": {"url": image_url},
                }
            
            messages.append({
                "role": "user",
                "content": [
                    image_content,
                    {"type": "text", "text": prompt},
                ],
            })
        else:
            messages.append({"role": "user", "content": prompt})

        # 发送请求
        extra_body = {}
        if enable_thinking:
            extra_body = {
                "enable_thinking": True,
                "thinking_budget": thinking_budget
            }

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=False,
                extra_body=extra_body,
            )

            # 兼容 enable_thinking 的输出
            reply = completion.choices[0].message

            result = {
                "content": reply.content if hasattr(reply, 'content') else "",
                "reasoning": getattr(reply, 'reasoning_content', "") if enable_thinking else None
            }

            return result
            
        except Exception as e:
            print(f"API调用错误: {e}")
            return {"content": "", "reasoning": None}
        
        
# 示例用法
if __name__ == "__main__":
    client = VLMClient()
    
    # 使用本地文件路径
    output = client.run(
        prompt="Analyze this screenshot.",
        image_url=r"C:\Projects\AndroidTaskAutomation\3_context_summarization\utg\sata-org.wikipedia-ape-sata-running-minutes-15_utg\states\s0065.png",
        enable_thinking=True
    )
    
    print("=== Output ===")
    print(output["content"])
    if output["reasoning"]:
        print("\n=== Reasoning ===")
        print(output["reasoning"])



