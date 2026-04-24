"""
观察池模块

提供完整的自动化股票观察池管理功能：
- 数据采集：龙虎榜、热门板块、机构调研
- 股票筛选：多维度评分与过滤
- 观察池管理：添加、移除、更新
- 表现跟踪：信号记录、收益率计算、胜率统计
- 报告生成：周报、月报、信号报告
- 自动调度：定时任务执行
"""

from .models import (
    StockCandidate, WatchlistData, DataSource,
    PriceSnapshot, SignalRecord, PerformanceStats,
    PriceHistory, SignalHistory
)
from .config import WatchlistConfig
from .data_collector import DataCollector
from .stock_screener import StockScreener
from .watchlist_manager import WatchlistManager
from .performance_tracker import PerformanceTracker
from .performance_reporter import PerformanceReporter
from .auto_scheduler import AutoScheduler
from .signal_backtest import build_signal_outcome_summary

__all__ = [
    'StockCandidate',
    'WatchlistData', 
    'DataSource',
    'PriceSnapshot',
    'SignalRecord',
    'PerformanceStats',
    'PriceHistory',
    'SignalHistory',
    'WatchlistConfig',
    'DataCollector',
    'StockScreener',
    'WatchlistManager',
    'PerformanceTracker',
    'PerformanceReporter',
    'AutoScheduler',
    'build_signal_outcome_summary',
]

__version__ = '1.1.0'
