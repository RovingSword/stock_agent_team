# -*- coding: utf-8 -*-
"""
LLM 适配层模块

支持多个国产大模型的统一调用接口。

支持的 Provider:
    - 通义千问 (Qwen)
    - DeepSeek
    - 智谱AI (Zhipu)
    - Moonshot
    - OpenAI 兼容接口

快速开始:
    >>> from llm import get_provider
    >>>
    >>> # 使用默认配置
    >>> provider = get_provider("qwen")
    >>> response = provider.chat("你好")
    >>> print(response.content)
    >>>
    >>> # 使用自定义配置
    >>> provider = get_provider(
    ...     "deepseek",
    ...     api_key="sk-xxxx",
    ...     model="deepseek-chat"
    ... )
    >>> response = provider.chat("解释一下什么是股票")
    >>> print(response.content)

环境变量配置:
    # 通义千问
    DASHSCOPE_API_KEY=your_api_key
    QWEN_MODEL=qwen-plus
    
    # DeepSeek
    DEEPSEEK_API_KEY=your_api_key
    DEEPSEEK_MODEL=deepseek-chat
    
    # 智谱AI
    ZHIPU_API_KEY=your_api_key
    ZHIPU_MODEL=glm-4
    
    # Moonshot
    MOONSHOT_API_KEY=your_api_key
    MOONSHOT_MODEL=moonshot-v1-8k
    
    # OpenAI 兼容
    OPENAI_API_KEY=your_api_key
    OPENAI_BASE_URL=http://localhost:8000/v1
    OPENAI_MODEL=gpt-3.5-turbo
"""

import logging

from .base_provider import (
    BaseLLMProvider,
    LLMConfig,
    ChatMessage,
    ChatCompletionResponse,
    LLMProviderType,
)

from .providers import (
    QwenProvider,
    DeepSeekProvider,
    ZhipuProvider,
    MoonshotProvider,
    OpenAICompatibleProvider,
    get_provider_class,
    get_provider_type_by_name,
)

from .llm_factory import (
    LLMFactory,
    get_factory,
    get_provider,
    create_provider,
)

# Mock Provider
from .providers import MockProvider

# 导出
__all__ = [
    # 版本
    "__version__",
    # 基础类
    "BaseLLMProvider",
    "LLMConfig",
    "ChatMessage",
    "ChatCompletionResponse",
    "LLMProviderType",
    # Provider 实现
    "QwenProvider",
    "DeepSeekProvider",
    "ZhipuProvider",
    "MoonshotProvider",
    "OpenAICompatibleProvider",
    "MockProvider",
    # 工厂函数
    "get_provider",
    "create_provider",
    "get_factory",
    "LLMFactory",
    # 工具函数
    "get_provider_class",
    "get_provider_type_by_name",
    "setup_logging",
]

# 配置日志
logging.getLogger(__name__).setLevel(logging.INFO)


def setup_logging(level: int = logging.INFO):
    """
    设置模块日志级别
    
    Args:
        level: 日志级别
    """
    logging.getLogger(__name__).setLevel(level)


__version__ = "1.0.0"
