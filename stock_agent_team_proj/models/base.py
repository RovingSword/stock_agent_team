"""
基础数据模型
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class TradeStatus(Enum):
    """交易状态"""
    PENDING = "pending"          # 待执行
    HOLDING = "holding"          # 持仓中
    CLOSED = "closed"            # 已平仓
    CANCELLED = "cancelled"      # 已取消


class TradeAction(Enum):
    """交易动作"""
    BUY = "buy"                  # 买入
    SELL = "sell"                # 卖出
    WATCH = "watch"              # 观望
    HOLD = "hold"                # 持有


class SellReason(Enum):
    """卖出原因"""
    TAKE_PROFIT_1 = "take_profit_1"      # 第一止盈
    TAKE_PROFIT_2 = "take_profit_2"      # 第二止盈
    TAKE_PROFIT_3 = "take_profit_3"      # 第三止盈
    STOP_LOSS = "stop_loss"              # 止损
    LOGIC_INVALID = "logic_invalid"      # 逻辑证伪
    TIMEOUT = "timeout"                  # 超时
    MANUAL = "manual"                    # 手动卖出
    RISK_ALERT = "risk_alert"            # 风控预警


class AgentType(Enum):
    """Agent类型"""
    LEADER = "leader"
    TECHNICAL = "technical"
    INTELLIGENCE = "intelligence"
    RISK = "risk"
    FUNDAMENTAL = "fundamental"
    REVIEW = "review"


class AccuracyLevel(Enum):
    """准确性等级"""
    ACCURATE = "accurate"        # 准确
    PARTIAL = "partial"          # 部分准确
    INACCURATE = "inaccurate"    # 不准确


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionType(Enum):
    """决策类型"""
    STRONG_BUY = "strong_buy"    # 强烈买入
    BUY = "buy"                  # 建议买入
    WATCH = "watch"              # 观望
    AVOID = "avoid"              # 回避
    RISK_REJECT = "risk_reject"  # 风控否决


class MessageType(Enum):
    """消息类型"""
    TASK_DISPATCH = "task_dispatch"
    ANALYSIS_REPORT = "analysis_report"
    RISK_ASSESSMENT = "risk_assessment"
    TRADE_DECISION = "trade_decision"
    ERROR_REPORT = "error_report"
    REVIEW_REQUEST = "review_request"
    REVIEW_REPORT = "review_report"


class ReviewType(Enum):
    """复盘类型"""
    SINGLE = "single"            # 单笔复盘
    DAILY = "daily"              # 日度复盘
    WEEKLY = "weekly"            # 周度复盘
    MONTHLY = "monthly"          # 月度复盘
    EMERGENCY = "emergency"      # 紧急复盘


@dataclass
class BaseModel:
    """基础模型"""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            k: v.isoformat() if isinstance(v, datetime) else v
            for k, v in self.__dict__.items()
            if not k.startswith('_')
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseModel':
        """从字典创建"""
        return cls(**data)


@dataclass
class Stock:
    """股票信息"""
    code: str                           # 股票代码
    name: str                           # 股票名称
    market: str = "SZ"                  # 市场
    
    def __str__(self) -> str:
        return f"{self.name}({self.code}.{self.market})"


@dataclass
class Price:
    """价格信息"""
    current: float                      # 当前价
    open: float                         # 开盘价
    high: float                         # 最高价
    low: float                          # 最低价
    close: float                        # 收盘价
    volume: float = 0.0                 # 成交量
    amount: float = 0.0                 # 成交额
    
    def change_rate(self, prev_close: float) -> float:
        """计算涨跌幅"""
        if prev_close == 0:
            return 0.0
        return (self.close - prev_close) / prev_close * 100


@dataclass
class Score:
    """评分信息"""
    value: float                        # 评分值 (0-10)
    weight: float = 1.0                 # 权重
    weighted_value: float = 0.0         # 加权评分
    
    def __post_init__(self):
        self.weighted_value = self.value * self.weight
    
    def __str__(self) -> str:
        return f"{self.value:.1f}/10 (权重{self.weight*100:.0f}%)"


@dataclass
class Position:
    """仓位信息"""
    ratio: float                        # 仓位比例
    amount: float = 0.0                 # 金额
    shares: float = 0.0                 # 股数
    cost_price: float = 0.0             # 成本价
    
    def value(self, current_price: float) -> float:
        """计算当前市值"""
        return self.shares * current_price
    
    def profit(self, current_price: float) -> float:
        """计算盈亏"""
        return (current_price - self.cost_price) * self.shares
    
    def profit_rate(self, current_price: float) -> float:
        """计算收益率"""
        if self.cost_price == 0:
            return 0.0
        return (current_price - self.cost_price) / self.cost_price


@dataclass
class StopLossTakeProfit:
    """止损止盈设置"""
    stop_loss: float                    # 止损价
    take_profit_1: float = 0.0          # 止盈价1
    take_profit_2: float = 0.0          # 止盈价2
    take_profit_3: float = 0.0          # 止盈价3
    
    stop_loss_rate: float = 0.0         # 止损比例
    take_profit_1_rate: float = 0.0     # 止盈比例1
    take_profit_2_rate: float = 0.0     # 止盈比例2
    take_profit_3_rate: float = 0.0     # 止盈比例3
    
    def profit_loss_ratio(self) -> float:
        """计算盈亏比"""
        if self.stop_loss_rate == 0:
            return 0.0
        return self.take_profit_1_rate / self.stop_loss_rate
