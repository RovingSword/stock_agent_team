"""
Leader Agent
决策中枢，汇总各方分析，输出最终交易决策
"""
from datetime import datetime
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.base_agent import LeaderAgent, AgentContext
from agents.technical_analyst import TechnicalAnalyst
from agents.intelligence_officer import IntelligenceOfficer
from agents.risk_controller import RiskController
from agents.fundamental_analyst import FundamentalAnalyst
from models.base import AgentType
from protocols.message_protocol import TradeDecisionMessage, AnalysisReportMessage
from storage.database import db
from config import SCORE_THRESHOLDS


class Leader(LeaderAgent):
    """决策中枢"""
    
    def __init__(self):
        super().__init__()
        
        # 初始化各Worker Agent
        self.technical_analyst = TechnicalAnalyst()
        self.intelligence_officer = IntelligenceOfficer()
        self.risk_controller = RiskController()
        self.fundamental_analyst = FundamentalAnalyst()
        
        self.workers = [
            self.technical_analyst,
            self.intelligence_officer,
            self.risk_controller,
            self.fundamental_analyst
        ]
    
    def _do_analysis(self, context: AgentContext) -> Dict[str, Any]:
        """Leader自身不执行分析，而是协调Worker"""
        return {}
    
    def analyze(self, context: AgentContext) -> TradeDecisionMessage:
        """
        执行完整分析流程
        
        Args:
            context: 分析上下文
        
        Returns:
            交易决策消息
        """
        self.logger.info(f"开始分析 {context.stock_name}({context.stock_code})")
        
        # 并行执行各Worker分析
        reports = self._run_workers_parallel(context)
        
        # 汇总报告
        self.collect_reports(reports)
        
        # 计算综合评分
        composite_score = self.calculate_composite_score()
        
        # 检查风控否决
        risk_report = self.worker_reports.get('risk')
        if risk_report:
            risk_conclusion = risk_report.conclusion
            if risk_conclusion.get('action') == 'reject':
                self.logger.warning(f"风控否决：{risk_conclusion.get('reason')}")
                return self._create_reject_decision(context, composite_score)
        
        # 做出决策
        decision = self.make_decision(context, reports)
        
        # 保存决策
        self._save_decision(context, decision, reports)
        
        self.logger.info(
            f"分析完成 - 决策: {decision.final_action}, "
            f"评分: {decision.composite_score:.2f}"
        )
        
        return decision
    
    def _run_workers_parallel(self, context: AgentContext) -> List[AnalysisReportMessage]:
        """并行执行Worker分析 - 改进版：失败时创建fallback报告，保证决策完整性"""
        reports = []
        failed_workers = []
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            # 提交任务
            futures = {
                executor.submit(worker.execute, context): worker
                for worker in self.workers
            }
            
            # 收集结果
            for future in as_completed(futures):
                worker = futures[future]
                try:
                    report = future.result(timeout=60)
                    reports.append(report)
                    self.logger.info(f"{worker.name} 分析完成，评分: {report.overall_score:.1f}")
                except Exception as e:
                    self.logger.error(f"{worker.name} 分析失败: {str(e)}")
                    failed_workers.append(worker.name)
                    # 创建完整的fallback低分报告，保证决策完整性
                    header = MessageHeader()
                    header.sender = {
                        'agent_id': f"fallback_{worker.name.lower()}",
                        'agent_name': worker.name
                    }
                    fallback_report = AnalysisReportMessage(
                        header=header,
                        task_id=context.task_id if hasattr(context, 'task_id') else "fallback",
                        stock_code=context.stock_code,
                        stock_name=context.stock_name,
                        agent_type=worker.name.lower().replace("分析员", "").replace(" ", "_").strip(),
                        weight=0.25,
                        overall_score=2.0,  # 失败视为低分
                        conclusion={
                            "summary": f"分析失败: {str(e)[:80]}...",
                            "action": "avoid",
                            "reason": "Worker执行异常，系统自动使用降级分数"
                        },
                        key_points=["分析执行失败", "已应用默认低分处理"],
                        risk_points=["潜在数据/网络问题"],
                        raw_data={"error": str(e)}
                    )
                    reports.append(fallback_report)
        
        if failed_workers:
            self.logger.warning(f"有 {len(failed_workers)} 个Worker失败: {failed_workers}。决策将包含降级处理。")
        
        return reports
    
    def make_decision(self, context: AgentContext, 
                       reports: List[AnalysisReportMessage]) -> TradeDecisionMessage:
        """做出交易决策"""
        # 计算综合评分
        composite_score = self.calculate_composite_score()
        
        # 确定交易动作
        action = self._determine_action(composite_score)
        
        # 构建执行方案
        execution = self._build_execution(reports)
        
        # 构建理由
        rationale = self._build_rationale(reports)
        
        # 创建决策消息
        from protocols.message_protocol import MessageHeader
        header = MessageHeader()
        header.sender = {
            'agent_id': self.agent_id,
            'agent_name': self.name
        }
        
        confidence = 'high' if composite_score >= 8 else ('medium' if composite_score >= 7 else 'low')
        
        decision = TradeDecisionMessage(
            header=header,
            stock_code=context.stock_code,
            stock_name=context.stock_name,
            final_action=action,
            confidence=confidence,
            composite_score=composite_score,
            score_breakdown=self._build_score_breakdown(),
            execution=execution,
            rationale=rationale,
            follow_up=self._build_follow_up(reports)
        )
        
        return decision
    
    def _determine_action(self, score: float) -> str:
        """根据评分确定交易动作"""
        if score >= SCORE_THRESHOLDS['strong_buy']:
            return 'strong_buy'
        elif score >= SCORE_THRESHOLDS['buy']:
            return 'buy'
        elif score >= SCORE_THRESHOLDS['watch']:
            return 'watch'
        else:
            return 'avoid'
    
    def _create_reject_decision(self, context: AgentContext, score: float) -> TradeDecisionMessage:
        """创建风控否决决策"""
        from protocols.message_protocol import MessageHeader
        header = MessageHeader()
        
        risk_report = self.worker_reports.get('risk')
        reject_reason = risk_report.conclusion.get('reason', '风险过高') if risk_report else '未知风险'
        
        return TradeDecisionMessage(
            header=header,
            stock_code=context.stock_code,
            stock_name=context.stock_name,
            final_action='risk_reject',
            confidence='high',
            composite_score=score,
            rationale={
                'buy_reasons': [],
                'risk_warnings': [f'风控否决：{reject_reason}']
            }
        )
    
    def _save_decision(self, context: AgentContext, 
                        decision: TradeDecisionMessage,
                        reports: List[AnalysisReportMessage]):
        """保存决策到数据库"""
        # 保存决策报告
        report_text = self.generate_decision_report(decision, reports)
        
        db.save_report({
            'stock_code': context.stock_code,
            'stock_name': context.stock_name,
            'agent_type': 'leader',
            'report_type': 'decision',
            'content': {
                'decision': decision.to_dict(),
                'text': report_text
            }
        })
        
        # 如果是买入决策，创建交易记录
        if decision.is_buy:
            trade_id = db.create_trade({
                'stock_code': context.stock_code,
                'stock_name': context.stock_name,
                'buy_date': datetime.now().strftime('%Y-%m-%d'),
                'buy_price': decision.execution.get('entry_zone', [0, 0])[0] if decision.entry_zone else 0,
                'buy_position': decision.position_size,
                'buy_reason': ', '.join(decision.rationale.get('buy_reasons', [])),
                'buy_score': decision.composite_score
            })
            
            # 保存各角色评分
            db.save_agent_scores({
                'trade_id': trade_id,
                'technical_score': self.worker_reports.get('technical').overall_score if 'technical' in self.worker_reports else 0,
                'technical_weight': self.technical_analyst.weight,
                'intelligence_score': self.worker_reports.get('intelligence').overall_score if 'intelligence' in self.worker_reports else 0,
                'intelligence_weight': self.intelligence_officer.weight,
                'risk_score': self.worker_reports.get('risk').overall_score if 'risk' in self.worker_reports else 0,
                'risk_weight': self.risk_controller.weight,
                'fundamental_score': self.worker_reports.get('fundamental').overall_score if 'fundamental' in self.worker_reports else 0,
                'fundamental_weight': self.fundamental_analyst.weight,
                'composite_score': decision.composite_score
            })
    
    def generate_report(self, analysis_result: Dict[str, Any]) -> str:
        """Leader使用generate_decision_report生成报告"""
        return ""
    
    def generate_decision_report(self, decision: TradeDecisionMessage, 
                                   reports: List[AnalysisReportMessage]) -> str:
        """生成决策报告"""
        action_display = {
            'strong_buy': '强烈买入',
            'buy': '建议买入',
            'watch': '观望',
            'avoid': '回避',
            'risk_reject': '风控否决'
        }
        
        score_table = self._format_score_table()
        execution = decision.execution
        rationale = decision.rationale
        
        report = f"""
══════════════════════════════════════════════════════════════════════════════
                      【交易决策指令】
══════════════════════════════════════════════════════════════════════════════
股票名称：{decision.stock_name}
股票代码：{decision.stock_code}
决策时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}

【综合评分】
{score_table}

【决策结论】
{action_display.get(decision.final_action, decision.final_action)}
置信度：{decision.confidence}

【交易执行方案】
┌──────────────────────────────────────────────────────────────────────────┐
│ 操作方向：{decision.final_action if decision.final_action != 'risk_reject' else '不执行'}{'                                      '}
│ 入场区间：{execution.get('entry_zone', ['-', '-'])[0]} - {execution.get('entry_zone', ['-', '-'])[1]}元
│ 止损位：{execution.get('stop_loss', 0):.2f}元
│ 止盈目标1：{execution.get('take_profit_1', 0):.2f}元
│ 止盈目标2：{execution.get('take_profit_2', 0):.2f}元
│ 建议仓位：{execution.get('position_size', 0)*100:.0f}%
│ 预计持股周期：{execution.get('holding_period_estimate', '-')}
└──────────────────────────────────────────────────────────────────────────┘

【核心逻辑】
买入理由：
{chr(10).join(['- ' + r for r in rationale.get('buy_reasons', ['无'])])}

风险点：
{chr(10).join(['- ' + r for r in rationale.get('risk_warnings', ['无'])])}

【后续跟踪】
{chr(10).join(['- ' + s for s in decision.follow_up.get('monitor_signals', [])])}

══════════════════════════════════════════════════════════════════════════════
                       风险提示：股市有风险，投资需谨慎
                  本分析仅供参考，不构成投资建议
══════════════════════════════════════════════════════════════════════════════
"""
        return report
    
    def _format_score_table(self) -> str:
        """格式化评分表格"""
        breakdown = self._build_score_breakdown()
        
        table = """┌────────────┬────────┬────────┬────────┐
│   分析维度  │  评分  │  权重  │  加权  │
├────────────┼────────┼────────┼────────┤"""
        
        total_weighted = 0
        for agent_type, data in breakdown.items():
            table += f"""
│ {agent_type.ljust(10)} │ {data['score']:.1f}/10 │ {data['weight']*100:.0f}%    │ {data['weighted']:.2f}   │"""
            total_weighted += data['weighted']
        
        table += f"""
├────────────┼────────┼────────┼────────┤
│ 综合       │ {total_weighted:.1f}/10 │ 100%   │ {total_weighted:.2f}   │
└────────────┴────────┴────────┴────────┘"""
        
        return table
