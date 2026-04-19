"""
数据时效性检查器
验证各类数据的新鲜度，过滤过期信息
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from utils.logger import get_logger

logger = get_logger('freshness_checker')


class FreshnessLevel(Enum):
    """数据新鲜度等级"""
    FRESH = "fresh"           # 新鲜，可直接使用
    ACCEPTABLE = "acceptable" # 可接受，标注后使用
    STALE = "stale"          # 陈旧，建议补充说明
    EXPIRED = "expired"       # 过期，不应使用


@dataclass
class FreshnessReport:
    """数据新鲜度报告"""
    data_type: str
    data_time: Optional[datetime]
    check_time: datetime
    freshness_level: FreshnessLevel
    age_hours: Optional[float] = None
    age_days: Optional[float] = None
    warning: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'data_type': self.data_type,
            'data_time': self.data_time.strftime('%Y-%m-%d %H:%M') if self.data_time else None,
            'freshness': self.freshness_level.value,
            'age_hours': self.age_hours,
            'age_days': self.age_days,
            'warning': self.warning
        }


class FreshnessChecker:
    """数据时效性检查器"""
    
    # 各类数据的时效性阈值（小时）
    FRESHNESS_THRESHOLDS = {
        # API数据
        'realtime_quote': {'fresh': 1, 'acceptable': 24, 'stale': 168},      # 实时行情
        'kline_daily': {'fresh': 24, 'acceptable': 72, 'stale': 168},         # 日K线
        'kline_weekly': {'fresh': 168, 'acceptable': 336, 'stale': 720},      # 周K线
        'financial_quarterly': {'fresh': 720, 'acceptable': 2160, 'stale': 4320},  # 季报（30/90/180天）
        'financial_annual': {'fresh': 2160, 'acceptable': 4320, 'stale': 8640},    # 年报
        'fund_flow': {'fresh': 24, 'acceptable': 72, 'stale': 168},           # 资金流向
        'north_bound': {'fresh': 24, 'acceptable': 72, 'stale': 168},         # 北向资金
        
        # 网络情报
        'news': {'fresh': 24, 'acceptable': 72, 'stale': 168},               # 新闻（1/3/7天）
        'research_report': {'fresh': 168, 'acceptable': 336, 'stale': 720},  # 研报（7/14/30天）
        'market_sentiment': {'fresh': 48, 'acceptable': 96, 'stale': 168},   # 市场舆情
        'industry_news': {'fresh': 72, 'acceptable': 168, 'stale': 336},     # 行业动态
        'policy_news': {'fresh': 168, 'acceptable': 336, 'stale': 720},      # 政策新闻
        'macro_analysis': {'fresh': 168, 'acceptable': 336, 'stale': 720},   # 宏观分析
    }
    
    def __init__(self):
        self.now = datetime.now()
    
    def check(self, data_type: str, data_time: Optional[datetime] = None) -> FreshnessReport:
        """检查数据新鲜度
        
        Args:
            data_type: 数据类型
            data_time: 数据时间戳
            
        Returns:
            FreshnessReport
        """
        thresholds = self.FRESHNESS_THRESHOLDS.get(data_type, 
            {'fresh': 24, 'acceptable': 72, 'stale': 168})
        
        if data_time is None:
            return FreshnessReport(
                data_type=data_type,
                data_time=None,
                check_time=self.now,
                freshness_level=FreshnessLevel.STALE,
                warning="数据时间未知，请核实来源"
            )
        
        # 计算数据年龄
        age = self.now - data_time
        age_hours = age.total_seconds() / 3600
        age_days = age_hours / 24
        
        # 判断新鲜度等级
        if age_hours <= thresholds['fresh']:
            level = FreshnessLevel.FRESH
            warning = None
        elif age_hours <= thresholds['acceptable']:
            level = FreshnessLevel.ACCEPTABLE
            warning = f"数据已过 {age_days:.1f} 天，建议确认是否有更新"
        elif age_hours <= thresholds['stale']:
            level = FreshnessLevel.STALE
            warning = f"数据较旧（{age_days:.1f} 天），可能影响分析准确性"
        else:
            level = FreshnessLevel.EXPIRED
            warning = f"数据已过期（{age_days:.1f} 天），不应使用"
        
        return FreshnessReport(
            data_type=data_type,
            data_time=data_time,
            check_time=self.now,
            freshness_level=level,
            age_hours=round(age_hours, 1),
            age_days=round(age_days, 1),
            warning=warning
        )
    
    def check_search_results(
        self, 
        results: List[Dict[str, Any]], 
        data_type: str = 'news'
    ) -> Tuple[List[Dict[str, Any]], FreshnessReport]:
        """检查搜索结果的新鲜度，过滤过期内容
        
        Args:
            results: 搜索结果列表
            data_type: 数据类型
            
        Returns:
            (过滤后的结果, 整体新鲜度报告)
        """
        valid_results = []
        all_reports = []
        
        for item in results:
            # 尝试解析时间
            time_str = item.get('time') or item.get('publish_time') or item.get('date')
            data_time = self._parse_time(time_str) if time_str else None
            
            # 检查新鲜度
            report = self.check(data_type, data_time)
            all_reports.append(report)
            
            # 只保留非过期数据
            if report.freshness_level != FreshnessLevel.EXPIRED:
                item['freshness'] = report.to_dict()
                valid_results.append(item)
            else:
                logger.warning(f"过滤过期数据: {item.get('title', '')[:50]}... ({report.warning})")
        
        # 计算整体新鲜度
        if all_reports:
            fresh_count = sum(1 for r in all_reports if r.freshness_level == FreshnessLevel.FRESH)
            overall_level = FreshnessLevel.FRESH if fresh_count >= len(all_reports) * 0.6 else \
                           FreshnessLevel.ACCEPTABLE if fresh_count >= len(all_reports) * 0.3 else \
                           FreshnessLevel.STALE
        else:
            overall_level = FreshnessLevel.STALE
        
        overall_report = FreshnessReport(
            data_type=data_type,
            data_time=None,
            check_time=self.now,
            freshness_level=overall_level,
            warning=f"有效数据 {len(valid_results)}/{len(results)} 条"
        )
        
        return valid_results, overall_report
    
    def _parse_time(self, time_str: str) -> Optional[datetime]:
        """解析各种格式的时间字符串"""
        formats = [
            '%Y-%m-%dT%H:%M:%S%z',      # ISO格式带时区
            '%Y-%m-%dT%H:%M:%S',         # ISO格式
            '%Y-%m-%d %H:%M:%S',         # 标准格式
            '%Y-%m-%d %H:%M',            # 简化格式
            '%Y-%m-%d',                  # 仅日期
            '%Y年%m月%d日',              # 中文格式
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(time_str, fmt)
            except (ValueError, TypeError):
                continue
        
        # 尝试提取相对时间
        if '小时前' in str(time_str) or '小时' in str(time_str):
            return self.now
        elif '今天' in str(time_str):
            return self.now
        elif '昨天' in str(time_str):
            return self.now - timedelta(days=1)
        
        return None
    
    def get_freshness_summary(self, reports: List[FreshnessReport]) -> Dict[str, Any]:
        """生成新鲜度摘要报告"""
        if not reports:
            return {'status': 'no_data'}
        
        by_level = {}
        for r in reports:
            level = r.freshness_level.value
            by_level[level] = by_level.get(level, 0) + 1
        
        avg_age = sum(r.age_days or 0 for r in reports if r.age_days) / max(
            sum(1 for r in reports if r.age_days), 1
        )
        
        return {
            'status': 'ok',
            'total_items': len(reports),
            'by_level': by_level,
            'avg_age_days': round(avg_age, 1),
            'warnings': [r.warning for r in reports if r.warning and r.freshness_level in 
                        (FreshnessLevel.STALE, FreshnessLevel.EXPIRED)]
        }


# 便捷函数
def check_data_freshness(data_type: str, data_time: Optional[datetime] = None) -> FreshnessReport:
    """检查数据新鲜度"""
    checker = FreshnessChecker()
    return checker.check(data_type, data_time)


def filter_stale_results(
    results: List[Dict[str, Any]], 
    data_type: str = 'news'
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """过滤过期搜索结果"""
    checker = FreshnessChecker()
    valid_results, report = checker.check_search_results(results, data_type)
    summary = checker.get_freshness_summary([report])
    return valid_results, summary
