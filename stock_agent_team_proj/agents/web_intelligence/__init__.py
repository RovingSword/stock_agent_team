"""
网络情报搜集模块
通过网络搜索获取实时市场情报，补充API数据的不足
"""
from .gatherer import WebIntelligenceGatherer, IntelligenceReport

__all__ = ['WebIntelligenceGatherer', 'IntelligenceReport']
