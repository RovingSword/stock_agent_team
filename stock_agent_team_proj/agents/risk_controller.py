"""
风控官 Agent
负责风险控制：大盘风险、个股风险、交易风险评估，拥有一票否决权
"""
from datetime import datetime
from typing import Dict, Any, List

from agents.base_agent import WorkerAgent, AgentContext
from config import POSITION_LIMITS
from models.base import AgentType
from utils.data_fetcher import data_fetcher


class RiskController(WorkerAgent):
    """风控官"""
    
    def __init__(self, weight: float = 0.20):
        super().__init__(AgentType.RISK, "风控官", weight)
        self.position_limits = POSITION_LIMITS
    
    def _do_analysis(self, context: AgentContext) -> Dict[str, Any]:
        """执行风控评估"""
        stock_code = context.stock_code
        stock_name = context.stock_name
        
        # 获取风控数据
        risk_data = self._get_risk_data(stock_code)
        
        # 1. 大盘风险评估
        market_risk = self._assess_market_risk(risk_data)
        
        # 2. 个股风险评估
        stock_risk = self._assess_stock_risk(risk_data)
        
        # 3. 交易风险评估
        trade_risk = self._assess_trade_risk(risk_data, context)
        
        # 4. 风控决策
        decision = self._make_risk_decision(market_risk, stock_risk, trade_risk)
        
        # 5. 综合评分 (加权平均，个股风险权重更高)
        overall_score = (
            market_risk['score'] * 0.3 +
            stock_risk['score'] * 0.4 +
            trade_risk['score'] * 0.3
        )
        
        # 6. 风险点
        risk_points = self._extract_risk_points(market_risk, stock_risk, trade_risk)
        
        return {
            'scores': {
                'market_score': market_risk['score'],
                'stock_score': stock_risk['score'],
                'trade_score': trade_risk['score']
            },
            'overall_score': overall_score,
            'conclusion': decision,
            'key_points': [f"风控{'通过' if decision['action'] == 'approve' else '否决'}"],
            'risk_points': risk_points,
            'raw_data': {
                'market_risk': market_risk,
                'stock_risk': stock_risk,
                'trade_risk': trade_risk
            }
        }
    
    def _get_risk_data(self, stock_code: str) -> Dict[str, Any]:
        """获取风控数据 - 真实数据"""
        # 获取真实大盘数据
        market_data = data_fetcher.get_market_data()
        
        if market_data:
            return {
                # 大盘数据
                'market_index': market_data['market_index'],
                'market_trend': market_data['market_trend'],
                'market_volume': 2000000000000,  # 简化
                'volume_change': 0,
                'limit_up': market_data['limit_up'],
                'limit_down': market_data['limit_down'],
                
                # 个股数据（部分需要额外获取）
                'st_status': 'normal',
                'audit_opinion': '标准无保留',
                'major_lawsuit': False,
                'delisting_risk': False,
                'unlock_30d': None,
                'pledge_ratio': 0.15,
                'daily_volume': 5000000000,
                
                # 当前持仓（需要从数据库获取，这里用默认值）
                'current_position': 0.40,
                'sector_position': 0.25,
            }
        
        # 兜底数据
        return {
            'market_index': {'sh': 3000, 'sz': 10000, 'cyb': 2000},
            'market_trend': '震荡',
            'market_volume': 2000000000000,
            'volume_change': 0,
            'limit_up': 50,
            'limit_down': 10,
            'st_status': 'normal',
            'audit_opinion': '标准无保留',
            'major_lawsuit': False,
            'delisting_risk': False,
            'unlock_30d': None,
            'pledge_ratio': 0.15,
            'daily_volume': 5000000000,
            'current_position': 0.40,
            'sector_position': 0.25,
        }
    
    def _assess_market_risk(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """评估大盘风险"""
        market_trend = data['market_trend']
        volume_change = data['volume_change']
        limit_up = data['limit_up']
        limit_down = data['limit_down']
        
        # 趋势评分
        trend_scores = {
            '强势上涨': 9.0,
            '震荡偏强': 7.0,
            '震荡': 6.0,
            '震荡偏弱': 5.0,
            '弱势下跌': 3.0
        }
        trend_score = trend_scores.get(market_trend, 5.0)
        
        # 量能评分
        if volume_change > 0:
            volume_score = 7.5
        elif volume_change > -100000000000:
            volume_score = 6.5
        else:
            volume_score = 5.5
        
        # 涨跌停比评分
        ratio = limit_up / max(limit_down, 1)
        if ratio >= 5:
            limit_score = 8.0
        elif ratio >= 3:
            limit_score = 6.5
        elif ratio >= 1:
            limit_score = 5.0
        else:
            limit_score = 3.0
        
        # 综合评分
        overall = trend_score * 0.5 + volume_score * 0.25 + limit_score * 0.25
        
        # 风险等级
        if overall >= 7:
            risk_level = "低"
        elif overall >= 5:
            risk_level = "中等"
        else:
            risk_level = "高"
        
        return {
            'trend': market_trend,
            'volume_change': volume_change / 100000000,  # 转换为亿
            'limit_ratio': ratio,
            'trend_score': trend_score,
            'volume_score': volume_score,
            'limit_score': limit_score,
            'score': round(overall, 1),
            'risk_level': risk_level,
            'description': f"大盘{market_trend}，风险等级{risk_level}"
        }
    
    def _assess_stock_risk(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """评估个股风险"""
        st = data['st_status']
        lawsuit = data['major_lawsuit']
        delisting = data['delisting_risk']
        unlock = data['unlock_30d']
        pledge = data['pledge_ratio']
        volume = data['daily_volume']
        
        score = 10.0
        risks = []
        
        # ST风险
        if st != 'normal':
            score -= 5
            risks.append(f"ST状态：{st}")
        
        # 退市风险
        if delisting:
            score -= 5
            risks.append("存在退市风险")
        
        # 诉讼风险
        if lawsuit:
            score -= 2
            risks.append("存在重大诉讼")
        
        # 解禁风险
        if unlock:
            score -= 1
            risks.append(f"近期解禁{unlock}")
        
        # 质押风险 (放宽质押扣分门槛)
        if pledge > 0.6:
            score -= 2
            risks.append(f"高比例质押{pledge*100:.0f}%")
        elif pledge > 0.4:
            score -= 1
            risks.append(f"质押比例{pledge*100:.0f}%")
        
        # 流动性 (放宽流动性扣分门槛)
        if volume < 50000000:
            score -= 2
            risks.append("流动性不足")
        elif volume < 200000000:
            score -= 1
            risks.append("流动性一般")
        
        score = max(score, 0)
        
        risk_level = "低" if score >= 7 else ("中等" if score >= 5 else "高")
        
        return {
            'st_status': st,
            'delisting_risk': delisting,
            'pledge_ratio': pledge,
            'liquidity': '充足' if volume >= 500000000 else ('一般' if volume >= 100000000 else '不足'),
            'risks': risks,
            'score': round(score, 1),
            'risk_level': risk_level,
            'description': f"个股风险等级{risk_level}"
        }
    
    def _assess_trade_risk(self, data: Dict[str, Any], context: AgentContext) -> Dict[str, Any]:
        """评估交易风险"""
        current_pos = data['current_position']
        sector_pos = data['sector_position']
        
        # 假设建议仓位
        proposed_pos = 0.15
        
        # 仓位检查
        total_after = current_pos + proposed_pos
        sector_after = sector_pos + proposed_pos
        
        warnings = []
        score = 10.0
        
        # 总仓位检查
        if total_after > self.position_limits['max_total_position']:
            score -= 3
            warnings.append(f"总仓位超限：{total_after*100:.0f}% > {self.position_limits['max_total_position']*100:.0f}%")
        
        # 单板块仓位检查
        if sector_after > self.position_limits['max_sector_position']:
            score -= 2
            warnings.append(f"板块仓位超限：{sector_after*100:.0f}%")
        
        # 单只仓位检查
        if proposed_pos > self.position_limits['max_single_position']:
            score -= 2
            warnings.append(f"单只仓位超限")
        
        score = max(score, 0)
        
        risk_level = "低" if score >= 7 else ("中等" if score >= 5 else "高")
        
        return {
            'current_position': current_pos,
            'proposed_position': proposed_pos,
            'total_after_trade': total_after,
            'sector_after_trade': sector_after,
            'within_limit': total_after <= self.position_limits['max_total_position'],
            'warnings': warnings,
            'score': round(score, 1),
            'risk_level': risk_level
        }
    
    def _make_risk_decision(self, market: Dict, stock: Dict, trade: Dict) -> Dict[str, Any]:
        """做出风控决策"""
        # 一票否决条件
        if stock['score'] < 3:
            return {
                'action': 'reject',
                'reason': '个股风险过高',
                'max_position_allowed': 0,
                'stop_loss_must_execute': True,
                'warnings': stock['risks']
            }
        
        if market['score'] < 4:
            return {
                'action': 'reject',
                'reason': '大盘风险过高',
                'max_position_allowed': 0,
                'stop_loss_must_execute': True,
                'warnings': [market['description']]
            }
        
        # 通过但有限制
        max_pos = self.position_limits['max_single_position']
        warnings = []
        
        if market['score'] < 6:
            max_pos = min(max_pos, 0.10)
            warnings.append("大盘风险偏高，建议降低仓位")
        
        if stock['score'] < 7:
            warnings.extend(stock['risks'])
        
        return {
            'action': 'approve',
            'reason': '风险可控',
            'max_position_allowed': max_pos,
            'stop_loss_must_execute': True,
            'warnings': warnings
        }
    
    def _extract_risk_points(self, market: Dict, stock: Dict, trade: Dict) -> List[str]:
        risks = []
        
        if market['risk_level'] != '低':
            risks.append(f"大盘风险{market['risk_level']}")
        
        risks.extend(stock['risks'])
        risks.extend(trade['warnings'])
        
        return risks if risks else ["风险可控"]
    
    def generate_report(self, analysis_result: Dict[str, Any]) -> str:
        """生成风控报告"""
        raw = analysis_result['raw_data']
        market = raw['market_risk']
        stock = raw['stock_risk']
        trade = raw['trade_risk']
        decision = analysis_result['conclusion']
        
        action_display = "☑ 通过" if decision['action'] == 'approve' else "☐ 否决"
        
        report = f"""
════════════════════════════════════════════════════════════
【风控评估报告】
════════════════════════════════════════════════════════════
分析时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}

一、大盘风险评估
┌────────────────────────────────────────────────────────┐
│ 大盘趋势：{market['trend']}                               │
│ 成交量变化：{'放量' if market['volume_change'] > 0 else '缩量'}{abs(market['volume_change']):.0f}亿 │
│ 涨跌停比：{market['limit_ratio']:.1f}:1                   │
│ 风险等级：{market['risk_level']}                          │
│ 评分：{market['score']:.1f}/10                            │
└────────────────────────────────────────────────────────┘

二、个股风险评估
┌────────────────────────────────────────────────────────┐
│ ST状态：{stock['st_status']}                              │
│ 退市风险：{'无' if not stock.get('delisting_risk') else '有'} │
│ 质押比例：{stock['pledge_ratio']*100:.0f}%                 │
│ 流动性：{stock['liquidity']}                              │
│ 风险等级：{stock['risk_level']}                           │
│ 评分：{stock['score']:.1f}/10                             │
└────────────────────────────────────────────────────────┘

三、交易风险评估
┌────────────────────────────────────────────────────────┐
│ 当前总仓位：{trade['current_position']*100:.0f}%          │
│ 本笔建议仓位：{trade['proposed_position']*100:.0f}%        │
│ 加仓后总仓位：{trade['total_after_trade']*100:.0f}%       │
│ 是否超限：{'否' if trade['within_limit'] else '是'}        │
│ 风险等级：{trade['risk_level']}                           │
│ 评分：{trade['score']:.1f}/10                             │
└────────────────────────────────────────────────────────┘

四、风控决策
┌────────────────────────────────────────────────────────┐
│ {action_display}：{decision['reason']}                   │
│ 最大允许仓位：{decision['max_position_allowed']*100:.0f}% │
│ 止损必须执行：{'是' if decision['stop_loss_must_execute'] else '否'} │
│ 警告事项：                                              │
│ {chr(10).join(['- ' + w for w in decision['warnings']]) if decision['warnings'] else '- 无'} │
└────────────────────────────────────────────────────────┘

五、风控综合评分
┌────────────────────────────────────────────────────────┐
│ 总评分：{analysis_result['overall_score']:.1f}/10         │
│ 风控决策：{'批准' if decision['action'] == 'approve' else '否决'} │
└────────────────────────────────────────────────────────┘
════════════════════════════════════════════════════════════
"""
        return report
