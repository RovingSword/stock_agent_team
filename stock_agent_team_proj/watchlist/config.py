"""
观察池配置文件
定义筛选标准、时间设置、缓存策略等
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List
from datetime import time


@dataclass
class WatchlistConfig:
    """观察池配置类"""
    
    # ========== 数据路径配置 ==========
    data_dir: str = field(default_factory=lambda: os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'data'))
    watchlist_file: str = 'watchlist.json'
    dragon_tiger_file: str = 'dragon_tiger.json'
    sector_file: str = 'sector_hot.json'
    research_file: str = 'research.json'
    analysis_history_file: str = 'analysis_history.json'
    
    # ========== 筛选标准配置 ==========
    # 流通市值下限（亿元）
    min_market_cap: float = 20.0
    
    # 近5日最大涨幅（%）
    max_5day_gain: float = 30.0
    
    # ST股过滤
    exclude_st: bool = True
    
    # 退市风险股过滤
    exclude_delisting_risk: bool = True
    
    # 观察池最大容量
    max_watchlist_size: int = 30
    
    # 候选股采集数量上限（每数据源）
    max_candidates_per_source: int = 50
    
    # ========== 评分权重配置 ==========
    # 优先级权重
    weights: Dict[str, float] = field(default_factory=lambda: {
        'dragon_tiger': 0.40,   # 龙虎榜信号
        'sector_hot': 0.30,    # 板块热度
        'research': 0.30,      # 机构调研
    })
    
    # ========== 时间配置 ==========
    # 每日数据采集时间（下午收盘后）
    daily_collect_time: str = '16:30'
    
    # 每周观察池更新+分析时间（周六）
    weekly_update_time: str = '10:00'
    
    # 分析间隔（天）
    analysis_interval_days: int = 3
    
    # ========== 缓存策略 ==========
    # 数据缓存有效期（小时）
    cache_ttl_hours: int = 24
    
    # 龙虎榜数据保留天数
    dragon_tiger_retention_days: int = 7
    
    # ========== 状态配置 ==========
    candidate_statuses: List[str] = field(default_factory=lambda: [
        'pending',      # 待处理
        'analyzing',    # 分析中
        'watching',     # 观察中
        'archived',     # 已归档
        'removed',      # 已移除
    ])
    
    # ========== 搜索关键词配置 ==========
    search_keywords: Dict[str, str] = field(default_factory=lambda: {
        'dragon_tiger': 'A股龙虎榜 机构净买入',
        'sector_hot': 'A股热门板块 涨幅居前',
        'research': '机构调研 股票',
    })
    
    def __post_init__(self):
        """确保数据目录存在"""
        os.makedirs(self.data_dir, exist_ok=True)
    
    def get_watchlist_path(self) -> str:
        """获取观察池文件路径"""
        return os.path.join(self.data_dir, self.watchlist_file)
    
    def get_cache_path(self, source: str) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.data_dir, f'{source}.json')
    
    def get_full_paths(self) -> Dict[str, str]:
        """获取所有数据文件路径"""
        return {
            'watchlist': self.get_watchlist_path(),
            'dragon_tiger': self.get_cache_path('dragon_tiger'),
            'sector': self.get_cache_path('sector'),
            'research': self.get_cache_path('research'),
            'analysis_history': os.path.join(self.data_dir, self.analysis_history_file),
        }


# 全局配置实例
config = WatchlistConfig()
