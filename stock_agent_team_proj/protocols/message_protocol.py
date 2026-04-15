"""
消息协议定义
"""
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List

from models.base import MessageType


@dataclass
class MessageHeader:
    """消息头"""
    message_id: str = field(default_factory=lambda: f"MSG_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}")
    message_type: MessageType = MessageType.TASK_DISPATCH
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    sender: Dict[str, str] = field(default_factory=dict)      # {agent_id, agent_name}
    receivers: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'message_id': self.message_id,
            'message_type': self.message_type.value,
            'timestamp': self.timestamp,
            'sender': self.sender,
            'receivers': self.receivers,
        }


@dataclass
class TaskDispatchMessage:
    """任务分发消息 (Leader -> Workers)"""
    header: MessageHeader
    task_id: str = ""
    task_type: str = "stock_analysis"
    stock: Dict[str, str] = field(default_factory=dict)       # {code, name, market}
    analysis_type: str = "entry_signal"                       # entry_signal / exit_signal
    holding_period: str = "medium_short"
    deadline: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        self.header.message_type = MessageType.TASK_DISPATCH
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'header': self.header.to_dict(),
            'task': {
                'task_id': self.task_id,
                'task_type': self.task_type,
                'stock': self.stock,
                'analysis_type': self.analysis_type,
                'holding_period': self.holding_period,
                'deadline': self.deadline,
                'context': self.context,
            }
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def create(cls, stock_code: str, stock_name: str, user_request: str, 
               sender: Dict[str, str] = None, receivers: List[str] = None) -> 'TaskDispatchMessage':
        """创建任务分发消息"""
        header = MessageHeader()
        if sender:
            header.sender = sender
        if receivers:
            header.receivers = receivers
        
        task_id = f"TASK_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{stock_code}"
        deadline = datetime.now().replace(hour=16, minute=0, second=0).isoformat()
        
        return cls(
            header=header,
            task_id=task_id,
            stock={'code': stock_code, 'name': stock_name, 'market': 'SZ'},
            deadline=deadline,
            context={'user_request': user_request}
        )


@dataclass
class AnalysisReportMessage:
    """分析报告消息 (Workers -> Leader)"""
    header: MessageHeader
    task_id: str = ""
    stock_code: str = ""
    stock_name: str = ""
    agent_type: str = ""                                      # technical / intelligence / risk / fundamental
    weight: float = 0.0
    scores: Dict[str, float] = field(default_factory=dict)    # 各细分评分
    overall_score: float = 0.0
    conclusion: Dict[str, Any] = field(default_factory=dict)  # 结论
    key_points: List[str] = field(default_factory=list)       # 要点
    risk_points: List[str] = field(default_factory=list)      # 风险点
    raw_data: Dict[str, Any] = field(default_factory=dict)    # 原始数据
    
    def __post_init__(self):
        self.header.message_type = MessageType.ANALYSIS_REPORT
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'header': self.header.to_dict(),
            'report': {
                'task_id': self.task_id,
                'stock_code': self.stock_code,
                'stock_name': self.stock_name,
                'agent_type': self.agent_type,
                'weight': self.weight,
                'scores': self.scores,
                'overall_score': self.overall_score,
                'conclusion': self.conclusion,
                'key_points': self.key_points,
                'risk_points': self.risk_points,
                'raw_data': self.raw_data,
            }
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class RiskAssessmentMessage:
    """风控评估消息 (Risk Controller -> Leader)"""
    header: MessageHeader
    task_id: str = ""
    stock_code: str = ""
    market_risk: Dict[str, Any] = field(default_factory=dict)
    stock_risk: Dict[str, Any] = field(default_factory=dict)
    trade_risk: Dict[str, Any] = field(default_factory=dict)
    decision: Dict[str, Any] = field(default_factory=dict)    # {action, max_position_allowed, warnings}
    
    def __post_init__(self):
        self.header.message_type = MessageType.RISK_ASSESSMENT
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'header': self.header.to_dict(),
            'assessment': {
                'task_id': self.task_id,
                'stock_code': self.stock_code,
                'market_risk': self.market_risk,
                'stock_risk': self.stock_risk,
                'trade_risk': self.trade_risk,
                'decision': self.decision,
            }
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @property
    def is_approved(self) -> bool:
        """是否通过风控"""
        return self.decision.get('action') == 'approve'
    
    @property
    def is_rejected(self) -> bool:
        """是否被否决"""
        return self.decision.get('action') == 'reject'


@dataclass
class TradeDecisionMessage:
    """交易决策消息 (Leader -> User)"""
    header: MessageHeader
    stock_code: str = ""
    stock_name: str = ""
    final_action: str = ""                                    # buy / sell / watch
    confidence: str = ""                                      # high / medium / low
    composite_score: float = 0.0
    score_breakdown: Dict[str, Dict[str, float]] = field(default_factory=dict)
    execution: Dict[str, Any] = field(default_factory=dict)   # 入场、止损、止盈、仓位
    rationale: Dict[str, List[str]] = field(default_factory=dict)  # 买入理由、风险点
    follow_up: Dict[str, Any] = field(default_factory=dict)   # 后续跟踪
    
    def __post_init__(self):
        self.header.message_type = MessageType.TRADE_DECISION
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'header': self.header.to_dict(),
            'decision': {
                'stock_code': self.stock_code,
                'stock_name': self.stock_name,
                'final_action': self.final_action,
                'confidence': self.confidence,
                'composite_score': self.composite_score,
                'score_breakdown': self.score_breakdown,
                'execution': self.execution,
                'rationale': self.rationale,
                'follow_up': self.follow_up,
            }
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @property
    def is_buy(self) -> bool:
        return self.final_action in ('buy', 'strong_buy')
    
    @property
    def entry_zone(self) -> List[float]:
        return self.execution.get('entry_zone', [])
    
    @property
    def stop_loss(self) -> float:
        return self.execution.get('stop_loss', 0)
    
    @property
    def position_size(self) -> float:
        return self.execution.get('position_size', 0)


