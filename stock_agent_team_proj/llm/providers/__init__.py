# -*- coding: utf-8 -*-
"""
LLM Providers 导出模块

导出所有支持的 LLM Provider 实现。
"""

import json
from typing import List, Optional, Dict, Any, Iterator

from ..base_provider import (
    BaseLLMProvider,
    LLMConfig,
    ChatMessage,
    ChatCompletionResponse,
    LLMProviderType,
)

from .qwen_provider import QwenProvider
from .deepseek_provider import DeepSeekProvider
from .zhipu_provider import ZhipuProvider
from .moonshot_provider import MoonshotProvider
from .openai_compatible_provider import OpenAICompatibleProvider


class MockProvider(BaseLLMProvider):
    """
    Mock LLM Provider - 用于开发测试
    
    当没有真实 API Key 或需要测试时使用此 Provider。
    返回基于关键词的模拟响应。
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        if config is None:
            config = LLMConfig(model="mock")
        super().__init__(config)
    
    def _get_provider_type(self) -> LLMProviderType:
        return LLMProviderType.OPENAI
    
    def _create_client(self):
        """Mock 客户端"""
        return None
    
    def chat(
        self,
        message: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> ChatCompletionResponse:
        """返回 Mock 响应"""
        messages = []
        if system_prompt:
            messages.append(ChatMessage(role="system", content=system_prompt))
        messages.append(ChatMessage(role="user", content=message))
        return self.chat_with_history(messages, **kwargs)
    
    def chat_with_history(
        self,
        messages: List[ChatMessage],
        **kwargs
    ) -> ChatCompletionResponse:
        """返回 Mock 响应"""
        last_message = ""
        for msg in reversed(messages):
            if msg.role == "user":
                last_message = msg.content
                break
        
        response_content = self._generate_mock_response(last_message)
        
        return ChatCompletionResponse(
            content=response_content,
            model=self.config.model or "mock-model",
            usage={"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300}
        )
    
    def _chat_stream_impl(
        self,
        messages: List[ChatMessage],
        **kwargs
    ):
        """Mock 流式响应"""
        last_message = ""
        for msg in reversed(messages):
            if msg.role == "user":
                last_message = msg.content
                break
        
        response = self._generate_mock_response(last_message)
        for char in response:
            yield char
    
    def get_model_info(self) -> Dict[str, Any]:
        """返回 Mock 模型信息"""
        return {
            "model": "mock-model",
            "provider": "mock",
            "description": "Mock Provider for testing"
        }
    
    def _generate_mock_response(self, user_message: str) -> str:
        """生成 Mock 响应内容"""
        msg_lower = user_message.lower()
        
        if "技术分析" in user_message or "technical" in msg_lower:
            return json.dumps({
                "score": 7.5, "confidence": 0.8,
                "summary": "技术面显示短期反弹信号",
                "analysis": "K线形态良好，MACD金叉形成，成交量温和放大。均线系统呈多头排列。",
                "risks": ["可能面临前期高点压力", "成交量能否持续是关键"],
                "opportunities": ["MACD形成金叉，买入信号"]
            }, ensure_ascii=False)
        
        elif "风险" in user_message or "risk" in msg_lower:
            return json.dumps({
                "score": 6.0, "confidence": 0.7,
                "summary": "风险可控，建议轻仓试探",
                "analysis": "当前市场波动较大，建议控制仓位在30%以内。",
                "risks": ["市场系统性风险", "个股黑天鹅事件"],
                "opportunities": ["严格止损可控制亏损"]
            }, ensure_ascii=False)
        
        elif "基本面" in user_message or "fundamental" in msg_lower:
            return json.dumps({
                "score": 7.0, "confidence": 0.75,
                "summary": "基本面良好，估值合理",
                "analysis": "公司营收稳定增长，毛利率保持行业平均水平。PE处于历史中位数。",
                "risks": ["行业竞争加剧", "原材料成本上升"],
                "opportunities": ["行业龙头地位稳固"]
            }, ensure_ascii=False)
        
        elif "情报" in user_message or "资金" in user_message:
            return json.dumps({
                "score": 6.5, "confidence": 0.7,
                "summary": "资金面偏中性",
                "analysis": "近5日主力资金净流出，但北向资金小幅净流入。",
                "risks": ["主力可能继续出货", "市场情绪转弱"],
                "opportunities": ["北向资金逆势买入值得关注"]
            }, ensure_ascii=False)
        
        elif "决策" in user_message or "综合" in user_message:
            return json.dumps({
                "score": 7.0, "confidence": 0.75,
                "summary": "综合分析后建议观望",
                "analysis": "各维度分析结果存在分歧，建议等待更明确信号。",
                "risks": ["方向不明", "等待确认"],
                "opportunities": ["可小仓位试探"]
            }, ensure_ascii=False)
        
        else:
            return json.dumps({
                "score": 7.0, "confidence": 0.7,
                "summary": "综合分析后给出中性偏多判断",
                "analysis": "基于当前信息综合分析，建议保持关注。",
                "risks": ["注意控制风险"],
                "opportunities": ["等待更好的买入时机"]
            }, ensure_ascii=False)

# Provider 映射表
PROVIDER_MAPPING = {
    LLMProviderType.QWEN: QwenProvider,
    LLMProviderType.DEEPSEEK: DeepSeekProvider,
    LLMProviderType.ZHIPU: ZhipuProvider,
    LLMProviderType.MOONSHOT: MoonshotProvider,
    LLMProviderType.OPENAI_COMPATIBLE: OpenAICompatibleProvider,
    LLMProviderType.OPENAI: OpenAICompatibleProvider,  # OpenAI 也使用通用接口
}

# 字符串到 Provider 类型的映射（用于配置）
PROVIDER_NAME_MAPPING = {
    "qwen": LLMProviderType.QWEN,
    "qwen_plus": LLMProviderType.QWEN,
    "deepseek": LLMProviderType.DEEPSEEK,
    "zhipu": LLMProviderType.ZHIPU,
    "glm": LLMProviderType.ZHIPU,
    "moonshot": LLMProviderType.MOONSHOT,
    "moonshot_v1": LLMProviderType.MOONSHOT,
    "openai": LLMProviderType.OPENAI,
    "openai_compatible": LLMProviderType.OPENAI_COMPATIBLE,
    "compatible": LLMProviderType.OPENAI_COMPATIBLE,
}


def get_provider_class(provider_type: LLMProviderType):
    """
    根据 Provider 类型获取对应的类
    
    Args:
        provider_type: Provider 类型
        
    Returns:
        Provider 类
    """
    return PROVIDER_MAPPING.get(provider_type)


def get_provider_type_by_name(name: str) -> LLMProviderType:
    """
    根据名称获取 Provider 类型
    
    Args:
        name: Provider 名称
        
    Returns:
        Provider 类型
        
    Raises:
        ValueError: 不支持的 Provider 名称
    """
    name_lower = name.lower()
    
    if name_lower in PROVIDER_NAME_MAPPING:
        return PROVIDER_NAME_MAPPING[name_lower]
    
    # Mock Provider 特殊处理
    if name_lower in ("mock", "default"):
        return LLMProviderType.OPENAI  # Mock 使用 OPENAI 类型
    
    # 尝试直接解析
    try:
        return LLMProviderType(name_lower)
    except ValueError:
        raise ValueError(
            f"不支持的 Provider: {name}。"
            f"支持的 Provider: {list(PROVIDER_NAME_MAPPING.keys())} + mock"
        )


__all__ = [
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
    # 工具函数
    "get_provider_class",
    "get_provider_type_by_name",
    "PROVIDER_MAPPING",
    "PROVIDER_NAME_MAPPING",
]
