"""
数据采集器
从网络采集龙虎榜、热门板块、机构调研数据
"""

import re
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import asdict

from .config import config
from .models import (
    StockCandidate, DragonTigerData, SectorHotData, 
    ResearchData, DataSource
)


class DataCollector:
    """数据采集器类"""
    
    def __init__(self):
        self.config = config
        self.searcher = None  # 延迟初始化
        self._init_searcher()
    
    def _init_searcher(self):
        """初始化搜索器"""
        try:
            from utils.intel_searcher import intel_searcher
            # 检查是否可用
            if hasattr(intel_searcher, 'search'):
                self.searcher = intel_searcher
        except ImportError:
            self.searcher = None
    
    def collect_all(self) -> Dict[str, Any]:
        """
        采集所有数据源
        
        Returns:
            包含所有数据源的字典
        """
        results = {
            'dragon_tiger': self.collect_dragon_tiger(),
            'sector_hot': self.collect_sector_hot(),
            'research': self.collect_research(),
            'collect_time': datetime.now().isoformat(),
        }
        
        # 缓存数据
        self._cache_results(results)
        
        return results
    
    def collect_dragon_tiger(self) -> List[DragonTigerData]:
        """
        采集龙虎榜数据
        
        Returns:
            龙虎榜数据列表
        """
        if not self.searcher:
            return self._get_mock_dragon_tiger()
        
        # 获取今日日期
        today = datetime.now()
        date_str = today.strftime('%Y年%m月%d日')
        last_week = (today - timedelta(days=7)).strftime('%Y年%m月%d日')
        
        # 搜索龙虎榜数据
        keywords = [
            f'A股龙虎榜 {date_str} 机构净买入',
            f'龙虎榜数据 {last_week} 营业部',
            f'{date_str} 龙虎榜 机构专用',
        ]
        
        all_data = []
        for keyword in keywords:
            try:
                results = self.searcher.search(keyword, max_results=10)
                data = self._parse_dragon_tiger_results(results, date_str)
                all_data.extend(data)
            except Exception as e:
                print(f"  搜索龙虎榜失败 [{keyword}]: {e}")
        
        # 去重
        unique_data = self._deduplicate_list(all_data, 'stock_code')
        
        # 缓存
        self._save_cache('dragon_tiger', [d.to_dict() for d in unique_data])
        
        return unique_data
    
    def collect_sector_hot(self) -> List[SectorHotData]:
        """
        采集热门板块数据
        
        Returns:
            热门板块数据列表
        """
        if not self.searcher:
            return self._get_mock_sector_hot()
        
        today = datetime.now()
        date_str = today.strftime('%Y年%m月%d日')
        
        keywords = [
            f'A股热门板块 {date_str} 涨幅',
            f'今日板块热点 {date_str}',
            f'概念板块涨幅榜',
        ]
        
        all_data = []
        for keyword in keywords:
            try:
                results = self.searcher.search(keyword, max_results=8)
                data = self._parse_sector_hot_results(results, date_str)
                all_data.extend(data)
            except Exception as e:
                print(f"  搜索板块失败 [{keyword}]: {e}")
        
        # 去重
        unique_data = self._deduplicate_list(all_data, 'sector_name')
        
        # 缓存
        self._save_cache('sector', [d.to_dict() for d in unique_data])
        
        return unique_data
    
    def collect_research(self) -> List[ResearchData]:
        """
        采集机构调研数据
        
        Returns:
            机构调研数据列表
        """
        if not self.searcher:
            return self._get_mock_research()
        
        # 获取近期的调研数据
        today = datetime.now()
        date_str = today.strftime('%Y年%m月%d日')
        week_ago = (today - timedelta(days=7)).strftime('%Y年%m月%d日')
        
        keywords = [
            f'机构调研 {week_ago} {date_str}',
            f'上市公司调研 {week_ago}',
            f'机构最新调研股票',
        ]
        
        all_data = []
        for keyword in keywords:
            try:
                results = self.searcher.search(keyword, max_results=10)
                data = self._parse_research_results(results, week_ago)
                all_data.extend(data)
            except Exception as e:
                print(f"  搜索机构调研失败 [{keyword}]: {e}")
        
        # 去重
        unique_data = self._deduplicate_list(all_data, 'stock_code')
        
        # 缓存
        self._save_cache('research', [d.to_dict() for d in unique_data])
        
        return unique_data
    
    def _parse_dragon_tiger_results(self, results: List[Dict], date_str: str) -> List[DragonTigerData]:
        """解析龙虎榜搜索结果"""
        data_list = []
        
        for result in results:
            title = result.get('title', '')
            snippet = result.get('snippet', '')
            
            # 提取股票代码和名称
            stock_info = self._extract_stock_info(title + ' ' + snippet)
            if not stock_info:
                continue
            
            # 提取净买入金额
            net_buy = self._extract_net_buy(snippet)
            
            # 提取涨跌幅
            change = self._extract_change(snippet)
            
            data = DragonTigerData(
                date=date_str,
                stock_code=stock_info['code'],
                stock_name=stock_info['name'],
                reason=self._extract_reason(title + ' ' + snippet),
                net_buy=net_buy,
                close_change=change,
                source_url=result.get('url'),
            )
            data_list.append(data)
        
        return data_list
    
    def _parse_sector_hot_results(self, results: List[Dict], date_str: str) -> List[SectorHotData]:
        """解析热门板块搜索结果"""
        data_list = []
        
        for result in results:
            title = result.get('title', '')
            snippet = result.get('snippet', '')
            
            # 提取板块名称
            sector_name = self._extract_sector_name(title + ' ' + snippet)
            if not sector_name:
                continue
            
            # 提取涨跌幅
            change_rate = self._extract_change(snippet)
            
            # 提取龙头股票
            leading_stocks = self._extract_leading_stocks(snippet)
            
            data = SectorHotData(
                date=date_str,
                sector_name=sector_name,
                change_rate=change_rate,
                leading_stocks=leading_stocks,
                reason=self._extract_sector_reason(snippet),
                source_url=result.get('url'),
            )
            data_list.append(data)
        
        return data_list
    
    def _parse_research_results(self, results: List[Dict], date_str: str) -> List[ResearchData]:
        """解析机构调研搜索结果"""
        data_list = []
        
        for result in results:
            title = result.get('title', '')
            snippet = result.get('snippet', '')
            
            # 提取股票信息
            stock_info = self._extract_stock_info(title + ' ' + snippet)
            if not stock_info:
                continue
            
            # 提取机构名称
            org_name = self._extract_org_name(snippet)
            
            data = ResearchData(
                date=date_str,
                stock_code=stock_info['code'],
                stock_name=stock_info['name'],
                org_name=org_name,
                topic=self._extract_topic(title + ' ' + snippet),
                source_url=result.get('url'),
            )
            data_list.append(data)
        
        return data_list
    
    def _extract_stock_info(self, text: str) -> Optional[Dict[str, str]]:
        """从文本中提取股票代码和名称"""
        # 匹配格式如: 贵州茅台(600519)、600519贵州茅台、平安银行(000001)
        patterns = [
            r'([\u4e00-\u9fa5]{2,10})\((\d{6})\)',  # 名称(代码)
            r'(\d{6})([\u4e00-\u9fa5]{2,10})',        # 代码名称
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                if pattern == patterns[0]:
                    return {'name': groups[0], 'code': groups[1]}
                else:
                    return {'name': groups[1], 'code': groups[0]}
        
        return None
    
    def _extract_net_buy(self, text: str) -> float:
        """提取净买入金额"""
        patterns = [
            r'净买入[^\d]*([-\d.]+)万',
            r'机构买入[^\d]*([-\d.]+)万',
            r'买入[^\d]*([-\d.]+)万',
            r'净额[^\d]*([-\d.]+)亿',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                value = float(match.group(1))
                if '亿' in pattern:
                    value *= 10000  # 转换为万
                return value
        
        return 0.0
    
    def _extract_change(self, text: str) -> float:
        """提取涨跌幅"""
        patterns = [
            r'涨[幅达]?([+\-]?\d+\.?\d*)%',
            r'跌[幅达]?([+\-]?\d+\.?\d*)%',
            r'([+\-]?\d+\.?\d*)个点',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return float(match.group(1))
        
        return 0.0
    
    def _extract_reason(self, text: str) -> str:
        """提取上榜原因"""
        reasons = ['连续三日涨停', '当日涨停', '异常波动', '振幅过大', '换手率高', '连续涨停']
        for reason in reasons:
            if reason in text:
                return reason
        return '其他'
    
    def _extract_sector_name(self, text: str) -> Optional[str]:
        """提取板块名称"""
        # 常见板块关键词
        sectors = [
            '人工智能', '新能源汽车', '半导体', '芯片', '锂电池',
            '光伏', '医药', '白酒', '银行', '券商', '军工',
            '元宇宙', '数字经济', '大数据', '云计算', '5G',
            '机器人', '智能制造', '新材料', '稀土', '碳中和',
        ]
        
        for sector in sectors:
            if sector in text:
                return sector
        
        # 尝试提取XXX板块格式
        match = re.search(r'([\u4e00-\u9fa5]+)板块', text)
        if match:
            return match.group(1)
        
        return None
    
    def _extract_leading_stocks(self, text: str) -> List[Dict[str, str]]:
        """提取龙头股票"""
        stocks = []
        
        # 匹配股票列表
        pattern = r'([\u4e00-\u9fa5]{2,10})(?:\(|（)(\d{6})(?:\)|）)'
        matches = re.findall(pattern, text)
        
        for name, code in matches[:5]:  # 最多5只
            stocks.append({'name': name, 'code': code})
        
        return stocks
    
    def _extract_sector_reason(self, text: str) -> str:
        """提取板块异动原因"""
        reasons = [
            '政策利好', '业绩预增', '订单爆发', '技术突破',
            '行业景气', '产能扩张', '产品涨价', '重组并购',
        ]
        for reason in reasons:
            if reason in text:
                return reason
        return '行业消息'
    
    def _extract_org_name(self, text: str) -> str:
        """提取机构名称"""
        # 常见机构类型
        org_types = ['基金', '券商', '保险', '私募', 'QFII', '外资']
        
        for org_type in org_types:
            if org_type in text:
                return f'{org_type}机构'
        
        # 尝试匹配具体机构名
        match = re.search(r'([\u4e00-\u9fa5]{2,6}(?:基金|证券|资产|资本|投资))', text)
        if match:
            return match.group(1)
        
        return '机构投资者'
    
    def _extract_topic(self, text: str) -> Optional[str]:
        """提取调研主题"""
        topics = ['业绩', '产能', '订单', '技术', '市场', '战略', '规划', '研发']
        for topic in topics:
            if topic in text:
                return f'关注{topic}'
        return None
    
    def _deduplicate_list(self, items: List, key: str) -> List:
        """列表去重"""
        seen = set()
        result = []
        
        for item in items:
            item_dict = item.to_dict() if hasattr(item, 'to_dict') else item
            item_key = item_dict.get(key)
            
            if item_key and item_key not in seen:
                seen.add(item_key)
                result.append(item)
        
        return result
    
    def _save_cache(self, source: str, data: List[Dict]):
        """保存缓存"""
        cache_path = self.config.get_cache_path(source)
        
        cache_data = {
            'update_time': datetime.now().isoformat(),
            'data': data,
        }
        
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    
    def load_cache(self, source: str) -> Optional[List[Dict]]:
        """加载缓存"""
        cache_path = self.config.get_cache_path(source)
        
        if not os.path.exists(cache_path):
            return None
        
        # 检查是否过期
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        update_time = datetime.fromisoformat(cache_data['update_time'])
        if (datetime.now() - update_time).total_seconds() > self.config.cache_ttl_hours * 3600:
            return None  # 已过期
        
        return cache_data.get('data')
    
    def _cache_results(self, results: Dict):
        """缓存所有结果"""
        for key in ['dragon_tiger', 'sector_hot', 'research']:
            if key in results and results[key]:
                self._save_cache(key, [d.to_dict() if hasattr(d, 'to_dict') else d for d in results[key]])
    
    # ========== 模拟数据（用于测试） ==========
    
    def _get_mock_dragon_tiger(self) -> List[DragonTigerData]:
        """获取模拟龙虎榜数据"""
        today = datetime.now().strftime('%Y年%m月%d日')
        return [
            DragonTigerData(
                date=today, stock_code='300750', stock_name='宁德时代',
                reason='当日涨停', net_buy=5000.0, close_change=20.0,
                source_url='mock://dragon_tiger'
            ),
            DragonTigerData(
                date=today, stock_code='002594', stock_name='比亚迪',
                reason='连续三日涨停', net_buy=3500.0, close_change=10.0,
                source_url='mock://dragon_tiger'
            ),
            DragonTigerData(
                date=today, stock_code='688981', stock_name='中微公司',
                reason='异常波动', net_buy=2800.0, close_change=15.0,
                source_url='mock://dragon_tiger'
            ),
        ]
    
    def _get_mock_sector_hot(self) -> List[SectorHotData]:
        """获取模拟板块数据"""
        today = datetime.now().strftime('%Y年%m月%d日')
        return [
            SectorHotData(
                date=today, sector_name='人工智能', change_rate=5.5,
                leading_stocks=[
                    {'code': '300750', 'name': '宁德时代'},
                    {'code': '002415', 'name': '海康威视'},
                ],
                reason='政策利好',
                source_url='mock://sector'
            ),
            SectorHotData(
                date=today, sector_name='新能源汽车', change_rate=4.2,
                leading_stocks=[
                    {'code': '002594', 'name': '比亚迪'},
                ],
                reason='销量爆发',
                source_url='mock://sector'
            ),
        ]
    
    def _get_mock_research(self) -> List[ResearchData]:
        """获取模拟机构调研数据"""
        today = datetime.now().strftime('%Y年%m月%d日')
        return [
            ResearchData(
                date=today, stock_code='300661', stock_name='圣邦股份',
                org_name='嘉实基金', org_count=15,
                topic='关注业绩',
                source_url='mock://research'
            ),
            ResearchData(
                date=today, stock_code='002916', stock_name='深南电路',
                org_name='华夏基金', org_count=12,
                topic='关注产能',
                source_url='mock://research'
            ),
        ]