@dataclass
class ErrorMessage:
    """错误消息"""
    header: MessageHeader
    task_id: str = ""
    error_code: str = ""
    error_message: str = ""
    severity: str = "high"                                    # low / medium / high / critical
    retry_possible: bool = False
    alternative_action: str = ""
    
    def __post_init__(self):
        self.header.message_type = MessageType.ERROR_REPORT
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'header': self.header.to_dict(),
            'error': {
                'task_id': self.task_id,
                'error_code': self.error_code,
                'error_message': self.error_message,
                'severity': self.severity,
                'retry_possible': self.retry_possible,
                'alternative_action': self.alternative_action,
            }
        }


@dataclass
class ReviewRequestMessage:
    """复盘请求消息"""
    header: MessageHeader
    review_type: str = "single"                               # single / weekly / monthly / emergency
    trade_id: Optional[str] = None                            # 单笔复盘的交易ID
    period_start: Optional[str] = None                        # 周期复盘的开始日期
    period_end: Optional[str] = None                          # 周期复盘的结束日期
    
    def __post_init__(self):
        self.header.message_type = MessageType.REVIEW_REQUEST
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'header': self.header.to_dict(),
            'review_request': {
                'review_type': self.review_type,
                'trade_id': self.trade_id,
                'period_start': self.period_start,
                'period_end': self.period_end,
            }
        }


@dataclass
class ReviewReportMessage:
    """复盘报告消息"""
    header: MessageHeader
    review_id: str = ""
    review_type: str = ""
    
    # 交易统计
    total_trades: int = 0
    win_trades: int = 0
    loss_trades: int = 0
    win_rate: float = 0.0
    total_return: float = 0.0
    
    # 各角色准确率
    accuracy_rates: Dict[str, float] = field(default_factory=dict)
    
    # 权重调整建议
    weight_adjustment: Dict[str, float] = field(default_factory=dict)
    
    # 报告内容
    content: str = ""
    file_path: str = ""
    
    def __post_init__(self):
        self.header.message_type = MessageType.REVIEW_REPORT
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'header': self.header.to_dict(),
            'review_report': {
                'review_id': self.review_id,
                'review_type': self.review_type,
                'total_trades': self.total_trades,
                'win_trades': self.win_trades,
                'loss_trades': self.loss_trades,
                'win_rate': self.win_rate,
                'total_return': self.total_return,
                'accuracy_rates': self.accuracy_rates,
                'weight_adjustment': self.weight_adjustment,
                'content': self.content,
                'file_path': self.file_path,
            }
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ============================================================
# 消息工厂
# ============================================================

class MessageFactory:
    """消息工厂"""
    
    @staticmethod
    def create_task_dispatch(stock_code: str, stock_name: str, 
                             user_request: str,
                             sender: Dict[str, str] = None) -> TaskDispatchMessage:
        """创建任务分发消息"""
        receivers = ['technical_analyst', 'intelligence_officer', 
                     'fundamental_analyst', 'risk_controller']
        return TaskDispatchMessage.create(
            stock_code=stock_code,
            stock_name=stock_name,
            user_request=user_request,
            sender=sender or {'agent_id': 'leader', 'agent_name': '决策中枢'},
            receivers=receivers
        )
    
    @staticmethod
    def create_analysis_report(task_id: str, stock_code: str, stock_name: str,
                               agent_type: str, weight: float, 
                               overall_score: float, conclusion: Dict[str, Any],
                               key_points: List[str], risk_points: List[str]) -> AnalysisReportMessage:
        """创建分析报告消息"""
        header = MessageHeader()
        header.message_type = MessageType.ANALYSIS_REPORT
        
        return AnalysisReportMessage(
            header=header,
            task_id=task_id,
            stock_code=stock_code,
            stock_name=stock_name,
            agent_type=agent_type,
            weight=weight,
            overall_score=overall_score,
            conclusion=conclusion,
            key_points=key_points,
            risk_points=risk_points
        )
    
    @staticmethod
    def create_trade_decision(stock_code: str, stock_name: str,
                              final_action: str, composite_score: float,
                              execution: Dict[str, Any],
                              rationale: Dict[str, List[str]]) -> TradeDecisionMessage:
        """创建交易决策消息"""
        header = MessageHeader()
        header.message_type = MessageType.TRADE_DECISION
        
        confidence = 'high' if composite_score >= 8 else ('medium' if composite_score >= 7 else 'low')
        
        return TradeDecisionMessage(
            header=header,
            stock_code=stock_code,
            stock_name=stock_name,
            final_action=final_action,
            confidence=confidence,
            composite_score=composite_score,
            execution=execution,
            rationale=rationale
        )
