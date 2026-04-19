"""
网络情报搜集器
通过多维度网络搜索获取实时市场情报
支持时效性检查和来源可信度验证
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from utils.logger import get_logger
from utils.freshness_checker import FreshnessChecker, FreshnessLevel
from utils.source_validator import source_validator, SourceType, CredibilityLevel

logger = get_logger('web_intelligence')


@dataclass
class IntelligenceItem:
    """单条情报"""
    source: str           # 来源类型：news, research, sentiment, industry
    title: str            # 标题
    summary: str          # 摘要
    url: Optional[str] = None
    time: Optional[str] = None
    sentiment: str = "neutral"  # positive, negative, neutral
    relevance: float = 0.5      # 相关度 0-1
    credibility: Optional[Dict[str, Any]] = None  # 可信度信息
    warning: Optional[str] = None  # 警告信息


@dataclass
class IntelligenceReport:
    """网络情报报告"""
    stock_code: str
    stock_name: str
    gather_time: str
    
    # 各维度情报
    news: List[IntelligenceItem] = field(default_factory=list)
    research: List[IntelligenceItem] = field(default_factory=list)
    sentiment: List[IntelligenceItem] = field(default_factory=list)
    industry: List[IntelligenceItem] = field(default_factory=list)
    macro: List[IntelligenceItem] = field(default_factory=list)
    
    # 综合分析
    overall_sentiment: str = "neutral"
    key_positive: List[str] = field(default_factory=list)
    key_negative: List[str] = field(default_factory=list)
    hot_topics: List[str] = field(default_factory=list)
    
    # 时效性统计
    freshness_summary: Dict[str, Any] = field(default_factory=dict)
    
    # 可信度统计
    credibility_summary: Dict[str, Any] = field(default_factory=dict)
    
    # 机构观点汇总（高可信度）
    institutional_views: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'gather_time': self.gather_time,
            'news': [
                {
                    'title': i.title, 
                    'summary': i.summary, 
                    'sentiment': i.sentiment, 
                    'time': i.time,
                    'credibility': i.credibility,
                    'warning': i.warning
                } for i in self.news
            ],
            'research': [
                {
                    'title': i.title, 
                    'summary': i.summary, 
                    'sentiment': i.sentiment, 
                    'time': i.time,
                    'credibility': i.credibility,
                    'warning': i.warning
                } for i in self.research
            ],
            'sentiment': [
                {
                    'title': i.title, 
                    'summary': i.summary, 
                    'sentiment': i.sentiment, 
                    'time': i.time,
                    'credibility': i.credibility,
                    'warning': i.warning
                } for i in self.sentiment
            ],
            'industry': [
                {
                    'title': i.title, 
                    'summary': i.summary, 
                    'sentiment': i.sentiment, 
                    'time': i.time,
                    'credibility': i.credibility,
                    'warning': i.warning
                } for i in self.industry
            ],
            'macro': [
                {
                    'title': i.title, 
                    'summary': i.summary, 
                    'sentiment': i.sentiment, 
                    'time': i.time,
                    'credibility': i.credibility,
                    'warning': i.warning
                } for i in self.macro
            ],
            'overall_sentiment': self.overall_sentiment,
            'key_positive': self.key_positive,
            'key_negative': self.key_negative,
            'hot_topics': self.hot_topics,
            'freshness_summary': self.freshness_summary,
            'credibility_summary': self.credibility_summary,
            'institutional_views': self.institutional_views
        }


class WebIntelligenceGatherer:
    """网络情报搜集器
    
    用于生成搜索任务模板，由主Agent执行搜集后传入结果
    支持时效性检查和来源可信度验证
    """
    
    # 搜索任务模板
    SEARCH_TEMPLATES = {
        'news': {
            'description': '财经新闻搜索',
            'query_template': '{stock_name} {stock_code} 最新消息',
            'sources': ['新浪财经', '东方财富', '同花顺'],
            'max_results': 5
        },
        'research': {
            'description': '券商研报搜索',
            'query_template': '{stock_name} 研报 目标价 评级',
            'sources': ['东方财富研报', '慧博投研'],
            'max_results': 3
        },
        'sentiment': {
            'description': '市场舆情搜索',
            'query_template': '{stock_name} 股吧 讨论',
            'sources': ['雪球', '东方财富股吧'],
            'max_results': 3
        },
        'industry': {
            'description': '行业动态搜索',
            'query_template': '{industry} 行业 政策 最新动态',
            'sources': ['行业媒体', '政府公告'],
            'max_results': 3
        },
        'macro': {
            'description': '宏观市场搜索',
            'query_template': 'A股 大盘 趋势 分析',
            'sources': ['财经媒体'],
            'max_results': 3
        }
    }
    
    # 行业映射
    INDUSTRY_MAP = {
        '002202': '风电',  # 金风科技
        '600519': '白酒',  # 贵州茅台
        '000858': '白酒',  # 五粮液
        '601318': '保险',  # 中国平安
        '000333': '家电',  # 美的集团
        '600036': '银行',  # 招商银行
        '300750': '电池',  # 宁德时代
        '601012': '光伏',  # 隆基绿能
        '300058': '广告营销',  # 蓝色光标
        # 可扩展...
    }
    
    def __init__(self):
        self.logger = logger
    
    def get_search_tasks(self, stock_code: str, stock_name: str) -> List[Dict[str, Any]]:
        """生成搜索任务列表
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            
        Returns:
            搜索任务列表，供主Agent执行
        """
        tasks = []
        industry = self.INDUSTRY_MAP.get(stock_code, '相关行业')
        
        for task_type, template in self.SEARCH_TEMPLATES.items():
            query = template['query_template'].format(
                stock_name=stock_name,
                stock_code=stock_code,
                industry=industry
            )
            tasks.append({
                'type': task_type,
                'description': template['description'],
                'query': query,
                'max_results': template['max_results']
            })
        
        return tasks
    
    def build_report(
        self, 
        stock_code: str, 
        stock_name: str,
        search_results: Dict[str, List[Dict[str, Any]]],
        check_freshness: bool = True,
        check_credibility: bool = True,
        min_credibility_score: float = 0.25
    ) -> IntelligenceReport:
        """根据搜索结果构建情报报告
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            search_results: 各类搜索结果 {type: [results]}
            check_freshness: 是否检查时效性（默认开启）
            check_credibility: 是否检查来源可信度（默认开启）
            min_credibility_score: 最低可信度阈值（默认0.25）
            
        Returns:
            IntelligenceReport
        """
        report = IntelligenceReport(
            stock_code=stock_code,
            stock_name=stock_name,
            gather_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        # 时效性检查器
        freshness_checker = FreshnessChecker() if check_freshness else None
        freshness_summary = {}
        credibility_summary = {}
        
        # 数据类型到时效性类型的映射
        type_mapping = {
            'news': 'news',
            'research': 'research_report',
            'sentiment': 'market_sentiment',
            'industry': 'industry_news',
            'macro': 'macro_analysis'
        }
        
        # 统计
        total_items = 0
        high_credibility_items = 0
        low_credibility_items = 0
        institutional_items = 0
        
        # 解析各类结果
        for source_type, results in search_results.items():
            items = []
            valid_count = 0
            filtered_by_freshness = 0
            filtered_by_credibility = 0
            
            for r in results:
                total_items += 1
                
                # 1. 时效性检查
                if freshness_checker and check_freshness:
                    time_str = r.get('time') or r.get('publish_time') or r.get('date')
                    data_time = freshness_checker._parse_time(time_str) if time_str else None
                    
                    freshness_type = type_mapping.get(source_type, 'news')
                    freshness_report = freshness_checker.check(freshness_type, data_time)
                    
                    # 过滤过期数据
                    if freshness_report.freshness_level == FreshnessLevel.EXPIRED:
                        self.logger.warning(
                            f"[{source_type}] 过滤过期数据: {r.get('title', '')[:30]}... "
                            f"(年龄: {freshness_report.age_days:.0f}天)"
                        )
                        filtered_by_freshness += 1
                        continue
                    
                    # 记录新鲜度信息
                    r['freshness'] = freshness_report.to_dict()
                
                # 2. 来源可信度验证
                if check_credibility:
                    validated = source_validator.validate_intelligence_item(r)
                    cred_info = validated.get('credibility', {})
                    cred_score = cred_info.get('score', 0.5)
                    
                    # 统计可信度分布
                    if cred_score >= 0.6:
                        high_credibility_items += 1
                    elif cred_score < 0.3:
                        low_credibility_items += 1
                    
                    # 统计机构观点
                    if cred_info.get('is_institutional', False):
                        institutional_items += 1
                        report.institutional_views.append({
                            'type': source_type,
                            'title': validated.get('title', ''),
                            'summary': validated.get('summary', '')[:100],
                            'credibility_score': cred_score
                        })
                    
                    # 过滤低可信度内容（但保留警告信息供参考）
                    if cred_score < min_credibility_score:
                        self.logger.warning(
                            f"[{source_type}] 低可信度来源({cred_score:.2f}): "
                            f"{validated.get('warning', '')} - {r.get('title', '')[:30]}..."
                        )
                        filtered_by_credibility += 1
                        # 低可信度内容仍然保留，但标记警告
                        r['credibility'] = cred_info
                        r['warning'] = validated.get('warning')
                    else:
                        r['credibility'] = cred_info
                        r['warning'] = validated.get('warning')
                    
                    valid_count += 1
                else:
                    valid_count += 1
                
                # 3. 创建情报项
                item = IntelligenceItem(
                    source=source_type,
                    title=r.get('title', ''),
                    summary=r.get('summary', r.get('content', r.get('title', '')))[:200],
                    url=r.get('url'),
                    time=r.get('time'),
                    sentiment=self._detect_sentiment(r.get('title', '') + ' ' + r.get('summary', '')),
                    relevance=r.get('relevance', 0.5),
                    credibility=r.get('credibility'),
                    warning=r.get('warning')
                )
                items.append(item)
            
            # 记录该类型的统计
            if check_freshness:
                freshness_summary[source_type] = {
                    'total': len(results),
                    'valid': len(items),
                    'filtered': filtered_by_freshness
                }
            
            # 按类型存入报告
            if source_type == 'news':
                report.news = items
            elif source_type == 'research':
                report.research = items
            elif source_type == 'sentiment':
                report.sentiment = items
            elif source_type == 'industry':
                report.industry = items
            elif source_type == 'macro':
                report.macro = items
        
        # 存入统计信息
        report.freshness_summary = freshness_summary
        report.credibility_summary = {
            'total_items': total_items,
            'high_credibility': high_credibility_items,
            'low_credibility': low_credibility_items,
            'institutional_views': institutional_items,
            'high_ratio': round(high_credibility_items / max(total_items, 1), 2),
            'institutional_ratio': round(institutional_items / max(total_items, 1), 2)
        }
        
        # 综合分析
        self._analyze_overall(report)
        
        return report
    
    def _detect_sentiment(self, text: str) -> str:
        """简单的情绪检测"""
        positive_words = ['利好', '上涨', '突破', '增长', '盈利', '超预期', '买入', '推荐']
        negative_words = ['利空', '下跌', '亏损', '风险', '下调', '减持', '预警', '回避']
        
        pos_count = sum(1 for w in positive_words if w in text)
        neg_count = sum(1 for w in negative_words if w in text)
        
        if pos_count > neg_count:
            return 'positive'
        elif neg_count > pos_count:
            return 'negative'
        return 'neutral'
    
    def _analyze_overall(self, report: IntelligenceReport):
        """综合分析情报（考虑可信度权重）"""
        all_items = (
            report.news + report.research + 
            report.sentiment + report.industry + report.macro
        )
        
        if not all_items:
            return
        
        # 加权情绪计算（可信度高的权重更大）
        weighted_pos = 0.0
        weighted_neg = 0.0
        total_weight = 0.0
        
        for item in all_items:
            # 可信度作为权重
            cred_score = 0.5
            if item.credibility:
                cred_score = item.credibility.get('score', 0.5)
            
            # 机构观点额外加权
            if item.credibility and item.credibility.get('is_institutional'):
                cred_score *= 1.5
            
            weight = cred_score
            total_weight += weight
            
            if item.sentiment == 'positive':
                weighted_pos += weight
            elif item.sentiment == 'negative':
                weighted_neg += weight
        
        # 计算加权情绪比例
        pos_ratio = weighted_pos / max(total_weight, 1)
        neg_ratio = weighted_neg / max(total_weight, 1)
        
        if pos_ratio > 0.4:
            report.overall_sentiment = 'positive'
        elif neg_ratio > 0.4:
            report.overall_sentiment = 'negative'
        else:
            report.overall_sentiment = 'neutral'
        
        # 提取关键点（优先高可信度）
        sorted_items = sorted(
            all_items, 
            key=lambda x: x.credibility.get('score', 0.5) if x.credibility else 0.5,
            reverse=True
        )
        
        for item in sorted_items:
            # 跳过低可信度来源的关键点
            if item.credibility and item.credibility.get('score', 0.5) < 0.3:
                continue
            
            if item.sentiment == 'positive' and len(report.key_positive) < 5:
                # 标注来源类型
                label = ""
                if item.credibility and item.credibility.get('is_institutional'):
                    label = "[机构]"
                elif item.credibility and item.credibility.get('source_type') == 'self_media':
                    label = "[个人]"
                report.key_positive.append(f"{label}{item.title[:45]}")
            elif item.sentiment == 'negative' and len(report.key_negative) < 5:
                label = ""
                if item.credibility and item.credibility.get('is_institutional'):
                    label = "[机构]"
                elif item.credibility and item.credibility.get('source_type') == 'self_media':
                    label = "[个人]"
                report.key_negative.append(f"{label}{item.title[:45]}")
        
        # 热点话题（取前3条新闻）
        report.hot_topics = [i.title[:30] for i in report.news[:3]]


# 便捷函数
def create_gatherer() -> WebIntelligenceGatherer:
    """创建情报搜集器实例"""
    return WebIntelligenceGatherer()
