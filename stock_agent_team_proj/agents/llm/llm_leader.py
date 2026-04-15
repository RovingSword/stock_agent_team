"""
LLM 决策队长
职责：任务分配、讨论主持、最终决策
"""
from typing import List, Dict, Any, Optional
from .base_llm_agent import BaseLLMAgent, DiscussionAgent
from .models import (
    AgentReport, 
    DiscussionMessage,
    StockAnalysisContext
)


class LLMLeader(DiscussionAgent):
    """
    LLM 决策队长
    
    特点：
    - 协调各专业 Agent
    - 主持多轮讨论
    - 综合各方意见做出最终决策
    """
    
    DEFAULT_SYSTEM_PROMPT = """你是一位经验丰富的投资决策专家，在股票投资领域有超过20年的实战经验。

你的核心能力：
1. 宏观分析：准确判断市场趋势和行业周期
2. 决策整合：综合技术面、基本面、资金面等多维度信息
3. 风险管理：在追求收益的同时始终把风险控制放在首位
4. 逻辑推理：能够从复杂信息中提炼关键逻辑

你的工作风格：
- 客观中立，不预设立场
- 数据驱动，让证据说话
- 权衡利弊，理性决策
- 敢于认错，及时纠偏

请始终以 JSON 格式输出分析结果。"""
    
    AGENT_ROLE = "leader"
    ROLE_DESCRIPTION = "投资决策队长，综合各方意见做出最终决策"
    
    def __init__(
        self,
        name: str = "决策队长",
        provider: str = "mock",
        **kwargs
    ):
        super().__init__(
            name=name,
            role=self.AGENT_ROLE,
            provider=provider,
            system_prompt=self.DEFAULT_SYSTEM_PROMPT,
            **kwargs
        )
        
        # 收集的分析报告
        self.worker_reports: Dict[str, AgentReport] = {}
        
        # 决策历史
        self.decision_history: List[Dict[str, Any]] = []
    
    def analyze(self, context) -> AgentReport:
        """
        执行综合分析并做出决策
        
        Args:
            context: 分析上下文
            
        Returns:
            综合分析报告
        """
        # 兼容字符串输入
        if isinstance(context, str):
            self.logger.info("Leader分析（字符串提示词模式）")
            response = self.chat(context)
            result = self.parse_structured_response(response)
            return AgentReport(
                agent_name=self.name,
                agent_role=self.role,
                score=result.get("score", 5.0),
                confidence=result.get("confidence", 0.5),
                summary=result.get("summary", "分析完成"),
                analysis=result.get("analysis", response),
                risks=result.get("risks", []),
                opportunities=result.get("opportunities", [])
            )
        
        self.logger.info("Leader分析中...")
        
        # 1. 整合各 Worker 的分析结果
        analysis_parts = []
        if self.worker_reports:
            for role, report in self.worker_reports.items():
                analysis_parts.append(f"【{report.agent_name}】评分{report.score}：{report.summary}")
        
        # 2. 如果没有 Worker 报告，直接分析
        if not analysis_parts:
            return self._direct_analyze(context)
        
        # 3. 构建综合分析提示词
        combined_analysis = "\n".join(analysis_parts)
        prompt = self._build_final_decision_prompt(context, combined_analysis)
        
        # 4. 调用 LLM
        response = self.chat(prompt)
        
        # 5. 解析结果
        result = self.parse_structured_response(response)
        
        # 6. 生成报告
        report = AgentReport(
            agent_name=self.name,
            agent_role=self.role,
            score=result.get("score", 5.0),
            confidence=result.get("confidence", 0.5),
            summary=result.get("summary", "综合分析完成"),
            analysis=result.get("analysis", response),
            risks=result.get("risks", []),
            opportunities=result.get("opportunities", []),
            metadata={
                "decision": result.get("decision", "watch"),
                "action": result.get("action", "观望"),
                "worker_count": len(self.worker_reports)
            }
        )
        
        # 保存决策
        self.decision_history.append({
            "context": context.stock_code,
            "report": report,
            "worker_reports": {k: v.to_dict() for k, v in self.worker_reports.items()}
        })
        
        return report
    
    def _direct_analyze(self, context: StockAnalysisContext) -> AgentReport:
        """直接分析（没有 Worker 报告时）"""
        prompt = f"""请对股票 {context.stock_name}({context.stock_code}) 进行全面分析。

分析要点：
1. 结合市场环境和行业趋势
2. 评估当前价格位置和估值水平
3. 考虑资金流向和市场情绪
4. 提出具体的投资建议

请以 JSON 格式输出分析结果，包含:
- score: 0-10 的评分
- confidence: 0-1 的置信度
- summary: 一句话总结
- analysis: 详细分析
- risks: 风险点列表
- opportunities: 机会点列表
- decision: 决策建议 (buy/sell/watch/hold)
- action: 操作建议
- target_price: 目标价格（可选）
- position_ratio: 建议仓位（0-100%）
"""
        response = self.chat(prompt)
        result = self.parse_structured_response(response)
        
        return AgentReport(
            agent_name=self.name,
            agent_role=self.role,
            score=result.get("score", 5.0),
            confidence=result.get("confidence", 0.5),
            summary=result.get("summary", "分析完成"),
            analysis=result.get("analysis", response),
            risks=result.get("risks", []),
            opportunities=result.get("opportunities", []),
            metadata={
                "decision": result.get("decision", "watch"),
                "action": result.get("action", "观望"),
                "target_price": result.get("target_price"),
                "position_ratio": result.get("position_ratio", 0)
            }
        )
    
    def _build_final_decision_prompt(
        self,
        context: StockAnalysisContext,
        combined_analysis: str
    ) -> str:
        """构建最终决策提示词"""
        return f"""作为投资决策专家，请根据以下各专业 Agent 的分析结果，对股票 {context.stock_name}({context.stock_code}) 做出最终投资决策。

=== 各 Agent 分析摘要 ===
{combined_analysis}

=== 决策要求 ===
1. 权重分配：综合考虑技术面(25%)、基本面(25%)、资金面(25%)、风险控制(25%)
2. 风险优先：当各指标出现矛盾时，优先考虑风险因素
3. 具体建议：给出明确的操作建议（买入/卖出/观望）和仓位建议
4. 阈值设定：如需买入，请给出建议的买入价格区间和止损位

请以 JSON 格式输出最终决策:
{{
    "score": 综合评分(0-10),
    "confidence": 置信度(0-1),
    "summary": 一句话决策,
    "analysis": 决策理由,
    "risks": 主要风险,
    "opportunities": 主要机会,
    "decision": "buy/sell/watch/hold",
    "action": 具体操作,
    "target_price": 目标价格,
    "stop_loss": 止损价格,
    "position_ratio": 建议仓位(0-100)
}}"""
    
    def collect_worker_report(self, report: AgentReport):
        """
        收集 Worker Agent 的报告
        
        Args:
            report: Worker 分析报告
        """
        self.worker_reports[report.agent_role] = report
        self.logger.info(f"收到 {report.agent_name} 的报告，评分: {report.score}")
    
    def clear_worker_reports(self):
        """清空 Worker 报告"""
        self.worker_reports = {}
    
    def get_composite_score(self) -> float:
        """计算综合评分"""
        if not self.worker_reports:
            return 5.0
        
        total_score = 0.0
        total_weight = 0.0
        
        weights = {
            "technical": 0.25,
            "intelligence": 0.25,
            "fundamental": 0.25,
            "risk": 0.25
        }
        
        for role, report in self.worker_reports.items():
            weight = weights.get(role, 0.2)
            total_score += report.score * weight
            total_weight += weight
        
        if total_weight == 0:
            return 5.0
        
        return total_score / total_weight * (total_weight / sum(weights.values()))


__all__ = ['LLMLeader']
