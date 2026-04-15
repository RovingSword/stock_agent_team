# -*- coding: utf-8 -*-
"""
LLM 适配层基础类

定义统一的 LLM 调用接口，所有 Provider 都应继承此类。
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Iterator, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class LLMProviderType(Enum):
    """LLM Provider 类型枚举"""
    QWEN = "qwen"
    DEEPSEEK = "deepseek"
    ZHIPU = "zhipu"
    MOONSHOT = "moonshot"
    OPENAI_COMPATIBLE = "openai_compatible"
    OPENAI = "openai"


@dataclass
class LLMConfig:
    """LLM 配置类"""
    api_key: str = ""
    base_url: str = ""
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 2000
    timeout: int = 60
    max_retries: int = 3
    retry_delay: float = 1.0
    stream: bool = False
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatMessage:
    """聊天消息类"""
    role: str  # system, user, assistant
    content: str
    name: Optional[str] = None


@dataclass
class ChatCompletionResponse:
    """聊天完成响应类"""
    content: str
    model: str
    usage: Dict[str, int]
    raw_response: Optional[Dict[str, Any]] = None


class BaseLLMProvider(ABC):
    """
    LLM Provider 基类
    
    定义统一的 LLM 调用接口，所有具体的 Provider 实现都应继承此类。
    
    Attributes:
        config: LLM 配置
        provider_type: Provider 类型
    """
    
    def __init__(self, config: LLMConfig):
        """
        初始化 Provider
        
        Args:
            config: LLM 配置对象
        """
        self.config = config
        self.provider_type = self._get_provider_type()
        self._client = None
        logger.info(f"初始化 {self.provider_type} Provider，模型: {config.model}")
    
    @abstractmethod
    def _get_provider_type(self) -> LLMProviderType:
        """获取 Provider 类型"""
        pass
    
    @abstractmethod
    def _create_client(self):
        """创建底层客户端（延迟初始化）"""
        pass
    
    def _get_client(self):
        """获取客户端（延迟初始化）"""
        if self._client is None:
            self._client = self._create_client()
        return self._client
    
    def _retry_with_backoff(
        self, 
        func: Callable, 
        *args, 
        **kwargs
    ) -> Any:
        """
        带退避的重试机制
        
        Args:
            func: 要重试的函数
            *args: 函数参数
            **kwargs: 函数关键字参数
            
        Returns:
            函数执行结果
            
        Raises:
            最后一次失败的异常
        """
        last_exception = None
        
        for attempt in range(self.config.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (2 ** attempt)  # 指数退避
                    logger.warning(
                        f"请求失败 (尝试 {attempt + 1}/{self.config.max_retries}): {e}, "
                        f"{delay:.1f}秒后重试..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"请求最终失败: {e}")
        
        raise last_exception
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def chat_with_history(
        self, 
        messages: List[ChatMessage],
        **kwargs
    ) -> ChatCompletionResponse:
        """
        发送聊天请求（带历史记录）
        
        Args:
            messages: 消息列表，包含角色和内容
            **kwargs: 其他参数
            
        Returns:
            ChatCompletionResponse: 聊天响应
        """
        pass
    
    def chat_stream(
        self, 
        message: str, 
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Iterator[str]:
        """
        流式聊天请求
        
        Args:
            message: 用户消息
            system_prompt: 系统提示（可选）
            **kwargs: 其他参数
            
        Yields:
            str: 生成的文本片段
        """
        # 构建消息列表
        messages = []
        if system_prompt:
            messages.append(ChatMessage(role="system", content=system_prompt))
        messages.append(ChatMessage(role="user", content=message))
        
        # 调用流式接口
        for chunk in self._chat_stream_impl(messages, **kwargs):
            yield chunk
    
    @abstractmethod
    def _chat_stream_impl(
        self, 
        messages: List[ChatMessage],
        **kwargs
    ) -> Iterator[str]:
        """流式聊天的具体实现"""
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息
        
        Returns:
            Dict: 模型信息字典
        """
        pass
    
    def validate_config(self) -> bool:
        """
        验证配置是否有效
        
        Returns:
            bool: 配置是否有效
        """
        if not self.config.api_key:
            logger.error("API Key 未设置")
            return False
        if not self.config.model:
            logger.error("模型名称未设置")
            return False
        return True
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} model={self.config.model}>"
