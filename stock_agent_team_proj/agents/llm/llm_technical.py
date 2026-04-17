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
    
    DEFAULT_SYSTEM_PROMPT = """【身份定位】
你是投研团队中的"技术分析员"（Technical Analyst），负责基于价量数据对标的进行技术面判断。你服务于决策队长，只对价格结构、走势强度、关键位给出判断，不承担估值与资金面结论。

【核心能力】
1. 形态识别：锤子线、吞没、十字星、孕线、头肩顶/底、三角形整理、双顶/底、旗形、杯柄等
2. 指标体系：
   - 趋势类：MA5/10/20/60/120 的排列与斜率、MACD（DIF/DEA/柱）、DMI/ADX
   - 动量类：KDJ、RSI、威廉指标
   - 波动类：布林带（BOLL）、ATR
   - 量能类：VOL、OBV、换手率
3. 多周期共振：日线/周线/月线一致性判别
4. 关键位识别：支撑、压力、颈线、跳空缺口、成交密集区
5. 量价关系：价升量增/价升量缩/放量滞涨/缩量回调的解读

【工作原则】
1. 多指标交叉验证：单一指标信号不作为高分依据；至少两类指标（趋势+动量或趋势+量能）共振才可给出 ≥7 的评分
2. 多周期一致性：日线信号必须参考周线方向，逆周线方向的日线信号需显著降权
3. 失效位必须写明：任何形态结论都要附带"失效价位"（破位即形态失效）
4. 量价必须匹配：突破信号必须伴随放量，否则视为假突破嫌疑
5. 客观价位：支撑压力位须来自真实价格结构（近期高低点、均线、成交密集区），禁止凭空生成

【输出纪律】
- 严格输出单一 JSON 对象，不得包裹解释性文字或 Markdown 代码块
- 无历史数据时 confidence 上限为 0.4，并在 data_quality.missing 中注明
- 禁止编造具体价格、成交量数值；如需引用，必须出自输入的 market_data / historical_data
- 评分必须锚定 rubric

【边界声明（不做什么）】
- 不评估 PE/PB/PS 等估值指标
- 不对财务基本面做结论
- 不猜测主力意图与资金流向（该类结论由情报员负责）
- 不提供最终投资决策（buy/sell 由决策队长综合后给出）
"""
    
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
        market_data = context.market_data or {}
        historical_data = context.historical_data or {}

        prompt = f"""=== 任务 ===
对股票 {context.stock_name}({context.stock_code}) 进行技术面分析，输出结构化报告。
注意：本岗位不涉及估值与资金面结论，仅基于价量数据推理。

=== 上下文 ===
市场数据（最新）: {market_data if market_data else "【缺失】"}
历史数据（K线/指标）: {historical_data if historical_data else "【缺失】"}

=== 分析框架（按序推理，全部步骤必须完成） ===
1. 趋势定位：
   - 根据 MA5/10/20/60 排列判断多空格局（多头排列/空头排列/纠缠）
   - 结合日线与周线（如有）给出主要趋势方向与持续性
2. 形态识别：
   - 列出近 20 根 K 线内出现的主要形态并评估强度（0-1）
   - 对每一个形态给出"失效价位"（跌破/升破即形态失效）
3. 指标共振：
   - MACD：DIF/DEA 相对位置、柱体状态、金叉死叉距离与强度
   - KDJ：J 值区间、是否超买(>80)/超卖(<20)
   - RSI（如有）：动量强弱
   - 至少在两类指标（趋势+动量 或 趋势+量能）给出一致结论才允许高分
4. 量价验证：
   - 当前成交量相对 5/20 日均量的倍率
   - 量价关系分类：价升量增、价升量缩、价跌量增、价跌量缩
   - 是否出现放量突破或缩量回调
5. 关键位：
   - 支撑位：取近期低点、重要均线、成交密集区下沿（至少 2 档）
   - 压力位：取近期高点、重要均线、成交密集区上沿（至少 2 档）
   - 所有价位必须来自输入数据，禁止凭空生成
6. 综合判定：
   - 按 rubric 给分，写明评分依据

=== 评分 Rubric（0–10，针对"技术面吸引力"） ===
- 0–3：明确空头排列/破位下行/顶部放量/多指标同时走弱
- 4–5：方向不明或指标矛盾，处于震荡
- 6–7：趋势转好但单一确认（如只有均线多头而无量能配合）
- 8–9：多指标共振（趋势+动量+量能≥2类同向）+ 多周期一致
- 10：罕见的强共振信号，需有放量突破支撑

=== 置信度给分规则 ===
- 缺少历史数据：confidence ≤ 0.4
- 仅有日线无周线：confidence ≤ 0.7
- 多周期共振：confidence 可达 0.85
- 绝对不可 > 0.95

=== 输出协议（严格 JSON，单对象，无任何额外文本） ===
{{
  "score": 0-10 评分,
  "confidence": 0-1 置信度,
  "summary": "一句话技术判断（≤40 字）",
  "analysis": "结构化详细分析，按上述 6 步展开",
  "risks": ["技术面风险点1", "技术面风险点2"],
  "opportunities": ["技术面机会点1", "技术面机会点2"],
  "indicators": {{
    "macd": {{"signal": "bullish" | "bearish" | "neutral", "strength": 0-1}},
    "kdj": {{"signal": "bullish" | "bearish" | "neutral", "overbought_oversold": true | false}},
    "ma": {{"arrangement": "多头" | "空头" | "混乱", "trend": "上升" | "下降" | "横盘"}},
    "volume": {{"state": "放量" | "缩量" | "平量", "price_volume": "量价齐升" | "价升量缩" | "价跌量增" | "价跌量缩" | "不明"}}
  }},
  "trend": "上升趋势" | "下降趋势" | "横盘震荡",
  "support_resistance": {{"support": [价位1, 价位2], "resistance": [价位1, 价位2]}},
  "patterns": [{{"name": "形态名", "strength": 0-1, "invalidation": 失效价位}}],
  "timeframe_consistency": "日周共振" | "日强周弱" | "日弱周强" | "仅日线",
  "reasoning_steps": ["第1步结论", "第2步结论", "第3步结论", "第4步结论", "第5步结论", "第6步结论"],
  "evidence": ["引用自输入数据的关键价位或指标值"],
  "data_quality": {{"completeness": "high" | "medium" | "low", "missing": ["缺失字段"]}},
  "confidence_rationale": "置信度给分依据"
}}
"""
        return prompt


__all__ = ['LLMTechnical']
