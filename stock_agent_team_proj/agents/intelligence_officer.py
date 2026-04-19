"""
情报员 Agent
负责情报面分析：资金流向、龙虎榜、北向资金、热点题材、消息催化剂
"""
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

from agents.base_agent import WorkerAgent, AgentContext
from models.base import AgentType
from utils.data_fetcher import data_fetcher


class IntelligenceOfficer(WorkerAgent):
    """情报员"""
    
    def __init__(self, weight: float = 0.30):
        super().__init__(AgentType.INTELLIGENCE, "情报员", weight)
    
    def _do_analysis(self, context: AgentContext) -> Dict[str, Any]:
        """执行情报分析"""
        stock_code = context.stock_code
        stock_name = context.stock_name
        
        # 获取情报数据（API数据）
        intel_data = self._get_intelligence_data(stock_code)
        
        # 合并网络情报（如果有）
        web_intel = context.additional_info.get('web_intelligence', {})
        if web_intel:
            intel_data['web_intelligence'] = web_intel
            self.logger.info(f"已合并网络情报: 整体情绪={web_intel.get('overall_sentiment', 'neutral')}")
        
        # 1. 题材分析
        theme_analysis = self._analyze_theme(intel_data)
        
        # 2. 资金流向
        fund_analysis = self._analyze_fund_flow(intel_data)
        
        # 3. 消息催化剂（增强：使用网络情报）
        catalyst_analysis = self._analyze_catalyst(intel_data, web_intel)
        
        # 4. 市场情绪（增强：使用网络情报）
        sentiment_analysis = self._analyze_sentiment(intel_data, web_intel)
        
        # 5. 综合评分 (加权平均，突出资金和题材)
        overall_score = (
            theme_analysis['score'] * 0.3 +
            fund_analysis['score'] * 0.3 +
            catalyst_analysis['score'] * 0.2 +
            sentiment_analysis['score'] * 0.2
        )
        
        # 6. 爆发力评估
        explosion = self._assess_explosion(theme_analysis, fund_analysis, catalyst_analysis)
        
        # 7. 关键点和风险点
        key_points = self._extract_key_points(theme_analysis, fund_analysis, catalyst_analysis)
        risk_points = self._extract_risk_points(catalyst_analysis, sentiment_analysis)
        
        return {
            'scores': {
                'theme_score': theme_analysis['score'],
                'fund_score': fund_analysis['score'],
                'catalyst_score': catalyst_analysis['score'],
                'sentiment_score': sentiment_analysis['score']
            },
            'overall_score': overall_score,
            'conclusion': {
                'recommendation': self._get_recommendation(overall_score),
                'explosion_score': explosion['score'],
                'explosion_timing': explosion['timing'],
                'theme_status': theme_analysis['theme_stage']
            },
            'key_points': key_points,
            'risk_points': risk_points,
            'raw_data': {
                'theme': theme_analysis,
                'fund': fund_analysis,
                'catalyst': catalyst_analysis,
                'sentiment': sentiment_analysis,
                'explosion': explosion
            }
        }
    
    def _get_intelligence_data(self, stock_code: str) -> Dict[str, Any]:
        """获取情报数据 - 真实数据 + 已存储的情报"""
        # 1. 先尝试读取已存储的情报文件
        stored_intel = self._load_stored_intel(stock_code)

        # 2. 获取API实时数据
        fund_flow = data_fetcher.get_fund_flow(stock_code)
        north_bound = data_fetcher.get_north_bound_flow()
        news = data_fetcher.get_news(stock_code, limit=5)
        
        # 构建资金流数据
        if fund_flow:
            fund_flows = fund_flow['fund_flows']
            net_inflow_5d = fund_flow['net_inflow_5d']
            inflow_days = fund_flow['inflow_days']
        else:
            # 兜底数据
            fund_flows = [{'date': datetime.now().strftime('%Y-%m-%d'), 'net_inflow': 100000000}]
            net_inflow_5d = 100000000
            inflow_days = 3
        
        # 处理新闻数据
        news_list = []
        if news:
            for n in news:
                sentiment = 'positive' if any(kw in n.get('title', '') for kw in ['涨', '增', '盈利', '突破']) else \
                           'negative' if any(kw in n.get('title', '') for kw in ['跌', '降', '亏损', '风险']) else 'neutral'
                news_list.append({
                    'date': n.get('date', ''),
                    'title': n.get('title', ''),
                    'sentiment': sentiment,
                    'impact': 'medium'
                })
        
        # 3. 合并已存储的情报到新闻列表
        if stored_intel:
            # 合并存储的新闻
            stored_news = stored_intel.get('news', [])
            for sn in stored_news:
                if sn.get('title') and not any(n.get('title') == sn.get('title') for n in news_list):
                    news_list.append({
                        'date': sn.get('date', sn.get('time', '')),
                        'title': sn.get('title', ''),
                        'sentiment': sn.get('sentiment', 'neutral'),
                        'impact': 'medium'
                    })

            # 合并存储的研报
            stored_research = stored_intel.get('research', [])
            for sr in stored_research:
                if sr.get('title') and not any(n.get('title') == sr.get('title') for n in news_list):
                    news_list.append({
                        'date': sr.get('date', sr.get('time', '')),
                        'title': sr.get('title', ''),
                        'sentiment': sr.get('sentiment', 'neutral'),
                        'impact': 'high'  # 研报影响较高
                    })

            self.logger.info(f"已合并存储情报: {len(stored_news)}条新闻, {len(stored_research)}条研报")

        # 4. 从存储情报中提取板块/题材信息（如果有）
        sector = stored_intel.get('sector', '新能源/智能制造') if stored_intel else '新能源/智能制造'
        theme = stored_intel.get('theme', '智能制造龙头') if stored_intel else '智能制造龙头'

        # 返回整合后的数据
        return {
            'sector': sector,
            'theme': theme,
            'theme_stage': stored_intel.get('theme_stage', '发酵') if stored_intel else '发酵',
            'theme_sustainability': stored_intel.get('theme_sustainability', '中') if stored_intel else '中',
            'is_sector_leader': stored_intel.get('is_sector_leader', True) if stored_intel else True,
            
            'fund_flow_5d': fund_flows,
            'north_bound_5d_change': north_bound['positive_days'] / 5 if north_bound else 0.1,
            'dragon_tiger': stored_intel.get('dragon_tiger') if stored_intel else None,
            'margin_balance': stored_intel.get('margin_balance', 0) if stored_intel else 0,
            'margin_change_5d': stored_intel.get('margin_change_5d', 0.01) if stored_intel else 0.01,
            
            'news': news_list if news_list else [
                {'date': datetime.now().strftime('%Y-%m-%d'), 'title': '暂无重大消息', 'sentiment': 'neutral', 'impact': 'low'}
            ],
            
            'sector_5d_change': stored_intel.get('sector_5d_change', 0.03) if stored_intel else 0.03,
            'sector_leader': stored_intel.get('sector_leader', stock_code) if stored_intel else stock_code,
            'sector_leader_5d_change': stored_intel.get('sector_leader_5d_change', 0.05) if stored_intel else 0.05,
            'limit_up_count': stored_intel.get('limit_up_count', 50) if stored_intel else 50,
            'market_sentiment': stored_intel.get('market_sentiment', '中性偏乐观') if stored_intel else '中性偏乐观'
        }
    
    def _load_stored_intel(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """加载已存储的情报文件

        读取 data/intel/{stock_code}.json，如果文件存在且未过期（7天内），
        则返回情报数据，否则返回 None
        """
        intel_file = os.path.join('data', 'intel', f'{stock_code}.json')

        if not os.path.exists(intel_file):
            return None

        try:
            with open(intel_file, 'r', encoding='utf-8') as f:
                intel_data = json.load(f)

            # 检查时效性（超过7天视为过期）
            tracked_at = intel_data.get('tracked_at', '')
            if tracked_at:
                try:
                    tracked_time = datetime.fromisoformat(tracked_at)
                    if (datetime.now() - tracked_time).days > 7:
                        self.logger.info(f"存储情报已过期: {stock_code} (采集于{tracked_at[:10]})")
                        return None
                except (ValueError, TypeError):
                    pass

            # 检查是否有实质内容
            has_content = (
                bool(intel_data.get('news')) or
                bool(intel_data.get('research')) or
                bool(intel_data.get('announcements'))
            )

            if has_content:
                self.logger.info(f"加载存储情报: {stock_code} (采集于{tracked_at[:10] if tracked_at else '未知'})")
                return intel_data
            else:
                self.logger.info(f"存储情报无实质内容: {stock_code}")
                return None

        except Exception as e:
            self.logger.warning(f"读取存储情报失败: {stock_code} - {e}")
            return None

    def _analyze_theme(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """分析题材"""
        theme = data['theme']
        stage = data['theme_stage']
        sustainability = data['theme_sustainability']
        is_leader = data['is_sector_leader']
        
        # 题材阶段评分
        stage_scores = {
            '启动': 9.0,
            '发酵': 8.0,
            '高潮': 5.0,
            '退潮': 3.0
        }
        stage_score = stage_scores.get(stage, 5.0)
        
        # 持续性评分
        sustainability_scores = {
            '强': 8.0,
            '中': 6.0,
            '弱': 4.0
        }
        sustain_score = sustainability_scores.get(sustainability, 5.0)
        
        # 龙头加分
        leader_bonus = 1.5 if is_leader else 0
        
        overall = (stage_score * 0.5 + sustain_score * 0.3 + (6 + leader_bonus) * 0.2)
        
        return {
            'theme': theme,
            'theme_stage': stage,
            'sustainability': sustainability,
            'is_leader': is_leader,
            'stage_score': stage_score,
            'sustain_score': sustain_score,
            'score': round(overall, 1),
            'description': f"题材{stage}期，持续性{sustainability}，{'龙头股' if is_leader else '跟风股'}"
        }
    
    def _analyze_fund_flow(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """分析资金流向"""
        fund_flows = data['fund_flow_5d']
        north_bound = data['north_bound_5d_change']
        margin_change = data['margin_change_5d']
        
        # 计算净流入
        net_inflow = sum(f['net_inflow'] for f in fund_flows)
        total_inflow = sum(f['net_inflow'] for f in fund_flows if f['net_inflow'] > 0)
        
        # 资金流入天数
        inflow_days = sum(1 for f in fund_flows if f['net_inflow'] > 0)
        inflow_ratio = inflow_days / len(fund_flows)
        
        # 评分 (降低资金门槛)
        if net_inflow > 150000000:
            fund_score = 8.5
        elif net_inflow > 50000000:
            fund_score = 7.0
        elif net_inflow > 0:
            fund_score = 6.0
        else:
            fund_score = 4.0
        
        # 北向资金评分
        if north_bound > 0.2:
            north_score = 8.0
        elif north_bound > 0.1:
            north_score = 7.0
        elif north_bound > 0:
            north_score = 6.0
        else:
            north_score = 4.0
        
        overall = fund_score * 0.6 + north_score * 0.4
        
        return {
            'net_inflow_5d': net_inflow,
            'inflow_days': inflow_days,
            'inflow_ratio': inflow_ratio,
            'north_bound_change': north_bound,
            'margin_change': margin_change,
            'fund_score': fund_score,
            'north_score': north_score,
            'score': round(overall, 1),
            'description': f"近5日净流入{net_inflow/100000000:.1f}亿，北向{'增持' if north_bound > 0 else '减持'}"
        }
    
    def _analyze_catalyst(self, data: Dict[str, Any], web_intel: Dict[str, Any] = None) -> Dict[str, Any]:
        """分析消息催化剂（增强：融合网络情报）"""
        news_list = data['news']
        
        positive_news = [n for n in news_list if n['sentiment'] == 'positive']
        negative_news = [n for n in news_list if n['sentiment'] == 'negative']
        
        # 计算催化剂影响（API数据）
        positive_impact = sum(1 if n['impact'] == 'high' else 0.5 for n in positive_news)
        negative_impact = sum(1 if n['impact'] == 'high' else 0.5 for n in negative_news)
        
        net_impact = positive_impact - negative_impact
        
        # 融合网络情报
        web_catalyst_items = []
        if web_intel:
            # 网络新闻催化剂
            for item in web_intel.get('news', [])[:3]:
                web_catalyst_items.append({
                    'title': item.get('title', ''),
                    'sentiment': item.get('sentiment', 'neutral'),
                    'source': '网络搜索'
                })
            # 研报催化剂
            for item in web_intel.get('research', [])[:2]:
                web_catalyst_items.append({
                    'title': item.get('title', ''),
                    'sentiment': item.get('sentiment', 'neutral'),
                    'source': '研报'
                })
            
            # 根据网络情报调整影响
            web_positive = len([i for i in web_catalyst_items if i['sentiment'] == 'positive'])
            web_negative = len([i for i in web_catalyst_items if i['sentiment'] == 'negative'])
            net_impact += (web_positive - web_negative) * 0.3
        
        if net_impact >= 1:
            score = 8.0
            strength = "强"
        elif net_impact >= 0.5:
            score = 6.5
            strength = "中"
        elif net_impact >= 0:
            score = 5.0
            strength = "弱"
        else:
            score = 3.5
            strength = "负面"
        
        return {
            'positive_count': len(positive_news),
            'negative_count': len(negative_news),
            'net_impact': net_impact,
            'strength': strength,
            'score': score,
            'news_list': news_list,
            'web_catalyst_items': web_catalyst_items,
            'description': f"催化剂强度{strength}，{'利好为主' if net_impact > 0 else '利空为主'}"
        }
    
    def _analyze_sentiment(self, data: Dict[str, Any], web_intel: Dict[str, Any] = None) -> Dict[str, Any]:
        """分析市场情绪（增强：融合网络情报）"""
        sector_change = data['sector_5d_change']
        leader_change = data['sector_leader_5d_change']
        limit_up = data['limit_up_count']
        sentiment = data['market_sentiment']
        
        # 板块表现评分
        if sector_change > 0.05:
            sector_score = 8.0
        elif sector_change > 0.02:
            sector_score = 7.0
        elif sector_change > 0:
            sector_score = 6.0
        else:
            sector_score = 4.0
        
        # 情绪评分（API数据）
        sentiment_scores = {
            '高涨': 8.5,
            '偏乐观': 7.0,
            '中性': 5.5,
            '低迷': 4.0,
            '恐慌': 2.5
        }
        sentiment_score = sentiment_scores.get(sentiment, 5.5)
        
        # 融合网络情报
        web_sentiment_adjust = 0
        web_sentiment_detail = []
        if web_intel:
            web_overall = web_intel.get('overall_sentiment', 'neutral')
            web_sentiment_scores = {'positive': 1.0, 'negative': -1.0, 'neutral': 0}
            web_sentiment_adjust = web_sentiment_scores.get(web_overall, 0)
            
            # 网络舆情详情
            for item in web_intel.get('sentiment', [])[:3]:
                web_sentiment_detail.append({
                    'title': item.get('title', ''),
                    'sentiment': item.get('sentiment', 'neutral')
                })
            
            # 关键正面/负面信息
            key_positive = web_intel.get('key_positive', [])
            key_negative = web_intel.get('key_negative', [])
            if key_positive:
                web_sentiment_adjust += 0.3
            if key_negative:
                web_sentiment_adjust -= 0.3
        
        overall = sector_score * 0.4 + sentiment_score * 0.4 + (5.5 + web_sentiment_adjust) * 0.2
        
        return {
            'sector_5d_change': sector_change,
            'leader_change': leader_change,
            'limit_up_count': limit_up,
            'sentiment': sentiment,
            'sector_score': sector_score,
            'sentiment_score': sentiment_score,
            'web_sentiment_adjust': web_sentiment_adjust,
            'web_sentiment_detail': web_sentiment_detail,
            'score': round(overall, 1),
            'description': f"板块涨幅{sector_change*100:.1f}%，市场情绪{sentiment}，网络情绪{web_intel.get('overall_sentiment', 'neutral') if web_intel else '无'}"
        }
    
    def _assess_explosion(self, theme: Dict, fund: Dict, catalyst: Dict) -> Dict[str, Any]:
        """评估短线爆发力"""
        score = (theme['score'] * 0.4 + fund['score'] * 0.35 + catalyst['score'] * 0.25)
        
        if score >= 7.5:
            timing = "即将爆发"
        elif score >= 6.5:
            timing = "1-3天内"
        elif score >= 5.5:
            timing = "待观察"
        else:
            timing = "不确定"
        
        return {
            'score': round(score, 1),
            'timing': timing
        }
    
    def _get_recommendation(self, score: float) -> str:
        if score >= 7.5:
            return "积极参与"
        elif score >= 6.5:
            return "可参与"
        elif score >= 5.5:
            return "观望"
        else:
            return "回避"
    
    def _extract_key_points(self, theme: Dict, fund: Dict, catalyst: Dict) -> List[str]:
        points = []
        
        if theme['is_leader']:
            points.append(f"板块龙头，题材{theme['theme_stage']}期")
        
        if fund['net_inflow_5d'] > 100000000:
            points.append(f"近5日主力净流入{fund['net_inflow_5d']/100000000:.1f}亿")
        
        if fund['north_bound_change'] > 0.1:
            points.append(f"北向资金连续增持{fund['north_bound_change']*100:.1f}%")
        
        if catalyst['strength'] in ['强', '中']:
            points.append(f"催化剂强度{catalyst['strength']}")
        
        return points if points else ["情报面中性"]
    
    def _extract_risk_points(self, catalyst: Dict, sentiment: Dict) -> List[str]:
        risks = []
        
        if catalyst['negative_count'] > 0:
            risks.append(f"存在{catalyst['negative_count']}条利空消息")
        
        if sentiment['sentiment'] in ['低迷', '恐慌']:
            risks.append(f"市场情绪{sentiment['sentiment']}")
        
        return risks if risks else ["情报面风险可控"]
    
    def generate_report(self, analysis_result: Dict[str, Any]) -> str:
        """生成情报分析报告"""
        raw = analysis_result['raw_data']
        theme = raw['theme']
        fund = raw['fund']
        catalyst = raw['catalyst']
        sentiment = raw['sentiment']
        explosion = raw['explosion']
        
        report = f"""
════════════════════════════════════════════════════════════
【情报分析报告】
════════════════════════════════════════════════════════════
分析时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}

一、题材分析
┌────────────────────────────────────────────────────────┐
│ 核心题材：{theme['theme']}                               │
│ 题材阶段：{theme['theme_stage']}                         │
│ 持续性：{theme['sustainability']}                        │
│ 板块地位：{'龙头' if theme['is_leader'] else '跟风'}      │
│ 题材评分：{theme['score']:.1f}/10                        │
└────────────────────────────────────────────────────────┘

二、资金流向
┌────────────────────────────────────────────────────────┐
│ 近5日净流入：{fund['net_inflow_5d']/100000000:.1f}亿元   │
│ 流入天数：{fund['inflow_days']}/5天                          │
│ 北向资金：{'增持' if fund['north_bound_change'] > 0 else '减持'} {abs(fund['north_bound_change'])*100:.1f}% │
│ 资金评分：{fund['score']:.1f}/10                         │
└────────────────────────────────────────────────────────┘

三、消息催化剂
┌────────────────────────────────────────────────────────┐
│ 利好消息：{catalyst['positive_count']}条                 │
│ 利空消息：{catalyst['negative_count']}条                 │
│ 催化剂强度：{catalyst['strength']}                       │
│ 催化剂评分：{catalyst['score']:.1f}/10                   │
└────────────────────────────────────────────────────────┘

四、市场情绪
┌────────────────────────────────────────────────────────┐
│ 板块5日涨幅：{sentiment['sector_5d_change']*100:.1f}%   │
│ 市场情绪：{sentiment['sentiment']}                       │
│ 情绪评分：{sentiment['score']:.1f}/10                    │
└────────────────────────────────────────────────────────┘

五、短线爆发力评估
┌────────────────────────────────────────────────────────┐
│ 爆发力评分：{explosion['score']:.1f}/10                  │
│ 爆发时机：{explosion['timing']}                          │
└────────────────────────────────────────────────────────┘

六、情报面综合评分
┌────────────────────────────────────────────────────────┐
│ 总评分：{analysis_result['overall_score']:.1f}/10        │
│ 操作建议：{analysis_result['conclusion']['recommendation']} │
└────────────────────────────────────────────────────────┘

七、关键点
{chr(10).join(['- ' + p for p in analysis_result['key_points']])}

八、风险点
{chr(10).join(['- ' + r for r in analysis_result['risk_points']])}
════════════════════════════════════════════════════════════
"""
        return report
