"""
LLM Agent 模块

提供基于 LLM 的智能 Agent 实现，与原有规则引擎 Agent 平行。
"""
from typing import Dict, Type, Optional

# 数据模型
from .models import (
    AgentReport,
    DiscussionMessage,
    LLMResponse,
    AgentConfig,
    StockAnalysisContext
)

# 基类
from .base_llm_agent import BaseLLMAgent, DiscussionAgent

# 各 Agent 实现
from .llm_leader import LLMLeader
from .llm_technical import LLMTechnical
from .llm_intelligence import LLMIntelligence
from .llm_risk import LLMRisk
from .llm_fundamental import LLMFundamental


# Agent 角色到类的映射
LLM_AGENT_REGISTRY: Dict[str, Type[BaseLLMAgent]] = {
    "leader": LLMLeader,
    "technical": LLMTechnical,
    "intelligence": LLMIntelligence,
    "risk": LLMRisk,
    "fundamental": LLMFundamental,
}


def create_llm_agent(
    role: str,
    name: Optional[str] = None,
    provider: str = "mock",
    **kwargs
) -> BaseLLMAgent:
    """
    创建 LLM Agent 工厂函数
    
    Args:
        role: Agent 角色 (leader/technical/intelligence/risk/fundamental)
        name: Agent 名称（可选）
        provider: LLM Provider 名称
        **kwargs: 额外参数
        
    Returns:
        LLM Agent 实例
        
    Raises:
        ValueError: 无效的角色名
    """
    if role not in LLM_AGENT_REGISTRY:
        available = ", ".join(LLM_AGENT_REGISTRY.keys())
        raise ValueError(f"Unknown role: {role}. Available: {available}")
    
    agent_class = LLM_AGENT_REGISTRY[role]
    agent_name = name or agent_class.__name__
    
    return agent_class(name=agent_name, provider=provider, **kwargs)


def create_team(
    provider: str = "mock",
    custom_names: Optional[Dict[str, str]] = None,
    **kwargs
) -> Dict[str, BaseLLMAgent]:
    """
    创建完整的 LLM Agent 团队
    
    Args:
        provider: LLM Provider 名称
        custom_names: 自定义 Agent 名称
        **kwargs: 传递给每个 Agent 的额外参数（如 api_key, base_url, model 等）
        
    Returns:
        Agent 字典 {role: agent_instance}
    """
    names = custom_names or {}
    
    team = {
        "leader": create_llm_agent("leader", names.get("leader"), provider, **kwargs),
        "technical": create_llm_agent("technical", names.get("technical"), provider, **kwargs),
        "intelligence": create_llm_agent("intelligence", names.get("intelligence"), provider, **kwargs),
        "risk": create_llm_agent("risk", names.get("risk"), provider, **kwargs),
        "fundamental": create_llm_agent("fundamental", names.get("fundamental"), provider, **kwargs),
    }
    
    return team


__all__ = [
    # 数据模型
    'AgentReport',
    'DiscussionMessage',
    'LLMResponse',
    'AgentConfig',
    'StockAnalysisContext',
    
    # 基类
    'BaseLLMAgent',
    'DiscussionAgent',
    
    # Agent 实现
    'LLMLeader',
    'LLMTechnical',
    'LLMIntelligence',
    'LLMRisk',
    'LLMFundamental',
    
    # 工厂函数
    'create_llm_agent',
    'create_team',
    'LLM_AGENT_REGISTRY',
]
