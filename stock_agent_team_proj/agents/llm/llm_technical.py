"""
LLM 技术分析员
职责：K线形态、技术指标、趋势分析
"""
from typing import Dict, Any
from .base_llm_agent import BaseLLMAgent
from .models import AgentReport, StockAnalysisContext


class LLMTechnical(BaseLLMAgent):
    """
    LLM 技术分析员
    
    专长：
    - K线形态识别（锤子线、吞没、十字星等）
    - 技术指标分析（MACD、KDJ、RSI、布林带等）
    - 趋势判断（上升、下降、横盘）
    - 支撑压力位识别
    - 成交量分析
    """
    
    DEFAULT_SYSTEM_PROMPT = """你是一位资深的技术分析专家，精通各种技术分析理论和实战应用。

你的专业领域：
1. K线形态分析：准确识别锤子线、吞没形态、十字星、头肩顶/底等经典形态
2. 技术指标应用：
   - MACD：判断趋势方向和动能强弱，寻找金叉死叉信号
   - KDJ：判断超买超卖，寻找叉点
   - RSI：评估上涨下跌动能
   - 均线系统：MA5/10/20/60 的排列和交叉
   - 布林带：判断通道和突破
3. 趋势分析：识别主要趋势、次级折返和短期波动
4. 量价关系：理解成交量与价格变动的关系
5. 缺口理论：识别普通缺口、突破缺口、衰竭缺口

你的分析风格：
- 图表结合数据，不仅看形态还要量化分析
- 多指标共振时信号更可靠
- 重视成交量的配合
- 结合不同时间周期分析

请始终以 JSON 格式输出分析结果，包含结构化的评分和分析。"""
    
    AGENT_ROLE = "technical"
    ROLE_DESCRIPTION = "技术分析专家，精通K线形态、MACD/KDJ/RSI等指标、趋势判断"
    
    def __init__(
        self,
        name: str = "技术分析员",
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
        执行技术分析
        
        Args:
            context: 分析上下文（StockAnalysisContext 或字符串 prompt）
            
        Returns:
            技术分析报告
        """
        # 兼容字符串输入
        if isinstance(context, str):
            self.logger.info("开始技术分析（字符串提示词模式）")
            response = self.chat(context)
            result = self.parse_structured_response(response)
        else:
            self.logger.info(f"开始技术分析 {context.stock_name}({context.stock_code})")
            prompt = self.build_analysis_prompt(context)
            response = self.chat(prompt)
            result = self.parse_structured_response(response)
        
        return self.build_agent_report(
            response=response,
            result=result,
            default_summary="技术分析完成",
            metadata={
                "indicators": result.get("indicators", {}),
                "trend": result.get("trend", "unknown"),
                "support_resistance": result.get("support_resistance", {})
            }
        )
    
    def build_analysis_prompt(self, context: StockAnalysisContext) -> str:
        """构建技术分析提示词"""
        prompt_parts = [
            f"请对股票 {context.stock_name}({context.stock_code}) 进行技术分析。",
            "",
            f"市场数据: {context.market_data}",
            f"历史数据: {context.historical_data}",
            "",
            "=== 分析要求 ===",
            "1. K线形态：识别近期主要形态，给出形态信号强度",
            "2. 均线分析：判断 MA5/10/20/60 的排列状态",
            "3. MACD：分析 DIF/DEA 状态，寻找金叉死叉",
            "4. KDJ：判断超买超卖区域",
            "5. 成交量：分析量价配合情况",
            "6. 趋势判断：明确当前趋势方向和持续性",
            "7. 支撑压力：识别关键支撑位和压力位",
            "",
            "请以 JSON 格式输出:",
            """{
    "score": 0-10 评分,
    "confidence": 0-1 置信度,
    "summary": 一句话技术判断,
    "analysis": 详细分析,
    "risks": ["风险点1", "风险点2"],
    "opportunities": ["机会点1", "机会点2"],
    "indicators": {
        "macd": {"signal": "bullish/bearish/neutral", "strength": 0-1},
        "kdj": {"signal": "bullish/bearish/neutral", "overbought_oversold": true/false},
        "ma": {"arrangement": "多头/空头/混乱", "trend": "上升/下降/横盘"}
    },
    "trend": "上升趋势/下降趋势/横盘震荡",
    "support_resistance": {"support": [价格], "resistance": [价格]}
}"""
        ]
        
        return "\n".join(prompt_parts)


__all__ = ['LLMTechnical']
