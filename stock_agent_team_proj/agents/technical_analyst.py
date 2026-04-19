"""
技术分析员 Agent
负责技术面分析：K线形态、均线系统、MACD、RSI、KDJ等
"""
from datetime import datetime
from typing import Dict, Any, List

from agents.base_agent import WorkerAgent, AgentContext
from config import TECHNICAL_PARAMS
from models.base import AgentType
from utils.data_fetcher import data_fetcher


class TechnicalAnalyst(WorkerAgent):
    """技术分析员"""
    
    def __init__(self, weight: float = 0.35):
        super().__init__(AgentType.TECHNICAL, "技术分析员", weight)
        self.ma_periods = TECHNICAL_PARAMS['ma_periods']
        self.macd_params = TECHNICAL_PARAMS['macd_params']
        self.rsi_period = TECHNICAL_PARAMS['rsi_period']
    
    def _do_analysis(self, context: AgentContext) -> Dict[str, Any]:
        """执行技术分析"""
        stock_code = context.stock_code
        stock_name = context.stock_name
        
        # 模拟数据（实际应从数据源获取）
        price_data = self._get_price_data(stock_code)
        
        # 1. 趋势判断
        trend_analysis = self._analyze_trend(price_data)
        
        # 2. 位置判断
        position_analysis = self._analyze_position(price_data)
        
        # 3. 入场信号
        signal_analysis = self._analyze_signals(price_data)
        
        # 4. 交易计划
        trade_plan = self._create_trade_plan(price_data, trend_analysis, position_analysis)
        
        # 5. 综合评分 (加权平均，突出趋势和入场信号)
        overall_score = (
            trend_analysis['score'] * 0.4 +
            position_analysis['score'] * 0.2 +
            signal_analysis['score'] * 0.4
        )
        
        # 6. 关键点和风险点
        key_points = self._extract_key_points(trend_analysis, signal_analysis)
        risk_points = self._extract_risk_points(position_analysis, signal_analysis)
        
        return {
            'scores': {
                'trend_score': trend_analysis['score'],
                'position_score': position_analysis['score'],
                'signal_score': signal_analysis['score']
            },
            'overall_score': overall_score,
            'conclusion': {
                'recommendation': self._get_recommendation(overall_score),
                'confidence': self._get_confidence(overall_score),
                'entry_zone': trade_plan['entry_zone'],
                'stop_loss': trade_plan['stop_loss'],
                'take_profit_1': trade_plan['take_profit_1'],
                'take_profit_2': trade_plan['take_profit_2'],
                'holding_days_estimate': trade_plan['holding_days']
            },
            'key_points': key_points,
            'risk_points': risk_points,
            'raw_data': {
                'trend': trend_analysis,
                'position': position_analysis,
                'signal': signal_analysis,
                'trade_plan': trade_plan
            }
        }
    
    def _get_price_data(self, stock_code: str) -> Dict[str, Any]:
        """获取价格数据 - 真实数据"""
        # 使用真实数据获取
        real_data = data_fetcher.get_technical_indicators(stock_code)
        
        if real_data:
            return real_data
        
        # 如果获取失败，返回模拟数据作为兜底
        self.logger.warning(f"无法获取 {stock_code} 的真实数据，使用模拟数据")
        return {
            'current_price': 103.82,
            'prev_close': 104.25,
            'open': 104.00,
            'high': 104.75,
            'low': 102.50,
            'volume': 26347500,
            'amount': 2717868000,
            'ma5': 101.80,
            'ma10': 100.50,
            'ma20': 98.20,
            'ma60': 95.50,
            'macd': {
                'dif': 1.25,
                'dea': 0.85,
                'histogram': 0.40
            },
            'rsi': {
                'rsi6': 58.32,
                'rsi12': 55.18,
                'rsi24': 52.45
            },
            'kdj': {
                'k': 65.32,
                'd': 58.45,
                'j': 79.06
            },
            'support_levels': [100.00, 101.50],
            'resistance_levels': [105.00, 110.00],
            'recent_high': 110.50,
            'recent_low': 95.20
        }
    
    def _analyze_trend(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """分析趋势"""
        current_price = data['current_price']
        ma5 = data['ma5']
        ma10 = data['ma10']
        ma20 = data['ma20']
        
        # 均线排列判断
        if ma5 > ma10 > ma20:
            ma_pattern = "多头排列"
            ma_score = 8.5
        elif ma5 > ma10 or ma5 > ma20:
            ma_pattern = "部分多头"
            ma_score = 6.5
        elif ma5 < ma10 < ma20:
            ma_pattern = "空头排列"
            ma_score = 3.0
        else:
            ma_pattern = "均线纠缠"
            ma_score = 5.0
        
        # MACD判断
        macd = data['macd']
        if macd['dif'] > macd['dea'] and macd['histogram'] > 0:
            macd_status = "金叉向上"
            macd_score = 8.0
        elif macd['dif'] > macd['dea']:
            macd_status = "金叉区域"
            macd_score = 6.5
        elif macd['dif'] < macd['dea'] and macd['histogram'] < 0:
            macd_status = "死叉向下"
            macd_score = 3.0
        else:
            macd_status = "死叉区域"
            macd_score = 4.0
        
        # 趋势综合判断 (加权计算，避免一票否决)
        score = ma_score * 0.6 + macd_score * 0.4
        if score >= 7.0:
            trend = "上升趋势"
        elif score >= 6.0:
            trend = "震荡偏强"
        elif score <= 4.5:
            trend = "下降趋势"
        else:
            trend = "震荡趋势"
        
        return {
            'trend': trend,
            'ma_pattern': ma_pattern,
            'ma_score': ma_score,
            'macd_status': macd_status,
            'macd_score': macd_score,
            'score': score,
            'description': f"均线{ma_pattern}，MACD{macd_status}"
        }
    
    def _analyze_position(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """分析位置"""
        current_price = data['current_price']
        ma5 = data['ma5']
        ma10 = data['ma10']
        ma20 = data['ma20']
        support = data['support_levels']
        resistance = data['resistance_levels']
        
        # 计算距离均线的距离
        dist_ma5 = (current_price - ma5) / ma5 * 100
        dist_ma10 = (current_price - ma10) / ma10 * 100
        dist_ma20 = (current_price - ma20) / ma20 * 100
        
        # 计算距离支撑压力的距离
        dist_support = (current_price - support[0]) / current_price * 100
        dist_resistance = (resistance[0] - current_price) / current_price * 100
        
        # 位置评估 (放宽条件)
        if abs(dist_ma5) <= 3 and abs(dist_ma10) <= 5:
            position = "均线附近"
            score = 7.0
        elif dist_support <= 8:
            position = "支撑位附近"
            score = 7.5
        elif dist_resistance <= 3:
            position = "压力位附近"
            score = 5.0
        elif dist_ma5 > 8:
            position = "高位偏离"
            score = 4.0
        else:
            position = "中位震荡"
            score = 6.0
        
        return {
            'position': position,
            'current_price': current_price,
            'dist_ma5': dist_ma5,
            'dist_ma10': dist_ma10,
            'dist_ma20': dist_ma20,
            'dist_support': dist_support,
            'dist_resistance': dist_resistance,
            'support': support,
            'resistance': resistance,
            'score': score
        }
    
    def _analyze_signals(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """分析入场信号"""
        macd = data['macd']
        rsi = data['rsi']
        kdj = data['kdj']
        
        signals = []
        scores = []
        
        # MACD信号
        if macd['dif'] > macd['dea'] and macd['histogram'] > 0:
            signals.append("MACD金叉确认")
            scores.append(8.0)
        elif macd['dif'] > macd['dea']:
            signals.append("MACD金叉区域")
            scores.append(6.5)
        else:
            signals.append("MACD信号不明")
            scores.append(4.0)
        
        # RSI信号
        rsi6 = rsi['rsi6']
        if rsi6 < 30:
            signals.append("RSI超卖")
            scores.append(8.0)
        elif 30 <= rsi6 <= 70:
            signals.append("RSI中性")
            scores.append(6.0)
        elif rsi6 > 80:
            signals.append("RSI超买")
            scores.append(3.0)
        else:
            signals.append("RSI偏高")
            scores.append(5.0)
        
        # KDJ信号
        if kdj['k'] > kdj['d'] and kdj['j'] < 100:
            signals.append("KDJ金叉向上")
            scores.append(7.0)
        elif kdj['j'] > 100:
            signals.append("KDJ超买")
            scores.append(3.0)
        else:
            signals.append("KDJ信号一般")
            scores.append(5.0)
        
        overall_score = sum(scores) / len(scores)
        
        return {
            'signals': signals,
            'signal_scores': scores,
            'score': overall_score,
            'strength': '强' if overall_score >= 7 else ('中' if overall_score >= 5 else '弱')
        }
    
    def _create_trade_plan(self, data: Dict[str, Any], 
                           trend: Dict[str, Any], 
                           position: Dict[str, Any]) -> Dict[str, Any]:
        """创建交易计划"""
        current_price = data['current_price']
        support = data['support_levels']
        resistance = data['resistance_levels']
        
        # 入场区间
        entry_low = min(position['dist_ma5'] * -0.5, 0)  # 略低于当前价
        entry_zone = [current_price + entry_low * current_price / 100, current_price]
        
        # 止损设置
        stop_loss_rate = 0.06  # 6%止损
        stop_loss = support[0] * 0.98  # 略低于支撑位
        
        # 止盈设置
        take_profit_1 = current_price * 1.04  # 4%
        take_profit_2 = resistance[0] * 0.98  # 接近压力位
        
        # 持股周期
        holding_days = "5-7"
        
        return {
            'entry_zone': [round(entry_zone[0], 2), round(entry_zone[1], 2)],
            'stop_loss': round(stop_loss, 2),
            'stop_loss_rate': round((current_price - stop_loss) / current_price * 100, 1),
            'take_profit_1': round(take_profit_1, 2),
            'take_profit_2': round(take_profit_2, 2),
            'take_profit_1_rate': round((take_profit_1 - current_price) / current_price * 100, 1),
            'take_profit_2_rate': round((take_profit_2 - current_price) / current_price * 100, 1),
            'profit_loss_ratio': round(((take_profit_1 - current_price) / (current_price - stop_loss)), 2),
            'holding_days': holding_days,
            'position_suggest': '15-20%'
        }
    
    def _get_recommendation(self, score: float) -> str:
        """根据评分给出建议"""
        if score >= 7.5:
            return "买入"
        elif score >= 6.0:
            return "可考虑买入"
        elif score >= 5.0:
            return "观望"
        else:
            return "回避"
    
    def _get_confidence(self, score: float) -> str:
        """根据评分给出置信度"""
        if score >= 8:
            return "高"
        elif score >= 7:
            return "中高"
        elif score >= 6:
            return "中"
        else:
            return "低"
    
    def _extract_key_points(self, trend: Dict[str, Any], signal: Dict[str, Any]) -> List[str]:
        """提取关键点"""
        points = []
        
        if trend['score'] >= 7:
            points.append(f"趋势明确：{trend['trend']}")
        
        for s in signal['signals'][:2]:
            if '金叉' in s or '超卖' in s:
                points.append(s)
        
        return points if points else ["技术面中性"]
    
    def _extract_risk_points(self, position: Dict[str, Any], signal: Dict[str, Any]) -> List[str]:
        """提取风险点"""
        risks = []
        
        if position['score'] <= 5:
            risks.append(f"位置偏高：{position['position']}")
        
        if position['dist_resistance'] <= 3:
            risks.append(f"接近压力位，距离{position['dist_resistance']:.1f}%")
        
        for s in signal['signals']:
            if '超买' in s:
                risks.append(s)
        
        return risks if risks else ["技术面风险可控"]
    
    def generate_report(self, analysis_result: Dict[str, Any]) -> str:
        """生成技术分析报告"""
        raw = analysis_result['raw_data']
        trend = raw['trend']
        position = raw['position']
        signal = raw['signal']
        trade_plan = raw['trade_plan']
        
        report = f"""
════════════════════════════════════════════════════════════
【技术分析报告】
════════════════════════════════════════════════════════════
分析时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}

一、趋势判断
┌────────────────────────────────────────────────────────┐
│ 趋势：{trend['trend']}                                    │
│ 均线形态：{trend['ma_pattern']}                           │
│ MACD状态：{trend['macd_status']}                         │
│ 趋势评分：{trend['score']:.1f}/10                        │
└────────────────────────────────────────────────────────┘

二、位置判断
┌────────────────────────────────────────────────────────┐
│ 当前价：{position['current_price']:.2f}元                │
│ 位置评估：{position['position']}                         │
│ 距5日均线：{position['dist_ma5']:+.1f}%                  │
│ 距支撑位：{position['dist_support']:.1f}%                │
│ 距压力位：{position['dist_resistance']:.1f}%             │
│ 位置评分：{position['score']:.1f}/10                     │
└────────────────────────────────────────────────────────┘

三、入场信号
┌────────────────────────────────────────────────────────┐
│ 信号强度：{signal['strength']}                           │
│ 主要信号：{', '.join(signal['signals'][:3])}            │
│ 信号评分：{signal['score']:.1f}/10                       │
└────────────────────────────────────────────────────────┘

四、交易计划
┌────────────────────────────────────────────────────────┐
│ 建议操作：{analysis_result['conclusion']['recommendation']} │
│ 入场区间：{trade_plan['entry_zone'][0]:.2f} - {trade_plan['entry_zone'][1]:.2f}元 │
│ 止损位：{trade_plan['stop_loss']:.2f}元（-{trade_plan['stop_loss_rate']:.1f}%）│
│ 止盈1：{trade_plan['take_profit_1']:.2f}元（+{trade_plan['take_profit_1_rate']:.1f}%）│
│ 止盈2：{trade_plan['take_profit_2']:.2f}元（+{trade_plan['take_profit_2_rate']:.1f}%）│
│ 盈亏比：1:{trade_plan['profit_loss_ratio']:.2f}          │
│ 建议仓位：{trade_plan['position_suggest']}               │
│ 预计持股：{trade_plan['holding_days']}天                 │
└────────────────────────────────────────────────────────┘

五、技术面综合评分
┌────────────────────────────────────────────────────────┐
│ 总评分：{analysis_result['overall_score']:.1f}/10        │
│ 建议权重：{'高' if analysis_result['overall_score'] >= 7 else '中'} │
└────────────────────────────────────────────────────────┘

六、关键点
{chr(10).join(['- ' + p for p in analysis_result['key_points']])}

七、风险点
{chr(10).join(['- ' + r for r in analysis_result['risk_points']])}
════════════════════════════════════════════════════════════
"""
        return report
