"""
LLM 风控官
职责：风险评估、仓位建议、止损止盈
"""
from typing import Dict, Any
from .base_llm_agent import BaseLLMAgent
from .models import AgentReport, StockAnalysisContext


class LLMRisk(BaseLLMAgent):
    """
    LLM 风控官
    
    特点：
    - 风险识别和量化
    - 仓位管理建议
    - 止损止盈策略
    - 风险收益比评估
    """
    
    DEFAULT_SYSTEM_PROMPT = """你是一位经验丰富的风险管理专家，坚持"本金安全第一"的投资原则。

你的核心原则：
1. 本金保护：任何时候都不能让本金遭受不可逆的损失
2. 仓位控制：根据风险程度调整仓位，高风险低仓位
3. 止损纪律：设置明确的止损位，并严格执行
4. 分散投资：避免过度集中持仓
5. 逆势思维：在市场疯狂时保持冷静

你的专业能力：
1. 风险识别：
   - 系统性风险（政策、宏观、汇率等）
   - 非系统性风险（个股、行业）
   - 流动性风险
   - 估值风险
2. 仓位管理：
   - 根据胜率和赔率计算最优仓位
   - 凯利公式应用
   - 金字塔/倒金字塔加仓策略
3. 止损止盈：
   - 固定比例止损
   - 移动止损
   - 时间止损
4. 风险收益比：
   - 计算潜在收益和亏损的比例
   - 评估是否值得参与

你的风格：
- 保守谨慎，宁可错过不要做错
- 量化分析，用数据说话
- 严格执行交易纪律
- 持续监控风险敞口

请始终以 JSON 格式输出分析结果。"""
    
    AGENT_ROLE = "risk"
    ROLE_DESCRIPTION = "风险控制专家，专注于仓位管理、止损止盈、风险评估"
    
    def __init__(
        self,
        name: str = "风控官",
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
        
        # 风控参数
        self.max_single_position = kwargs.get("max_single_position", 30)  # 最大单票仓位%
        self.max_total_position = kwargs.get("max_total_position", 80)    # 最大总仓位%
        self.default_stop_loss = kwargs.get("default_stop_loss", 7)       # 默认止损%
    
    def analyze(self, context) -> AgentReport:
        """
        执行风险评估
        
        Args:
            context: 分析上下文
            
        Returns:
            风险评估报告
        """
        # 兼容字符串输入
        if isinstance(context, str):
            self.logger.info("风控分析（字符串提示词模式）")
            response = self.chat(context)
            result = self.parse_structured_response(response)
            return AgentReport(
                agent_name=self.name,
                agent_role=self.role,
                score=result.get("score", 5.0),
                confidence=result.get("confidence", 0.5),
                summary=result.get("summary", "风控分析完成"),
                analysis=result.get("analysis", response),
                risks=result.get("risks", []),
                opportunities=result.get("opportunities", [])
            )
        
        self.logger.info("风控分析中...")
        
        # 构建分析提示词
        prompt = self.build_analysis_prompt(context)
        
        # 调用 LLM
        response = self.chat(prompt)
        
        # 解析结果
        result = self.parse_structured_response(response)
        
        # 生成报告
        report = AgentReport(
            agent_name=self.name,
            agent_role=self.role,
            score=result.get("score", 5.0),
            confidence=result.get("confidence", 0.5),
            summary=result.get("summary", "风险评估完成"),
            analysis=result.get("analysis", response),
            risks=result.get("risks", []),
            opportunities=result.get("opportunities", []),
            metadata={
                "risk_level": result.get("risk_level", "medium"),
                "recommended_position": result.get("recommended_position", 0),
                "stop_loss": result.get("stop_loss"),
                "take_profit": result.get("take_profit"),
                "risk_reward_ratio": result.get("risk_reward_ratio")
            }
        )
        
        return report
    
    def build_analysis_prompt(self, context: StockAnalysisContext) -> str:
        """构建风险评估提示词"""
        prompt_parts = [
            f"请对股票 {context.stock_name}({context.stock_code}) 进行风险评估。",
            "",
            f"市场数据: {context.market_data}",
            f"基本面数据: {context.fundamental_data}",
            "",
            "=== 风险评估要求 ===",
            "1. 风险识别：列出所有可能的风险因素",
            "2. 风险量化：评估各风险的严重程度",
            "3. 仓位建议：根据风险评估给出仓位建议",
            "4. 止损止盈：建议具体的止损和止盈位",
            "5. 风险收益比：计算潜在收益和风险的比例",
            "",
            "请以 JSON 格式输出:",
            """{
    "score": 0-10 评分（低分=高风险，高分=低风险）,
    "confidence": 0-1 置信度,
    "summary": 一句话风险判断,
    "analysis": 详细分析,
    "risks": ["风险点1", "风险点2"],
    "opportunities": ["风控优势1", "风控优势2"],
    "risk_level": "low/medium/high/critical",
    "recommended_position": 建议仓位(0-100),
    "stop_loss": 建议止损价,
    "stop_loss_ratio": 止损比例(%),
    "take_profit": 建议止盈价,
    "take_profit_ratio": 止盈比例(%),
    "risk_reward_ratio": 风险收益比,
    "action": "approve/reject/watch"
}"""
        ]
        
        return "\n".join(prompt_parts)
    
    def calculate_position_size(
        self,
        account_value: float,
        risk_per_trade: float,
        entry_price: float,
        stop_loss_price: float
    ) -> Dict[str, Any]:
        """
        计算仓位大小
        
        Args:
            account_value: 账户总价值
            risk_per_trade: 每笔交易承受的风险比例
            entry_price: 买入价格
            stop_loss_price: 止损价格
            
        Returns:
            仓位计算结果
        """
        risk_amount = account_value * risk_per_trade
        price_risk = abs(entry_price - stop_loss_price)
        
        if price_risk == 0:
            return {
                "shares": 0,
                "position_value": 0,
                "risk_amount": risk_amount,
                "error": "止损价格不能等于买入价格"
            }
        
        shares = int(risk_amount / price_risk / 100) * 100  # 取整到百股
        position_value = shares * entry_price
        
        return {
            "shares": shares,
            "position_value": position_value,
            "position_ratio": position_value / account_value * 100,
            "risk_amount": risk_amount,
            "price_risk": price_risk,
            "risk_per_share": price_risk / entry_price * 100
        }


__all__ = ['LLMRisk']
