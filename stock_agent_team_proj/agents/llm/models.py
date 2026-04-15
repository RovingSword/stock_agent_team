"""
LLM Agent 数据模型
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class AgentReport:
    """Agent 分析报告"""
    agent_name: str
    agent_role: str
    score: float  # 0-10 评分
    confidence: float  # 0-1 置信度
    summary: str  # 一句话总结
    analysis: str  # 详细分析
    risks: List[str] = field(default_factory=list)  # 风险点
    opportunities: List[str] = field(default_factory=list)  # 机会点
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外元数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'agent_name': self.agent_name,
            'agent_role': self.agent_role,
            'score': self.score,
            'confidence': self.confidence,
            'summary': self.summary,
            'analysis': self.analysis,
            'risks': self.risks,
            'opportunities': self.opportunities,
            'metadata': self.metadata
        }


@dataclass
class DiscussionMessage:
    """讨论消息"""
    agent_name: str
    content: str
    round: int
    timestamp: datetime = field(default_factory=datetime.now)
    message_type: str = "opinion"  # opinion, question, agreement, objection
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'agent_name': self.agent_name,
            'content': self.content,
            'round': self.round,
            'timestamp': self.timestamp.isoformat(),
            'message_type': self.message_type
        }


@dataclass
class LLMResponse:
    """LLM 响应封装"""
    content: str
    raw_response: Optional[Dict[str, Any]] = None
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    finish_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'content': self.content,
            'raw_response': self.raw_response,
            'model': self.model,
            'tokens_used': self.tokens_used,
            'finish_reason': self.finish_reason
        }


@dataclass
class AgentConfig:
    """Agent 配置"""
    name: str
    role: str
    provider: str
    model: str
    system_prompt: str
    temperature: float = 0.7
    max_tokens: int = 2000
    timeout: int = 60


@dataclass
class StockAnalysisContext:
    """股票分析上下文"""
    stock_code: str
    stock_name: str
    task_id: str
    user_request: str = ""
    market_data: Dict[str, Any] = field(default_factory=dict)
    historical_data: Dict[str, Any] = field(default_factory=dict)
    news_data: List[Dict[str, Any]] = field(default_factory=list)
    fundamental_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_prompt_context(self) -> str:
        """转换为提示词上下文"""
        context_parts = [
            f"股票代码: {self.stock_code}",
            f"股票名称: {self.stock_name}",
            f"用户请求: {self.user_request or '综合分析'}",
        ]
        
        if self.market_data:
            context_parts.append(f"市场数据: {self.market_data}")
        
        if self.historical_data:
            context_parts.append(f"历史数据: {self.historical_data}")
            
        if self.news_data:
            news_summary = [f"- {n.get('title', '')}" for n in self.news_data[:5]]
            context_parts.append(f"相关新闻:\n" + "\n".join(news_summary))
            
        if self.fundamental_data:
            context_parts.append(f"基本面数据: {self.fundamental_data}")
            
        return "\n".join(context_parts)
