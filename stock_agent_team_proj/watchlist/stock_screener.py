"""
股票筛选器
基于多维度评分进行股票筛选和优先级排序
"""

import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from .config import config
from .models import StockCandidate, DragonTigerData, SectorHotData, ResearchData


class StockScreener:
    """股票筛选器类"""
    
    def __init__(self):
        self.config = config
        self.weights = config.weights
        self._data_fetcher = None
    
    def _init_data_fetcher(self):
        """延迟初始化数据获取器"""
        if self._data_fetcher is None:
            try:
                from utils.data_fetcher import data_fetcher
                self._data_fetcher = data_fetcher
            except ImportError:
                self._data_fetcher = None
    
    def screen_candidates(
        self,
        dragon_tiger_data: List[DragonTigerData],
        sector_data: List[SectorHotData],
        research_data: List[ResearchData],
        existing_codes: List[str] = None
    ) -> List[StockCandidate]:
        """
        筛选候选股票
        
        Args:
            dragon_tiger_data: 龙虎榜数据
            sector_data: 板块热度数据
            research_data: 机构调研数据
            existing_codes: 已存在于观察池的股票代码（用于排除）
        
        Returns:
            筛选后的候选股票列表
        """
        self._init_data_fetcher()
        
        existing_codes = existing_codes or []
        candidates_dict: Dict[str, StockCandidate] = {}
        
        # 1. 处理龙虎榜数据（权重40%）
        for dt in dragon_tiger_data:
            if dt.stock_code in existing_codes:
                continue
            
            if dt.stock_code not in candidates_dict:
                candidates_dict[dt.stock_code] = StockCandidate(
                    code=dt.stock_code,
                    name=dt.stock_name,
                    add_date=dt.date,
                    add_reason=f'龙虎榜: {dt.reason}',
                    source='dragon_tiger',
                    source_score=0.0,
                    raw_data=dt.to_dict(),
                )
            
            # 计算龙虎榜得分
            dragon_score = self._calc_dragon_tiger_score(dt)
            candidates_dict[dt.stock_code].source_score += dragon_score * self.weights['dragon_tiger']
        
        # 2. 处理板块热度数据（权重30%）
        for sector in sector_data:
            sector_score = self._calc_sector_score(sector)
            
            # 添加板块中的龙头股
            for stock in sector.leading_stocks:
                code = stock['code']
                if code in existing_codes or code in candidates_dict:
                    continue
                
                candidates_dict[code] = StockCandidate(
                    code=code,
                    name=stock['name'],
                    add_date=sector.date,
                    add_reason=f'热门板块: {sector.sector_name}({sector.change_rate}%)',
                    source='sector_hot',
                    source_score=0.0,
                    raw_data=sector.to_dict(),
                )
                
                # 直接添加板块得分
                candidates_dict[code].source_score += sector_score * self.weights['sector_hot']
                
                # 如果该股票同时在龙虎榜中
                for dt in dragon_tiger_data:
                    if dt.stock_code == code:
                        candidates_dict[code].source_score += self._calc_dragon_tiger_score(dt) * self.weights['dragon_tiger']
        
        # 3. 处理机构调研数据（权重30%）
        for research in research_data:
            if research.stock_code in existing_codes:
                continue
            
            research_score = self._calc_research_score(research)
            
            if research.stock_code not in candidates_dict:
                candidates_dict[research.stock_code] = StockCandidate(
                    code=research.stock_code,
                    name=research.stock_name,
                    add_date=research.date,
                    add_reason=f'机构调研: {research.org_name}',
                    source='research',
                    source_score=0.0,
                    raw_data=research.to_dict(),
                )
            
            candidates_dict[research.stock_code].source_score += research_score * self.weights['research']
        
        # 4. 验证候选股票
        validated_candidates = []
        for candidate in candidates_dict.values():
            if self._validate_candidate(candidate):
                validated_candidates.append(candidate)
        
        # 5. 按评分排序
        validated_candidates.sort(key=lambda x: x.source_score, reverse=True)
        
        # 6. 限制数量
        return validated_candidates[:self.config.max_watchlist_size]
    
    def _calc_dragon_tiger_score(self, data: DragonTigerData) -> float:
        """
        计算龙虎榜得分
        
        考虑因素：
        - 机构净买入金额（越高越好）
        - 涨跌幅（涨停板更有价值）
        - 上榜原因（连续涨停更有价值）
        """
        score = 0.0
        
        # 机构净买入得分（满分40）
        if data.net_buy > 0:
            buy_score = min(data.net_buy / 10000, 1.0) * 40  # 1亿以上满分
        else:
            buy_score = max(data.net_buy / 5000, -1) * 10  # 净卖出扣分
        score += buy_score
        
        # 涨跌幅得分（满分30）
        if data.close_change >= 10:  # 涨停
            change_score = 30
        elif data.close_change >= 5:
            change_score = 20
        elif data.close_change >= 0:
            change_score = 10
        else:
            change_score = max(data.close_change, -20)
        score += change_score
        
        # 上榜原因得分（满分30）
        reason_scores = {
            '连续三日涨停': 30,
            '连续涨停': 25,
            '当日涨停': 20,
            '异常波动': 10,
            '振幅过大': 5,
            '换手率高': 5,
        }
        reason_score = reason_scores.get(data.reason, 5)
        score += reason_score
        
        # 归一化到0-100
        return max(0, min(score, 100))
    
    def _calc_sector_score(self, data: SectorHotData) -> float:
        """
        计算板块热度得分
        
        考虑因素：
        - 板块涨跌幅（越高越好）
        - 龙头股数量（越多说明板块越热）
        """
        score = 0.0
        
        # 涨跌幅得分（满分60）
        if data.change_rate >= 7:
            change_score = 60
        elif data.change_rate >= 5:
            change_score = 45
        elif data.change_rate >= 3:
            change_score = 30
        elif data.change_rate >= 1:
            change_score = 15
        else:
            change_score = 5
        score += change_score
        
        # 龙头股数量得分（满分40）
        leading_count = len(data.leading_stocks)
        leading_score = min(leading_count * 10, 40)
        score += leading_score
        
        return max(0, min(score, 100))
    
    def _calc_research_score(self, data: ResearchData) -> float:
        """
        计算机构调研得分
        
        考虑因素：
        - 参与机构数量（越多说明关注度越高）
        - 机构类型（大机构更有价值）
        """
        score = 0.0
        
        # 机构数量得分（满分60）
        if data.org_count >= 30:
            count_score = 60
        elif data.org_count >= 20:
            count_score = 45
        elif data.org_count >= 10:
            count_score = 30
        elif data.org_count >= 5:
            count_score = 15
        else:
            count_score = 10
        score += count_score
        
        # 机构类型得分（满分40）
        if '基金' in data.org_name:
            org_score = 40
        elif '券商' in data.org_name:
            org_score = 35
        elif '保险' in data.org_name:
            org_score = 30
        elif '私募' in data.org_name:
            org_score = 20
        else:
            org_score = 15
        score += org_score
        
        return max(0, min(score, 100))
    
    def _validate_candidate(self, candidate: StockCandidate) -> bool:
        """
        验证候选股票是否有效
        
        筛选条件：
        - 股票代码格式正确
        - 非ST股
        - 流通市值 > 20亿
        - 近5日涨幅 < 30%
        """
        # 检查代码格式
        if not self._is_valid_stock_code(candidate.code):
            return False
        
        # 检查是否为ST股（通过名称判断）
        if candidate.name.startswith('ST') or candidate.name.startswith('*ST'):
            if self.config.exclude_st:
                return False
        
        # 获取详细数据进行验证
        if self._data_fetcher:
            try:
                # 获取股票基本信息
                quote = self._data_fetcher.get_realtime_quote(candidate.code)
                
                if quote:
                    # 检查流通市值
                    market_cap = quote.get('流通市值', 0)
                    if market_cap and market_cap < self.config.min_market_cap:
                        candidate.market_cap = market_cap
                        return False
                    
                    candidate.market_cap = market_cap
                    
                    # 检查是否为ST
                    stock_name = quote.get('名称', candidate.name)
                    if stock_name.startswith('ST') or stock_name.startswith('*ST'):
                        candidate.is_st = True
                        if self.config.exclude_st:
                            return False
                    
                    # 检查5日涨幅
                    change_5d = self._calc_5day_change(candidate.code)
                    candidate.price_change_5d = change_5d
                    
                    if change_5d and change_5d > self.config.max_5day_gain:
                        return False
                        
            except Exception as e:
                # 数据获取失败时，默认通过基本验证
                pass
        
        # 基本验证通过
        return candidate.source_score > 0
    
    def _is_valid_stock_code(self, code: str) -> bool:
        """验证股票代码格式"""
        if not code:
            return False
        
        # 匹配沪深股票代码：6位数字
        # 上海: 600xxx, 601xxx, 688xxx
        # 深圳: 000xxx, 001xxx, 002xxx, 300xxx
        pattern = r'^(60[018]\d{3}|00[012]\d{3}|300\d{3}|688\d{3})$'
        return bool(re.match(pattern, code))
    
    def _calc_5day_change(self, code: str) -> Optional[float]:
        """计算近5日涨跌幅"""
        if not self._data_fetcher:
            return None
        
        try:
            # 获取日K线数据
            klines = self._data_fetcher.get_daily_kline(code, period=5, adjust='qfq')
            
            if not klines or len(klines) < 2:
                return None
            
            # 计算涨跌幅
            first_close = float(klines[0].get('close', 0))
            last_close = float(klines[-1].get('close', 0))
            
            if first_close > 0:
                change = (last_close - first_close) / first_close * 100
                return change
            
        except Exception:
            pass
        
        return None
    
    def get_screening_report(self, candidates: List[StockCandidate]) -> str:
        """
        生成筛选报告
        
        Args:
            candidates: 候选股票列表
        
        Returns:
            格式化的报告文本
        """
        if not candidates:
            return "暂无符合条件的候选股票"
        
        report_lines = [
            "=" * 60,
            "📊 股票筛选报告",
            "=" * 60,
            f"筛选时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"候选数量: {len(candidates)} 只",
            "",
            "-" * 60,
            "筛选标准:",
            f"  • 非ST、非退市风险股: {'是' if self.config.exclude_st else '否'}",
            f"  • 流通市值 > {self.config.min_market_cap}亿",
            f"  • 近5日涨幅 < {self.config.max_5day_gain}%",
            "",
            "-" * 60,
            "评分权重:",
            f"  • 龙虎榜信号: {self.weights['dragon_tiger']*100:.0f}%",
            f"  • 板块热度: {self.weights['sector_hot']*100:.0f}%",
            f"  • 机构调研: {self.weights['research']*100:.0f}%",
            "",
            "-" * 60,
            "候选股票列表:",
            "",
        ]
        
        for i, c in enumerate(candidates, 1):
            status_icon = {
                'pending': '⏳',
                'analyzing': '🔍',
                'watching': '👀',
                'archived': '📁',
            }.get(c.status, '❓')
            
            report_lines.append(
                f"  {i}. {status_icon} {c.name}({c.code}) "
                f"评分:{c.source_score:.1f} | {c.add_reason}"
            )
            
            if c.market_cap:
                report_lines.append(f"     市值:{c.market_cap:.1f}亿 | 5日涨跌:{c.price_change_5d or 0:+.1f}%")
        
        report_lines.extend([
            "",
            "=" * 60,
            "建议优先关注评分较高的股票",
            "=" * 60,
        ])
        
        return '\n'.join(report_lines)
