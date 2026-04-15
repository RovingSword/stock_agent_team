"""
消息模型模块 - 定义多轮讨论中的消息和轮次结构
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class AgentRole(Enum):
    """Agent 角色枚举"""
    LEADER = "leader"
    TECHNICAL = "technical"           # 技术分析员
    INTELLIGENCE = "intelligence"     # 情报员
    RISK = "risk"                     # 风控官
    FUNDAMENTAL = "fundamental"       # 基本面分析员


@dataclass
class Message:
    """讨论消息"""
    role: str                          # "system", "user", "assistant"
    content: str
    agent_name: Optional[str] = None  # Agent 名称
    agent_role: Optional[AgentRole] = None  # Agent 角色
    timestamp: datetime = field(default_factory=datetime.now)
    parent_message_id: Optional[str] = None  # 父消息ID，用于追踪讨论脉络
    message_id: str = ""              # 消息唯一ID
    
    def __post_init__(self):
        if not self.message_id:
            import uuid
            self.message_id = str(uuid.uuid4())[:8]


@dataclass
class AgentReport:
    """Agent 分析报告"""
    agent_name: str
    agent_role: AgentRole
    score: float = 0.0           # 评分 0-10
    confidence: float = 0.0     # 置信度 0-1
    analysis: str = ""          # 分析内容
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "agent_role": self.agent_role.value,
            "score": self.score,
            "confidence": self.confidence,
            "analysis": self.analysis
        }


@dataclass
class DiscussionRound:
    """讨论轮次"""
    round_number: int                    # 轮次编号 (1, 2, 3)
    round_type: str                       # "independent", "discussion", "consensus"
    messages: List[Message] = field(default_factory=list)
    summary: str = ""                     # 本轮讨论总结
    agent_reports: List[AgentReport] = field(default_factory=list)
    
    def add_message(self, message: Message):
        """添加消息"""
        self.messages.append(message)
    
    def add_report(self, report: AgentReport):
        """添加 Agent 报告"""
        self.agent_reports.append(report)


@dataclass
class DiscussionHistory:
    """完整讨论历史"""
    stock_code: str
    stock_name: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    rounds: List[DiscussionRound] = field(default_factory=list)
    
    def add_round(self, round_obj: DiscussionRound):
        """添加一轮讨论"""
        self.rounds.append(round_obj)
    
    def get_all_messages(self) -> List[Message]:
        """获取所有消息"""
        all_messages = []
        for round_obj in self.rounds:
            all_messages.extend(round_obj.messages)
        return all_messages
    
    def get_final_decision(self) -> Optional[dict]:
        """获取最终决策"""
        if self.rounds and len(self.rounds) > 0:
            last_round = self.rounds[-1]
            if last_round.round_type == "consensus":
                return {
                    "reports": [r.to_dict() for r in last_round.agent_reports],
                    "summary": last_round.summary
                }
        return None


@dataclass
class DiscussionResult:
    """讨论结果"""
    stock_code: str
    stock_name: str
    final_reports: List[AgentReport]
    final_summary: str
    discussion_history: DiscussionHistory
    recommendation: str = ""            # 综合建议
    overall_score: float = 0.0           # 综合评分
    confidence: float = 0.0              # 综合置信度
