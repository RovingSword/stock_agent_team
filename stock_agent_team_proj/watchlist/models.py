"""
观察池数据模型
定义候选股票、观察池数据等数据结构
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
import json


class DataSource(Enum):
    """数据来源枚举"""
    DRAGON_TIGER = 'dragon_tiger'      # 龙虎榜
    SECTOR_HOT = 'sector_hot'          # 热门板块
    RESEARCH = 'research'               # 机构调研
    MANUAL = 'manual'                   # 手动添加
    UNKNOWN = 'unknown'


class CandidateStatus(Enum):
    """候选股状态枚举"""
    PENDING = 'pending'      # 待处理
    ANALYZING = 'analyzing'  # 分析中
    WATCHING = 'watching'    # 观察中
    ARCHIVED = 'archived'    # 已归档
    REMOVED = 'removed'      # 已移除


@dataclass
class StockCandidate:
    """候选股票数据类"""
    code: str
    name: str
    add_date: str
    add_reason: str
    source: str = 'unknown'
    source_score: float = 0.0
    
    # 状态与时间
    status: str = 'pending'
    last_analysis_date: Optional[str] = None
    added_by: str = 'system'
    
    # 分析结果
    analysis_result: Optional[Dict[str, Any]] = None
    composite_score: Optional[float] = None
    is_buy_recommended: Optional[bool] = None
    
    # 原始数据（用于追踪）
    raw_data: Optional[Dict[str, Any]] = None
    
    # 涨跌数据
    price_change_5d: Optional[float] = None  # 5日涨幅
    market_cap: Optional[float] = None        # 流通市值（亿）
    is_st: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StockCandidate':
        """从字典创建"""
        return cls(**data)
    
    def is_valid(self) -> bool:
        """检查是否有效"""
        return (
            bool(self.code) and 
            bool(self.name) and
            not self.is_st and
            self.source_score > 0
        )
    
    def update_status(self, new_status: str):
        """更新状态"""
        if new_status in ['pending', 'analyzing', 'watching', 'archived', 'removed']:
            self.status = new_status


@dataclass
class DragonTigerData:
    """龙虎榜数据"""
    date: str
    stock_code: str
    stock_name: str
    reason: str  # 上榜原因
    net_buy: float = 0.0  # 机构净买入金额（万）
    close_change: float = 0.0  # 当日涨跌幅
    source_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DragonTigerData':
        return cls(**data)


@dataclass
class SectorHotData:
    """板块热度数据"""
    date: str
    sector_name: str
    change_rate: float  # 板块涨跌幅
    leading_stocks: List[Dict[str, str]] = field(default_factory=list)  # [{code, name}]
    reason: Optional[str] = None
    source_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SectorHotData':
        return cls(**data)


@dataclass
class ResearchData:
    """机构调研数据"""
    date: str
    stock_code: str
    stock_name: str
    org_name: str  # 调研机构名称
    org_count: int = 1  # 参与机构数量
    topic: Optional[str] = None
    source_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResearchData':
        return cls(**data)


@dataclass
class WatchlistData:
    """观察池完整数据"""
    update_time: str
    version: str = '1.0'
    
    candidates: List[StockCandidate] = field(default_factory=list)
    removed: List[StockCandidate] = field(default_factory=list)  # 已移除的股票
    
    # 统计数据
    stats: Dict[str, int] = field(default_factory=lambda: {
        'total': 0,
        'pending': 0,
        'analyzing': 0,
        'watching': 0,
        'archived': 0,
    })
    
    def update_stats(self):
        """更新统计"""
        self.stats = {
            'total': len(self.candidates),
            'pending': sum(1 for c in self.candidates if c.status == 'pending'),
            'analyzing': sum(1 for c in self.candidates if c.status == 'analyzing'),
            'watching': sum(1 for c in self.candidates if c.status == 'watching'),
            'archived': sum(1 for c in self.candidates if c.status == 'archived'),
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'update_time': self.update_time,
            'version': self.version,
            'candidates': [c.to_dict() for c in self.candidates],
            'removed': [r.to_dict() for r in self.removed],
            'stats': self.stats,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WatchlistData':
        """从字典创建"""
        candidates = [StockCandidate.from_dict(c) for c in data.get('candidates', [])]
        removed = [StockCandidate.from_dict(r) for r in data.get('removed', [])]
        
        instance = cls(
            update_time=data.get('update_time', ''),
            version=data.get('version', '1.0'),
            candidates=candidates,
            removed=removed,
            stats=data.get('stats', {}),
        )
        instance.update_stats()
        return instance
    
    def save(self, filepath: str):
        """保存到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load(cls, filepath: str) -> 'WatchlistData':
        """从文件加载"""
        if not os.path.exists(filepath):
            return cls(update_time=datetime.now().isoformat())
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)


@dataclass
class ScheduledTask:
    """定时任务配置"""
    task_id: str
    task_name: str
    task_type: str  # 'collect', 'screen', 'analyze', 'full'
    schedule_time: str  # cron格式或 HH:MM
    enabled: bool = True
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    run_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScheduledTask':
        return cls(**data)


