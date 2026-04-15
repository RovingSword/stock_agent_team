"""
Agent 多轮讨论引擎

提供股票分析团队的多轮讨论能力，支持 2-3 轮讨论机制，
最终输出综合投资建议。

Usage:
    from stock_agent_team.conversation import DiscussionManager, AgentRole

    # 创建 Agent
    leader = SimpleLLMAgent("讨论主持", AgentRole.LEADER, "讨论主持人")
    agents = [
        SimpleLLMAgent("技术分析员", AgentRole.TECHNICAL, "技术分析专家"),
        SimpleLLMAgent("情报员", AgentRole.INTELLIGENCE, "市场情报分析师"),
        SimpleLLMAgent("风控官", AgentRole.RISK, "风险控制专家"),
        SimpleLLMAgent("基本面分析员", AgentRole.FUNDAMENTAL, "基本面分析师"),
    ]

    # 启动讨论
    manager = DiscussionManager(leader, agents)
    result = manager.start_discussion_sync(
        stock_code="000001",
        stock_name="平安银行",
        data={
            "current_price": "12.50",
            "market_context": "震荡上行",
            "technical": {"MACD": "金叉", "KDJ": "多头"},
            "intelligence": {"north_flow": "+5000万"},
            "risk": {"volatility": "中等"},
            "fundamental": {"PE": "6.5", "ROE": "12%"}
        }
    )

    # 获取结果
    print(result.recommendation)
    print(result.overall_score)
"""

from .message import (
    Message,
    AgentReport,
    DiscussionRound,
    DiscussionHistory,
    DiscussionResult,
    AgentRole,
)

from .discussion_manager import (
    DiscussionManager,
    BaseLLMAgent,
    SimpleLLMAgent,
)

from .prompts import (
    LEADER_START_DISCUSSION,
    LEADER_SUMMARY,
    LEADER_FINAL_SUMMARY,
    AGENT_RESPONSE_TEMPLATE,
    AGENT_INITIAL_REPORT,
    format_agent_reports,
    format_discussion_context,
    format_other_views,
    ROUND_INSTRUCTIONS,
)

__all__ = [
    # 消息模型
    "Message",
    "AgentReport", 
    "DiscussionRound",
    "DiscussionHistory",
    "DiscussionResult",
    "AgentRole",
    
    # 管理器
    "DiscussionManager",
    "BaseLLMAgent",
    "SimpleLLMAgent",
    
    # 提示词模板
    "LEADER_START_DISCUSSION",
    "LEADER_SUMMARY",
    "LEADER_FINAL_SUMMARY",
    "AGENT_RESPONSE_TEMPLATE",
    "AGENT_INITIAL_REPORT",
    "format_agent_reports",
    "format_discussion_context",
    "format_other_views",
    "ROUND_INSTRUCTIONS",
]

__version__ = "1.0.0"
