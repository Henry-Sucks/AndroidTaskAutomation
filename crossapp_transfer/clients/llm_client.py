import os
from openai import OpenAI
from clients.config import DEEPSEEK_API_KEY
class LLMClient:
    def __init__(self, api_key=None, base_url=None, model="deepseek-chat"):
        """
        初始化LLM客户端（纯文本模型）
        
        Args:
            api_key: API密钥，如果为None则尝试从环境变量获取
            base_url: API基础URL
            model: 模型名称
        """
        self.model = model
        
        # 根据模型设置默认的base_url
        if base_url is None:
            if "deepseek" in model.lower():
                self.base_url = "https://api.deepseek.com"
            elif "qwen" in model.lower():
                self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            else:
                # 默认使用DeepSeek
                self.base_url = "https://api.deepseek.com"
        else:
            self.base_url = base_url
            
        # 设置API密钥
        if api_key is None:
            if "deepseek" in model.lower():
                self.api_key = DEEPSEEK_API_KEY
                if self.api_key is None:
                    raise ValueError("DeepSeek API密钥未提供，请设置DEEPSEEK_API_KEY环境变量")
            elif "qwen" in model.lower():
                self.api_key = os.environ.get("DASHSCOPE_API_KEY")
            else:
                self.api_key = os.environ.get("DEEPSEEK_API_KEY")
                if self.api_key is None:
                    raise ValueError("API密钥未提供，请设置相应的环境变量")
        else:
            self.api_key = api_key
            
        # 初始化OpenAI客户端
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat(self, messages, temperature=0.7, max_tokens=None, stream=False):
        """
        使用消息列表进行聊天
        
        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "Hello"}]
            temperature: 生成文本的随机性，0-1之间，值越大随机性越强
            max_tokens: 最大生成长度
            stream: 是否使用流式输出
            
        Returns:
            str: 模型回复
        """
        try:
            # 准备请求参数
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "stream": stream
            }
            
            # 如果有最大令牌数限制，则添加
            if max_tokens:
                params["max_tokens"] = max_tokens
                
            completion = self.client.chat.completions.create(**params)
            
            if stream:
                # 流式输出处理
                full_response = ""
                for chunk in completion:
                    if chunk.choices[0].delta.content is not None:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        print(content, end="", flush=True)
                return full_response
            else:
                # 非流式输出
                return completion.choices[0].message.content
                
        except Exception as e:
            print(f"API调用错误: {e}")
            return ""

    def run(self, prompt, system_prompt=None, temperature=0.7, max_tokens=None, stream=False):
        """
        简化接口：使用单轮对话
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 生成文本的随机性
            max_tokens: 最大生成长度
            stream: 是否使用流式输出
            
        Returns:
            str: 模型回复
        """
        messages = []
        
        # 添加系统提示
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
            
        # 添加用户消息
        messages.append({"role": "user", "content": prompt})
        
        return self.chat(messages, temperature, max_tokens, stream)
    
    def multi_turn_chat(self, conversation_history, temperature=0.7, max_tokens=None, stream=False):
        """
        多轮对话接口
        
        Args:
            conversation_history: 完整的对话历史
            temperature: 生成文本的随机性
            max_tokens: 最大生成长度
            stream: 是否使用流式输出
            
        Returns:
            str: 模型回复
        """
        return self.chat(conversation_history, temperature, max_tokens, stream)
    
    def get_embedding(self, text, model=None, dimensions=1024):
        """
        获取文本的embedding向量
        
        支持多种embedding模型：
        - DashScope (阿里云): text-embedding-v4, text-embedding-v3
        - OpenAI: text-embedding-3-small, text-embedding-ada-002
        
        Args:
            text: 输入文本或文本列表
            model: embedding模型名称，如果为None则根据base_url自动选择
            dimensions: 向量维度（仅部分模型支持）
            
        Returns:
            numpy array: embedding向量
        """
        import numpy as np
        
        # 自动选择embedding模型
        if model is None:
            if "dashscope" in self.base_url.lower():
                model = "text-embedding-v4"
            elif "deepseek" in self.base_url.lower():
                # DeepSeek不支持embedding，返回None
                return None
            else:
                model = "text-embedding-3-small"
        
        try:
            # 创建embedding客户端（使用相同的配置）
            embedding_client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            
            # 调用embedding API
            params = {
                "model": model,
                "input": text,
                "encoding_format": "float"
            }
            
            # 只有部分模型支持dimensions参数
            if model in ["text-embedding-v4", "text-embedding-v3", "text-embedding-3-small"]:
                params["dimensions"] = dimensions
            
            response = embedding_client.embeddings.create(**params)
            
            # 返回第一个结果的embedding
            embedding = response.data[0].embedding
            return np.array(embedding, dtype=np.float32)
            
        except Exception as e:
            print(f"Embedding API调用错误: {e}")
            return None