"""
LLM 基本面分析员
职责：财务分析、估值评估
"""
from typing import Dict, Any
from .base_llm_agent import BaseLLMAgent
from .models import AgentReport, StockAnalysisContext


class LLMFundamental(BaseLLMAgent):
    """
    LLM 基本面分析员
    
    专长：
    - 财务报表分析（资产负债表、利润表、现金流量表）
    - 估值方法（PE、PB、PS、DCF）
    - 行业对比分析
    - 成长性评估
    - 管理层评估
    """
    
    DEFAULT_SYSTEM_PROMPT = """你是一位资深的基本面分析专家，专注于企业内在价值的评估。

你的专业领域：
1. 财务报表分析：
   - 盈利能力：毛利率、净利率、ROE、ROA
   - 成长能力：营收增速、利润增速
   - 偿债能力：资产负债率、流动比率
   - 运营效率：存货周转、应收账款周转
2. 估值分析：
   - PE（市盈率）：与历史和行业对比
   - PB（市净率）：适合金融和周期股
   - PS（市销率）：适合成长股
   - PEG：评估成长与估值匹配度
3. 行业分析：
   - 行业地位和竞争格局
   - 行业周期和景气度
   - 政策影响
4. 成长性评估：
   - 业绩增长驱动因素
   - 市场份额变化
   - 新业务拓展
5. 现金流分析：
   - 经营现金流质量
   - 自由现金流
   - 分红能力

你的分析特点：
- 重视财务数据的真实性和持续性
- 关注现金流而非会计利润
- 寻找具有护城河的公司
- 合理估值，不追高

请始终以 JSON 格式输出分析结果。"""
    
    AGENT_ROLE = "fundamental"
    ROLE_DESCRIPTION = "基本面分析专家，擅长财务分析、估值评估、行业研究"
    
    def __init__(
        self,
        name: str = "基本面分析员",
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
        执行基本面分析
        
        Args:
            context: 分析上下文
            
        Returns:
            基本面分析报告
        """
        # 兼容字符串输入
        if isinstance(context, str):
            self.logger.info("基本面分析（字符串提示词模式）")
            response = self.chat(context)
            result = self.parse_structured_response(response)
            return AgentReport(
                agent_name=self.name,
                agent_role=self.role,
                score=result.get("score", 5.0),
                confidence=result.get("confidence", 0.5),
                summary=result.get("summary", "基本面分析完成"),
                analysis=result.get("analysis", response),
                risks=result.get("risks", []),
                opportunities=result.get("opportunities", [])
            )
        
        self.logger.info("基本面分析中...")
        
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
            summary=result.get("summary", "基本面分析完成"),
            analysis=result.get("analysis", response),
            risks=result.get("risks", []),
            opportunities=result.get("opportunities", []),
            metadata={
                "valuation": result.get("valuation", {}),
                "financial_health": result.get("financial_health", "unknown"),
                "growth_potential": result.get("growth_potential", "unknown")
            }
        )
        
        return report
    
    def build_analysis_prompt(self, context: StockAnalysisContext) -> str:
        """构建基本面分析提示词"""
        prompt_parts = [
            f"请对股票 {context.stock_name}({context.stock_code}) 进行基本面分析。",
            "",
            f"基本面数据: {context.fundamental_data}",
            "",
            "=== 分析要求 ===",
            "1. 盈利能力：分析毛利率、净利率、ROE等指标",
            "2. 成长性：评估营收和利润增速",
            "3. 估值水平：计算PE/PB/PS，与行业对比",
            "4. 财务健康：评估资产负债率和现金流",
            "5. 行业地位：判断公司在行业中的竞争力",
            "6. 风险因素：识别可能影响基本面的风险",
            "",
            "请以 JSON 格式输出:",
            """{
    "score": 0-10 评分,
    "confidence": 0-1 置信度,
    "summary": 一句话基本面判断,
    "analysis": 详细分析,
    "risks": ["风险点1", "风险点2"],
    "opportunities": ["机会点1", "机会点2"],
    "valuation": {
        "pe": 市盈率,
        "pb": 市净率,
        "ps": 市销率,
        "peg": 市盈增长比,
        "valuation_level": "低估/合理/高估"
    },
    "financial_health": "优秀/良好/一般/较差",
    "growth_potential": "高成长/稳定成长/低速成长/衰退",
    "moat": "护城河描述"
}"""
        ]
        
        return "\n".join(prompt_parts)


__all__ = ['LLMFundamental']
