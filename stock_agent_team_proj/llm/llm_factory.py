# -*- coding: utf-8 -*-
"""
LLM 工厂模块

使用工厂模式和单例模式管理 LLM Provider 的创建和访问。
"""

import logging
import threading
from typing import Optional, Dict, Any

from .base_provider import BaseLLMProvider, LLMConfig, LLMProviderType
from .providers import (
    get_provider_class,
    get_provider_type_by_name,
    QwenProvider,
    DeepSeekProvider,
    ZhipuProvider,
    MoonshotProvider,
    OpenAICompatibleProvider,
)

logger = logging.getLogger(__name__)


class LLMFactory:
    """
    LLM Provider 工厂类
    
    使用单例模式管理 Provider 实例，确保同一配置只会创建一个实例。
    
    Usage:
        # 方式1: 使用工厂函数（推荐）
        provider = get_provider("qwen")
        
        # 方式2: 使用工厂类
        factory = LLMFactory()
        provider = factory.create_provider("deepseek")
        
        # 方式3: 直接创建 Provider
        config = LLMConfig(api_key="xxx", model="qwen-plus")
        provider = QwenProvider(config)
    """
    
    _instance: Optional["LLMFactory"] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """单例模式：确保只有一个工厂实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化工厂"""
        if self._initialized:
            return
        self._providers: Dict[str, BaseLLMProvider] = {}
        self._config_lock = threading.Lock()
        self._initialized = True
        logger.info("LLM Factory 初始化完成")
    
    def create_provider(
        self, 
        provider_name: str,
        config: Optional[LLMConfig] = None,
        **kwargs
    ) -> BaseLLMProvider:
        """
        创建或获取 Provider 实例
        
        Args:
            provider_name: Provider 名称 (qwen, deepseek, zhipu, moonshot, openai_compatible)
            config: 可选的配置对象，如果为 None 则使用默认配置
            **kwargs: 直接传入的配置参数
            
        Returns:
            BaseLLMProvider: Provider 实例
            
        Raises:
            ValueError: 不支持的 Provider 类型
            RuntimeError: Provider 创建失败
        """
        # 生成唯一键
        config_key = self._generate_config_key(provider_name, config, **kwargs)
        
        # 检查是否已存在
        with self._config_lock:
            if config_key in self._providers:
                logger.debug(f"复用已有 Provider: {config_key}")
                return self._providers[config_key]
        
        # 创建新实例
        try:
            # Mock Provider 特殊处理
            if provider_name.lower() in ("mock", "default"):
                from .providers import MockProvider
                provider = MockProvider(config)
                with self._config_lock:
                    self._providers[config_key] = provider
                logger.info(f"创建 Mock Provider: {provider}")
                return provider
            
            provider_type = get_provider_type_by_name(provider_name)
            provider_class = get_provider_class(provider_type)
            
            if provider_class is None:
                raise ValueError(f"不支持的 Provider 类型: {provider_name}")
            
            # 构建配置
            if config is None:
                config = self._build_config(provider_name, **kwargs)
            
            # 创建 Provider
            provider = provider_class(config)
            
            # 验证配置
            if not provider.validate_config():
                logger.warning(f"Provider {provider_name} 配置验证失败")
            
            # 缓存实例
            with self._config_lock:
                self._providers[config_key] = provider
            
            logger.info(f"创建新 Provider: {provider}")
            return provider
            
        except Exception as e:
            logger.error(f"创建 Provider 失败: {e}")
            raise RuntimeError(f"无法创建 Provider {provider_name}: {e}")
    
    def _generate_config_key(
        self, 
        provider_name: str,
        config: Optional[LLMConfig],
        **kwargs
    ) -> str:
        """生成配置的唯一键"""
        parts = [provider_name.lower()]
        
        if config:
            parts.append(config.model)
            if config.base_url:
                parts.append(config.base_url)
        
        for key, value in sorted(kwargs.items()):
            parts.append(f"{key}={value}")
        
        return "|".join(parts)
    
    def _build_config(self, provider_name: str, **kwargs) -> LLMConfig:
        """根据参数构建配置"""
        # 从 kwargs 中提取配置参数
        config_params = {}
        
        for key in ["api_key", "base_url", "model", "temperature", 
                    "max_tokens", "timeout", "max_retries"]:
            if key in kwargs:
                config_params[key] = kwargs.pop(key)
        
        # 处理 extra_params
        if kwargs:
            config_params["extra_params"] = kwargs
        
        return LLMConfig(**config_params)
    
    def get_provider(self, provider_name: str, **kwargs) -> BaseLLMProvider:
        """
        获取 Provider 实例（快捷方法）
        
        Args:
            provider_name: Provider 名称
            **kwargs: 配置参数
            
        Returns:
            BaseLLMProvider: Provider 实例
        """
        return self.create_provider(provider_name, **kwargs)
    
    def clear_providers(self):
        """清除所有缓存的 Provider 实例"""
        with self._config_lock:
            self._providers.clear()
        logger.info("已清除所有 Provider 缓存")
    
    def list_providers(self) -> Dict[str, Dict[str, Any]]:
        """
        列出所有已创建的 Provider
        
        Returns:
            Dict: Provider 信息字典
        """
        result = {}
        for key, provider in self._providers.items():
            result[key] = {
                "type": provider.provider_type.value,
                "model": provider.config.model,
                "base_url": provider.config.base_url,
            }
        return result


# 全局工厂实例
_factory: Optional[LLMFactory] = None


def get_factory() -> LLMFactory:
    """获取全局工厂实例"""
    global _factory
    if _factory is None:
        _factory = LLMFactory()
    return _factory


def get_provider(provider_name: str, **kwargs) -> BaseLLMProvider:
    """
    获取 Provider 实例的快捷函数（推荐使用）
    
    Args:
        provider_name: Provider 名称
            - "qwen": 通义千问
            - "deepseek": DeepSeek
            - "zhipu": 智谱AI
            - "moonshot": Moonshot
            - "openai": OpenAI
            - "openai_compatible": 通用 OpenAI 兼容接口
        **kwargs: 配置参数
            - api_key: API Key
            - model: 模型名称
            - base_url: API 地址
            - temperature: 温度参数
            - max_tokens: 最大 token 数
            - timeout: 超时时间
            - max_retries: 最大重试次数
    
    Returns:
        BaseLLMProvider: Provider 实例
        
    Example:
        # 使用默认配置（从环境变量读取）
        provider = get_provider("qwen")
        
        # 使用自定义配置
        provider = get_provider(
            "deepseek",
            api_key="sk-xxxx",
            model="deepseek-chat",
            temperature=0.5
        )
        
        # 发送聊天请求
        response = provider.chat("你好，请介绍一下自己")
        print(response.content)
    """
    factory = get_factory()
    return factory.get_provider(provider_name, **kwargs)


def create_provider(
    provider_name: str, 
    config: Optional[LLMConfig] = None
) -> BaseLLMProvider:
    """
    创建 Provider 实例（显式创建）
    
    Args:
        provider_name: Provider 名称
        config: 可选的配置对象
        
    Returns:
        BaseLLMProvider: Provider 实例
    """
    factory = get_factory()
    return factory.create_provider(provider_name, config)


__all__ = [
    "LLMFactory",
    "get_factory",
    "get_provider",
    "create_provider",
]
