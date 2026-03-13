import logging
from abc import ABC, abstractmethod
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class AIClient(ABC):
    @abstractmethod
    def generate_response(self, prompt: str) -> Optional[str]:
        pass

class OpenAIClient(AIClient):
    def __init__(self, api_key: str, base_url: str, model: str, system_prompt: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.system_prompt = system_prompt
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        return self._client

    def generate_response(self, prompt: str) -> Optional[str]:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API 调用失败: {e}")
            return None

class DeepSeekClient(AIClient):
    def __init__(self, api_key: str, base_url: str, model: str, system_prompt: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.system_prompt = system_prompt
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        return self._client

    def generate_response(self, prompt: str) -> Optional[str]:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"DeepSeek API 调用失败: {e}")
            return None

class SiliconFlowClient(AIClient):
    def __init__(self, api_key: str, base_url: str, model: str, system_prompt: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.system_prompt = system_prompt
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        return self._client

    def generate_response(self, prompt: str) -> Optional[str]:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"SiliconFlow API 调用失败: {e}")
            return None

class GeminiClient(AIClient):
    def __init__(self, api_key: str, model: str, system_prompt: str):
        self.api_key = api_key
        self.model = model
        self.system_prompt = system_prompt
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(self.model)
        return self._client

    def generate_response(self, prompt: str) -> Optional[str]:
        try:
            response = self.client.generate_content(
                f"{self.system_prompt}\n\n用户问题: {prompt}"
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API 调用失败: {e}")
            return None

def create_ai_client(provider: str, config: dict) -> Optional[AIClient]:
    providers = {
        'openai': OpenAIClient,
        'deepseek': DeepSeekClient,
        'siliconflow': SiliconFlowClient,
        'gemini': GeminiClient
    }
    
    provider_lower = provider.lower()
    if provider_lower not in providers:
        logger.error(f"不支持的 AI 提供商: {provider}")
        return None
    
    client_class = providers[provider_lower]
    system_prompt = config.get('system_prompt', '你是一个友好的AI助手，帮助回答用户的问题。请用中文回复。')
    
    if provider_lower == 'gemini':
        return client_class(
            api_key=config.get('api_key'),
            model=config.get('model'),
            system_prompt=system_prompt
        )
    else:
        return client_class(
            api_key=config.get('api_key'),
            base_url=config.get('base_url'),
            model=config.get('model'),
            system_prompt=system_prompt
        )
