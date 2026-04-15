"""
LLM 情报员
职责：资金流向、北向资金、市场情绪
"""
from typing import Dict, Any
from .base_llm_agent import BaseLLMAgent
from .models import AgentReport, StockAnalysisContext


class LLMIntelligence(BaseLLMAgent):
    """
    LLM 情报员
    
    专长：
    - 主力资金流向分析
    - 北向资金（沪深港通）追踪
    - 融资融券数据解读
    - 市场情绪量化
    - 龙虎榜数据分析
    """
    
    DEFAULT_SYSTEM_PROMPT = """你是一位专业的市场情报分析专家，专注于资金流向和市场情绪的分析。

你的专业领域：
1. 资金流向分析：
   - 主力资金净流入/净流出
   - 超大单、大单、中单、小单资金分布
   - 资金流入板块和个股
2. 北向资金（沪深港通）：
   - 外资每日净买卖情况
   - 外资持股比例变化
   - 外资偏好行业和个股
3. 融资融券：
   - 融资余额变化趋势
   - 融券余额变化
   - 融资融券比分析
4. 市场情绪指标：
   - 涨跌停家数
   - 涨停板炸板率
   - 炸板后次日表现
5. 龙虎榜：
   - 营业部游资动向
   - 机构席位买卖
   - 知名游资操作风格

你的分析特点：
- 资金是股价的驱动力，密切关注大资金动向
- 区分长线资金和短线游资
- 关注情绪拐点
- 追踪聪明钱的动向

请始终以 JSON 格式输出分析结果。"""
    
    AGENT_ROLE = "intelligence"
    ROLE_DESCRIPTION = "情报分析专家，擅长资金流向、北向资金、市场情绪分析"
    
    def __init__(
        self,
        name: str = "市场情报员",
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
    
    def analyze(self, context) -> AgentReport:
        """
        执行情报分析
        
        Args:
            context: 分析上下文
            
        Returns:
            情报分析报告
        """
        # 兼容字符串输入
        if isinstance(context, str):
            self.logger.info("情报分析（字符串提示词模式）")
            response = self.chat(context)
            result = self.parse_structured_response(response)
            return AgentReport(
                agent_name=self.name,
                agent_role=self.role,
                score=result.get("score", 5.0),
                confidence=result.get("confidence", 0.5),
                summary=result.get("summary", "情报分析完成"),
                analysis=result.get("analysis", response),
                risks=result.get("risks", []),
                opportunities=result.get("opportunities", [])
            )
        
        self.logger.info("情报分析中...")
        
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
            summary=result.get("summary", "情报分析完成"),
            analysis=result.get("analysis", response),
            risks=result.get("risks", []),
            opportunities=result.get("opportunities", []),
            metadata={
                "main_force_flow": result.get("main_force_flow", "unknown"),
                "north_flow": result.get("north_flow", "unknown"),
                "margin_trading": result.get("margin_trading", {}),
                "sentiment": result.get("sentiment", "neutral")
            }
        )
        
        return report
    
    def build_analysis_prompt(self, context: StockAnalysisContext) -> str:
        """构建情报分析提示词"""
        prompt_parts = [
            f"请对股票 {context.stock_name}({context.stock_code}) 进行资金面和市场情绪分析。",
            "",
            f"市场数据: {context.market_data}",
            f"相关新闻: {context.news_data[:5] if context.news_data else '暂无'}",
            "",
            "=== 分析要求 ===",
            "1. 主力资金：分析近5日主力资金净流入情况",
            "2. 北向资金：判断外资是买入还是卖出",
            "3. 融资融券：分析融资余额变化趋势",
            "4. 市场情绪：从新闻和公告中判断市场情绪",
            "5. 龙虎榜：分析营业部资金动向（如有）",
            "",
            "请以 JSON 格式输出:",
            """{
    "score": 0-10 评分,
    "confidence": 0-1 置信度,
    "summary": 一句话资金面判断,
    "analysis": 详细分析,
    "risks": ["风险点1", "风险点2"],
    "opportunities": ["机会点1", "机会点2"],
    "main_force_flow": "净流入/净流出/持平",
    "north_flow": "净买入/净卖出/持平",
    "margin_trading": {
        "margin_balance_trend": "上升/下降/持平",
        "margin_ratio": 融资融券比
    },
    "sentiment": "乐观/中性/悲观",
    "smart_money_signal": "跟随/逆势/观望"
}"""
        ]
        
        return "\n".join(prompt_parts)


__all__ = ['LLMIntelligence']
