# -*- coding: utf-8 -*-
"""
Moonshot (月之暗面) Provider

Moonshot 大模型适配器，使用 OpenAI 兼容接口。
"""

import os
import logging
from typing import List, Dict, Any, Iterator, Optional

from openai import OpenAI

from ..base_provider import (
    BaseLLMProvider, 
    LLMConfig, 
    ChatMessage, 
    ChatCompletionResponse,
    LLMProviderType
)

logger = logging.getLogger(__name__)


class MoonshotProvider(BaseLLMProvider):
    """
    Moonshot Provider
    
    使用 Moonshot API，兼容 OpenAI 接口格式。
    
    API地址: https://api.moonshot.cn/v1
    
    环境变量:
        MOONSHOT_API_KEY: Moonshot API Key
    """
    
    # Moonshot 默认模型
    DEFAULT_MODELS = [
        "moonshot-v1-8k",
        "moonshot-v1-32k",
        "moonshot-v1-128k",
    ]
    
    # API 基础地址
    BASE_URL = "https://api.moonshot.cn/v1"
    
    def __init__(self, config: Optional[LLMConfig] = None):
        """
        初始化 Moonshot Provider
        
        Args:
            config: LLM 配置，如果为 None 则从环境变量读取
        """
        if config is None:
            config = self._load_config_from_env()
        super().__init__(config)
    
    def _load_config_from_env(self) -> LLMConfig:
        """从环境变量加载配置"""
        api_key = os.environ.get("MOONSHOT_API_KEY", "")
        
        return LLMConfig(
            api_key=api_key,
            base_url=self.BASE_URL,
            model=os.environ.get("MOONSHOT_MODEL", "moonshot-v1-8k"),
            temperature=float(os.environ.get("MOONSHOT_TEMPERATURE", "0.7")),
            max_tokens=int(os.environ.get("MOONSHOT_MAX_TOKENS", "2000")),
            timeout=int(os.environ.get("MOONSHOT_TIMEOUT", "60")),
            max_retries=int(os.environ.get("MOONSHOT_MAX_RETRIES", "3")),
        )
    
    def _get_provider_type(self) -> LLMProviderType:
        return LLMProviderType.MOONSHOT
    
    def _create_client(self):
        """创建 OpenAI 客户端"""
        return OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout,
        )
    
    def _build_messages(
        self, 
        message: str, 
        system_prompt: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """构建消息列表"""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})
        
        return messages
    
    def _build_messages_from_chat_messages(
        self, 
        messages: List[ChatMessage]
    ) -> List[Dict[str, str]]:
        """从 ChatMessage 列表构建 API 消息"""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
    
    def chat(
        self, 
        message: str, 
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> ChatCompletionResponse:
        """
        发送聊天请求（单轮对话）
        
        Args:
            message: 用户消息
            system_prompt: 系统提示（可选）
            **kwargs: 其他参数
            
        Returns:
            ChatCompletionResponse: 聊天响应
        """
        messages = self._build_messages(message, system_prompt)
        return self._do_chat(messages, **kwargs)
    
    def chat_with_history(
        self, 
        messages: List[ChatMessage],
        **kwargs
    ) -> ChatCompletionResponse:
        """
        发送聊天请求（带历史记录）
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            ChatCompletionResponse: 聊天响应
        """
        api_messages = self._build_messages_from_chat_messages(messages)
        return self._do_chat(api_messages, **kwargs)
    
    def _do_chat(
        self, 
        messages: List[Dict[str, str]],
        **kwargs
    ) -> ChatCompletionResponse:
        """执行聊天请求"""
        def _request():
            client = self._get_client()
            
            params = {
                "model": kwargs.get("model", self.config.model),
                "messages": messages,
                "temperature": kwargs.get("temperature", self.config.temperature),
                "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            }
            
            # 添加可选参数
            if kwargs.get("top_p"):
                params["top_p"] = kwargs["top_p"]
            if kwargs.get("stop"):
                params["stop"] = kwargs["stop"]
            
            params.update(self.config.extra_params)
            
            logger.debug(f"发送请求到 Moonshot: {params['model']}")
            
            response = client.chat.completions.create(**params)
            
            return ChatCompletionResponse(
                content=response.choices[0].message.content,
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                raw_response=response.model_dump() if hasattr(response, 'model_dump') else None
            )
        
        return self._retry_with_backoff(_request)
    
    def _chat_stream_impl(
        self, 
        messages: List[ChatMessage],
        **kwargs
    ) -> Iterator[str]:
        """流式聊天的具体实现"""
        client = self._get_client()
        api_messages = self._build_messages_from_chat_messages(messages)
        
        params = {
            "model": kwargs.get("model", self.config.model),
            "messages": api_messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "stream": True,
        }
        
        logger.debug(f"发送流式请求到 Moonshot: {params['model']}")
        
        stream = client.chat.completions.create(**params)
        
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息
        
        Returns:
            Dict: 模型信息字典
        """
        return {
            "provider": "moonshot",
            "provider_name": "Moonshot",
            "base_url": self.config.base_url,
            "model": self.config.model,
            "available_models": self.DEFAULT_MODELS,
            "features": [
                "chat",
                "stream_chat",
                "long_context"  # 支持 128k 上下文
            ]
        }
    
    @classmethod
    def get_default_model(cls) -> str:
        """获取默认模型"""
        return cls.DEFAULT_MODELS[0]
