"""
Agent基类
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List
import json

from models.base import AgentType
from protocols.message_protocol import (
    MessageHeader, AnalysisReportMessage, RiskAssessmentMessage,
    TradeDecisionMessage, TaskDispatchMessage
)
from storage.database import db
from utils.logger import get_logger


@dataclass
class AgentContext:
    """Agent上下文"""
    task_id: str
    stock_code: str
    stock_name: str
    user_request: str = ""
    additional_info: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.additional_info is None:
            self.additional_info = {}


class BaseAgent(ABC):
    """Agent基类"""
    
    def __init__(self, agent_type: AgentType, name: str, weight: float = 0.0):
        self.agent_type = agent_type
        self.name = name
        self.weight = weight
        self.logger = get_logger(f"agent.{agent_type.value}")
    
    @property
    def agent_id(self) -> str:
        return f"{self.agent_type.value}_{id(self)}"
    
    @abstractmethod
    def analyze(self, context: AgentContext) -> Dict[str, Any]:
        """
        执行分析
        
        Args:
            context: Agent上下文，包含股票信息、用户请求等
        
        Returns:
            分析结果字典，包含评分、结论、关键点等
        """
        pass
    
    @abstractmethod
    def generate_report(self, analysis_result: Dict[str, Any]) -> str:
        """
        生成分析报告
        
        Args:
            analysis_result: 分析结果
        
        Returns:
            格式化的报告文本
        """
        pass
    
    def execute(self, context: AgentContext) -> AnalysisReportMessage:
        """
        执行完整分析流程
        
        Args:
            context: Agent上下文
        
        Returns:
            分析报告消息
        """
        self.logger.info(f"开始分析 {context.stock_name}({context.stock_code})")
        
        try:
            # 执行分析
            analysis_result = self.analyze(context)
            
            # 生成报告
            report_text = self.generate_report(analysis_result)
            
            # 构建消息
            header = MessageHeader()
            header.sender = {
                'agent_id': self.agent_id,
                'agent_name': self.name
            }
            
            message = AnalysisReportMessage(
                header=header,
                task_id=context.task_id,
                stock_code=context.stock_code,
                stock_name=context.stock_name,
                agent_type=self.agent_type.value,
                weight=self.weight,
                scores=analysis_result.get('scores', {}),
                overall_score=analysis_result.get('overall_score', 0),
                conclusion=analysis_result.get('conclusion', {}),
                key_points=analysis_result.get('key_points', []),
                risk_points=analysis_result.get('risk_points', []),
                raw_data=analysis_result.get('raw_data', {})
            )
            
            # 保存报告
            self._save_report(context, report_text, analysis_result)
            
            self.logger.info(f"分析完成，评分: {message.overall_score:.1f}")
            
            return message
            
        except Exception as e:
            self.logger.error(f"分析失败: {str(e)}")
            raise
    
    def _save_report(self, context: AgentContext, report_text: str, analysis_result: Dict[str, Any]):
        """保存报告到数据库"""
        db.save_report({
            'trade_id': context.task_id,
            'stock_code': context.stock_code,
            'stock_name': context.stock_name,
            'agent_type': self.agent_type.value,
            'report_type': 'analysis',
            'content': {
                'text': report_text,
                'result': analysis_result
            }
        })
    
    def get_current_weights(self) -> Dict[str, float]:
        """获取当前权重配置"""
        return db.get_current_weights()
    
    def log_analysis(self, context: AgentContext, result: Dict[str, Any]):
        """记录分析日志"""
        self.logger.info(
            f"[{self.name}] {context.stock_name}({context.stock_code}) "
            f"评分: {result.get('overall_score', 0):.1f}"
        )


class WorkerAgent(BaseAgent):
    """Worker Agent基类（技术分析员、情报员、基本面分析师、风控官）"""
    
    def __init__(self, agent_type: AgentType, name: str, weight: float):
        super().__init__(agent_type, name, weight)
    
    def analyze(self, context: AgentContext) -> Dict[str, Any]:
        """由子类实现具体分析逻辑"""
        return self._do_analysis(context)
    
    @abstractmethod
    def _do_analysis(self, context: AgentContext) -> Dict[str, Any]:
        """具体分析逻辑，由子类实现"""
        pass
    
    def calculate_score(self, scores: Dict[str, float]) -> float:
        """
        计算综合评分
        
        Args:
            scores: 各维度评分字典
        
        Returns:
            综合评分
        """
        if not scores:
            return 0.0
        
        return sum(scores.values()) / len(scores)


class LeaderAgent(BaseAgent):
    """Leader Agent基类"""
    
    def __init__(self):
        super().__init__(AgentType.LEADER, "决策中枢", 0)
        self.worker_reports: Dict[str, AnalysisReportMessage] = {}
    
    def collect_reports(self, reports: List[AnalysisReportMessage]):
        """收集Worker报告"""
        for report in reports:
            self.worker_reports[report.agent_type] = report
    
    def calculate_composite_score(self) -> float:
        """计算综合评分 - 改进版：处理部分Worker失败情况，保证决策完整性"""
        weights = self.get_current_weights()
        total_score = 0.0
        expected_agents = {'technical', 'intelligence', 'fundamental', 'risk'}
        missing_agents = []
        
        for agent_type, report in self.worker_reports.items():
            weight = weights.get(agent_type, 0.25)  # 默认权重兜底
            total_score += report.overall_score * weight
        
        # 处理缺失的Agent（失败或未报告），使用默认低分5.0
        for agent_type in expected_agents:
            if agent_type not in self.worker_reports:
                missing_agents.append(agent_type)
                default_score = 5.0  # 中性偏低
                weight = weights.get(agent_type, 0.25)
                total_score += default_score * weight
                self.logger.warning(f"缺失 {agent_type} 报告，使用默认分 {default_score}")
        
        if missing_agents:
            self.logger.warning(f"分析不完整，缺失报告: {missing_agents}。综合评分已调整。")
        
        return min(total_score, 10.0)  # 上限10分
    
    def make_decision(self, context: AgentContext, 
                       reports: List[AnalysisReportMessage]) -> TradeDecisionMessage:
        """
        做出交易决策
        
        Args:
            context: Agent上下文
            reports: 各Worker的报告
        
        Returns:
            交易决策消息
        """
        # 收集报告
        self.collect_reports(reports)
        
        # 计算综合评分
        composite_score = self.calculate_composite_score()
        
        # 检查风控否决
        risk_report = self.worker_reports.get('risk')
        if risk_report and hasattr(risk_report, 'conclusion'):
            if risk_report.conclusion.get('action') == 'reject':
                return self._create_reject_decision(context, composite_score)
        
        # 确定交易动作
        action = self._determine_action(composite_score)
        
        # 构建执行方案
        execution = self._build_execution(reports)
        
        # 构建理由
        rationale = self._build_rationale(reports)
        
        # 创建决策消息
        header = MessageHeader()
        header.sender = {
            'agent_id': self.agent_id,
            'agent_name': self.name
        }
        
        confidence = 'high' if composite_score >= 8 else ('medium' if composite_score >= 7 else 'low')
        
        return TradeDecisionMessage(
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
    
    def _determine_action(self, score: float) -> str:
        """根据评分确定交易动作"""
        if score >= 8.0:
            return 'strong_buy'
        elif score >= 7.0:
            return 'buy'
        elif score >= 5.0:
            return 'watch'
        else:
            return 'avoid'
    
    def _create_reject_decision(self, context: AgentContext, score: float) -> TradeDecisionMessage:
        """创建风控否决决策"""
        header = MessageHeader()
        
        return TradeDecisionMessage(
            header=header,
            stock_code=context.stock_code,
            stock_name=context.stock_name,
            final_action='risk_reject',
            confidence='high',
            composite_score=score,
            rationale={
                'reject_reason': ['风控否决：风险过高'],
                'risk_warnings': ['请查看风控报告了解详情']
            }
        )
    
    def _build_execution(self, reports: List[AnalysisReportMessage]) -> Dict[str, Any]:
        """构建执行方案"""
        execution = {
            'entry_zone': [],
            'stop_loss': 0,
            'take_profit_1': 0,
            'take_profit_2': 0,
            'position_size': 0.15,
            'holding_period_estimate': '5-7 trading days'
        }
        
        # 从技术分析报告获取入场和止损止盈
        tech_report = self.worker_reports.get('technical')
        if tech_report and tech_report.conclusion:
            execution['entry_zone'] = tech_report.conclusion.get('entry_zone', [])
            execution['stop_loss'] = tech_report.conclusion.get('stop_loss', 0)
            execution['take_profit_1'] = tech_report.conclusion.get('take_profit_1', 0)
            execution['take_profit_2'] = tech_report.conclusion.get('take_profit_2', 0)
        
        # 从风控报告获取仓位限制
        risk_report = self.worker_reports.get('risk')
        if risk_report and risk_report.conclusion:
            execution['position_size'] = min(
                execution['position_size'],
                risk_report.conclusion.get('max_position_allowed', 0.15)
            )
        
        return execution
    
    def _build_rationale(self, reports: List[AnalysisReportMessage]) -> Dict[str, List[str]]:
        """构建理由"""
        buy_reasons = []
        risk_warnings = []
        
        for agent_type, report in self.worker_reports.items():
            if report.key_points:
                buy_reasons.extend([f"[{report.agent_type}] {p}" for p in report.key_points[:2]])
            if report.risk_points:
                risk_warnings.extend([f"[{report.agent_type}] {p}" for p in report.risk_points])
        
        return {
            'buy_reasons': buy_reasons,
            'risk_warnings': risk_warnings
        }
    
    def _build_score_breakdown(self) -> Dict[str, Dict[str, float]]:
        """构建评分明细"""
        weights = self.get_current_weights()
        breakdown = {}
        
        for agent_type, report in self.worker_reports.items():
            weight = weights.get(agent_type, 0)
            breakdown[agent_type] = {
                'score': report.overall_score,
                'weight': weight,
                'weighted': report.overall_score * weight
            }
        
        return breakdown
    
    def _build_follow_up(self, reports: List[AnalysisReportMessage]) -> Dict[str, Any]:
        """构建后续跟踪"""
        return {
            'monitor_signals': [
                '跌破关键支撑位需警惕',
                '放量突破可加仓',
                '触及止损位必须离场'
            ],
            'review_schedule': '每日盘后更新分析'
        }


class ReviewAgent(BaseAgent):
    """复盘分析师Agent"""
    
    def __init__(self):
        super().__init__(AgentType.REVIEW, "复盘分析师", 0)
    
    def analyze(self, context: AgentContext) -> Dict[str, Any]:
        """复盘分析"""
        return self._do_review(context)
    
    def _do_analysis(self, context: AgentContext) -> Dict[str, Any]:
        return self._do_review(context)
    
    @abstractmethod
    def _do_review(self, context: AgentContext) -> Dict[str, Any]:
        """具体复盘逻辑，由子类实现"""
        pass
    
    def calculate_accuracy(self, trades: List[Dict[str, Any]]) -> Dict[str, float]:
        """计算各角色准确率"""
        accuracy = {
            'technical': 0.0,
            'intelligence': 0.0,
            'risk': 0.0,
            'fundamental': 0.0
        }
        
        # 需要根据交易结果计算准确率
        # 这里返回示例数据
        return accuracy
    
    def suggest_weight_adjustment(self, accuracy_rates: Dict[str, float]) -> Dict[str, float]:
        """建议权重调整"""
        current_weights = self.get_current_weights()
        new_weights = {}
        
        for agent_type, rate in accuracy_rates.items():
            current = current_weights.get(agent_type, 0)
            # 根据准确率调整权重
            adjustment = (rate - 0.5) * 0.8  # 调整系数
            new_weights[agent_type] = max(0.1, min(0.5, current + adjustment * current))
        
        # 归一化
        total = sum(new_weights.values())
        for agent_type in new_weights:
            new_weights[agent_type] = round(new_weights[agent_type] / total, 2)
        
        return new_weights