import os  # 用于WatchlistData.load


# ========== 表现跟踪相关数据模型 ==========

@dataclass
class PriceSnapshot:
    """价格快照"""
    code: str
    date: str
    close_price: float
    change_pct: float  # 当日涨跌幅
    volume: float
    turnover: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PriceSnapshot':
        return cls(**data)


@dataclass
class SignalRecord:
    """信号记录"""
    code: str
    name: str
    signal_date: str
    signal_type: str  # buy/watch/avoid
    composite_score: float
    entry_price: Optional[float] = None  # 建议入场价
    stop_loss: Optional[float] = None    # 止损价
    take_profit: Optional[float] = None  # 止盈价
    position_size: Optional[float] = None  # 建议仓位
    
    # 后续跟踪
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # 止盈/止损/移除/手动
    actual_return: Optional[float] = None  # 实际收益率
    max_return: Optional[float] = None  # 期间最大收益
    max_drawdown: Optional[float] = None  # 期间最大回撤
    holding_days: Optional[int] = None
    
    # 附加信息
    add_reason: str = ''
    source: str = 'analysis'
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SignalRecord':
        return cls(**data)
    
    @property
    def is_closed(self) -> bool:
        """是否已平仓"""
        return self.exit_date is not None
    
    @property
    def is_winning(self) -> bool:
        """是否盈利"""
        return self.actual_return is not None and self.actual_return > 0


@dataclass
class PerformanceStats:
    """表现统计"""
    update_time: str
    
    # 信号统计
    total_signals: int = 0
    buy_signals: int = 0
    watch_signals: int = 0
    avoid_signals: int = 0
    
    # 买入信号表现
    closed_signals: int = 0
    buy_wins: int = 0
    buy_losses: int = 0
    win_rate: float = 0.0
    avg_return: float = 0.0
    avg_win_return: float = 0.0
    avg_loss_return: float = 0.0
    total_return: float = 0.0
    
    # 信号准确率
    avoid_accuracy: float = 0.0  # avoid信号后股价下跌的比例
    
    # 观察信号表现
    watching_count: int = 0
    avg_watching_return: float = 0.0  # 观察中股票的平均收益
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PerformanceStats':
        return cls(**data)


@dataclass
class PriceHistory:
    """价格历史数据"""
    update_time: str
    snapshots: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)  # {code: [snapshots]}
    
    def add_snapshot(self, code: str, snapshot: PriceSnapshot):
        """添加价格快照"""
        if code not in self.snapshots:
            self.snapshots[code] = []
        self.snapshots[code].append(snapshot.to_dict())
    
    def get_latest_price(self, code: str) -> Optional[float]:
        """获取最新价格"""
        if code not in self.snapshots or not self.snapshots[code]:
            return None
        return self.snapshots[code][-1].get('close_price')
    
    def get_price_series(self, code: str, days: int = 30) -> List[float]:
        """获取价格序列"""
        if code not in self.snapshots:
            return []
        return [s['close_price'] for s in self.snapshots[code][-days:]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'update_time': self.update_time,
            'snapshots': self.snapshots,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PriceHistory':
        return cls(
            update_time=data.get('update_time', ''),
            snapshots=data.get('snapshots', {}),
        )
    
    def save(self, filepath: str):
        """保存到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load(cls, filepath: str) -> 'PriceHistory':
        """从文件加载"""
        if not os.path.exists(filepath):
            return cls(update_time=datetime.now().isoformat())
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)


@dataclass
class SignalHistory:
    """信号历史数据"""
    update_time: str
    signals: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_signal(self, signal: SignalRecord):
        """添加信号"""
        self.signals.append(signal.to_dict())
    
    def update_signal(self, code: str, signal_date: str, updates: Dict[str, Any]):
        """更新信号"""
        for sig in self.signals:
            if sig['code'] == code and sig['signal_date'] == signal_date:
                sig.update(updates)
                return True
        return False
    
    def get_open_signals(self, signal_type: str = None) -> List[SignalRecord]:
        """获取未平仓信号"""
        results = []
        for sig in self.signals:
            if sig.get('exit_date') is None:
                if signal_type is None or sig.get('signal_type') == signal_type:
                    results.append(SignalRecord.from_dict(sig))
        return results
    
    def get_closed_signals(self, signal_type: str = None) -> List[SignalRecord]:
        """获取已平仓信号"""
        results = []
        for sig in self.signals:
            if sig.get('exit_date') is not None:
                if signal_type is None or sig.get('signal_type') == signal_type:
                    results.append(SignalRecord.from_dict(sig))
        return results
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'update_time': self.update_time,
            'signals': self.signals,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SignalHistory':
        return cls(
            update_time=data.get('update_time', ''),
            signals=data.get('signals', []),
        )
    
    def save(self, filepath: str):
        """保存到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load(cls, filepath: str) -> 'SignalHistory':
        """从文件加载"""
        if not os.path.exists(filepath):
            return cls(update_time=datetime.now().isoformat())
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)
