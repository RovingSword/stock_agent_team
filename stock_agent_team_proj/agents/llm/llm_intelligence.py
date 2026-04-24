"""
LLM 情报员
职责：资金流向、北向资金、市场情绪
"""
from typing import Any, Dict, Optional
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
    
    DEFAULT_SYSTEM_PROMPT = """【身份定位】
你是投研团队中的"市场情报员"（Market Intelligence Analyst），专注于资金流向、筹码结构、市场情绪的实证研判。你代表"聪明钱视角"，服务于决策队长，不提供估值与技术形态结论，也不给出最终买卖指令。

【核心能力】
1. 主力资金：
   - 超大单/大单/中单/小单净流入结构
   - 近 1/3/5/10/20 日资金累计流向趋势
   - 主力建仓 / 拉高出货 / 震荡换手的识别
2. 北向资金（陆股通）：
   - 日/周净买卖额与趋势
   - 外资持股比例变化与加减仓节奏
   - 北向连续净买入对基本面稳定性的指示意义
3. 融资融券：
   - 融资余额变化趋势（散户情绪代理）
   - 融券余额与融券占比（空头力量）
   - 融资融券比 = 融资余额 / 融券余额
4. 筹码与龙虎榜：
   - 筹码集中度、获利盘比例、套牢盘位置
   - 营业部席位性质（知名游资 / 机构专用 / 普通）
   - 一线游资风格识别（接力、打板、低吸、孵化）
5. 市场情绪：
   - 涨跌停家数、连板高度与阶梯、炸板率
   - 情绪周期（冰点 → 启动 → 高潮 → 退潮）定位
   - 板块/题材轮动与标的归属

【工作原则】
1. 三维交叉：主力资金、北向资金、融资余额三条线索共振才可给 ≥7 的分；单一信号最多 6 分
2. 区分资金性质：
   - 北向与机构 → 长线定价力
   - 游资与融资 → 短线情绪/博弈
   - 两类资金的共振 vs 对冲要分别解读
3. 警惕假信号：
   - 单日异动可能是假动作，需看持续性（连续 3 日同向）
   - 拉高伴随大单净流出 = 出货嫌疑
   - 炸板后次日走弱是情绪退潮信号
4. 时间衰减：5 日内信号权重高于 20 日外的信号
5. 不编造数据：所有资金数据必须来自输入的 market_data / news_data

【输出纪律】
- 严格输出单一 JSON 对象，不得包裹解释性文字或 Markdown 代码块
- 缺失资金流数据时 confidence 上限为 0.4，并在 data_quality.missing 注明
- 禁止编造具体金额、持股比例、席位名称
- 评分必须锚定 rubric

【边界声明（不做什么）】
- 不评价 PE/PB 等估值指标
- 不评判企业基本面质地
- 不做 K 线形态与指标分析
- 不替代决策队长给出最终 buy/sell 指令
"""
    
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
            return self.build_agent_report(
                response=response,
                result=result,
                default_summary="情报分析完成",
            )
        
        self.logger.info("情报分析中...")
        
        # 构建分析提示词
        prompt = self.build_analysis_prompt(context)
        
        # 调用 LLM
        response = self.chat(prompt)
        
        # 解析结果
        result = self.parse_structured_response(response)
        
        return self.build_agent_report(
            response=response,
            result=result,
            default_summary="情报分析完成",
            metadata={
                "main_force_flow": result.get("main_force_flow", "unknown"),
                "north_flow": result.get("north_flow", "unknown"),
                "margin_trading": result.get("margin_trading", {}),
                "sentiment": result.get("sentiment", "neutral"),
                "smart_money_signal": result.get("smart_money_signal", "观望"),
            }
        )
    
    def build_analysis_prompt(self, context: StockAnalysisContext) -> str:
        """构建情报分析提示词"""
        market = context.market_data or {}
        news = context.news_data[:5] if context.news_data else []

        prompt = f"""=== 任务 ===
对股票 {context.stock_name}({context.stock_code}) 进行资金面与情绪面分析，输出结构化报告。
注意：本岗位仅对资金流向、筹码结构、市场情绪负责，不涉及估值或技术形态结论。

=== 上下文 ===
市场数据: {market if market else "【缺失】"}
相关新闻（近 5 条）: {news if news else "【缺失】"}

=== 分析框架（按序推理） ===
1. 主力资金扫描：
   - 近 1/5/20 日主力资金净流入方向与金额级别
   - 大单与超大单是否同向
   - 是否出现"拉高+大单净流出"的出货嫌疑
2. 北向资金判读：
   - 近 5/20 日北向净买卖
   - 是否连续净买入（≥3 日）或连续净卖出
   - 外资持股比例的斜率
3. 融资融券：
   - 融资余额趋势（上升/下降/持平）
   - 融券余额与变化
   - 融资融券比（反映多空情绪）
4. 筹码与龙虎榜（如有）：
   - 主要席位性质（机构 / 一线游资 / 普通游资 / 散户）
   - 买卖方向与金额
   - 是否出现机构与游资对打
5. 情绪研判：
   - 市场整体情绪位置（冰点/回暖/高潮/退潮）
   - 个股所属板块/题材是否处于资金偏好区
   - 涨跌停、连板高度等宏观情绪指标（若输入可得）
6. 三维交叉验证：
   - 主力、北向、融资三者方向是否一致
   - 一致同向且持续 ≥3 日 → 高可信度正/负面信号
   - 相互背离 → 降低置信度，倾向观望
7. 综合判定：按 rubric 评分

=== 评分 Rubric（0–10，针对"资金面吸引力"） ===
- 0–3：主力+北向+融资三杀 或 明确出货信号
- 4–5：信号分歧、资金观望或信号不足
- 6–7：单一维度偏正向（例如仅主力净流入，北向中性）
- 8–9：三维至少两维共振向上，持续多日
- 10：三维强共振 + 情绪周期启动期 + 板块强势（罕见）

=== 置信度给分规则 ===
- 无资金流核心数据：confidence ≤ 0.4
- 只有单日数据无持续性验证：confidence ≤ 0.6
- 多日三维交叉：confidence 可达 0.85
- 绝对不可 > 0.95

=== 输出协议（严格 JSON，单对象，无任何额外文本） ===
{{
  "score": 0-10 评分,
  "confidence": 0-1 置信度,
  "summary": "一句话资金面判断（≤40 字）",
  "analysis": "结构化详细分析，按上述 7 步展开",
  "risks": ["资金面风险点1", "资金面风险点2"],
  "opportunities": ["资金面机会点1", "资金面机会点2"],
  "main_force_flow": "净流入" | "净流出" | "持平",
  "main_force_persistence_days": 数值（近期同向持续天数，无数据填 0),
  "north_flow": "净买入" | "净卖出" | "持平",
  "north_persistence_days": 数值,
  "margin_trading": {{
    "margin_balance_trend": "上升" | "下降" | "持平",
    "margin_ratio": 融资融券比 或 null,
    "short_interest_trend": "上升" | "下降" | "持平"
  }},
  "sentiment": "乐观" | "中性" | "悲观",
  "sentiment_phase": "冰点" | "回暖" | "高潮" | "退潮" | "不明",
  "smart_money_signal": "跟随" | "逆势" | "观望",
  "cross_validation": "三维同向" | "两维同向" | "分歧" | "数据不足",
  "top_seats": [{{"seat_type": "机构" | "一线游资" | "普通游资" | "散户", "direction": "买入" | "卖出", "note": "席位或金额描述"}}],
  "reasoning_steps": ["第1步结论", "第2步结论", "第3步结论", "第4步结论", "第5步结论", "第6步结论", "第7步结论"],
  "evidence": ["引用自输入数据的关键资金/情绪数据"],
  "data_quality": {{"completeness": "high" | "medium" | "low", "missing": ["缺失字段"]}},
  "confidence_rationale": "置信度给分依据"
}}
"""
        return prompt

    @staticmethod
    def interpret_from_intel_package(
        intel_brief: Dict[str, Any],
        intel_report: Optional[Dict[str, Any]],
        stock_code: str,
        stock_name: str,
        tracked_at: str = "",
        gather_time: str = "",
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """对「规则型 IntelBrief + 结构化报告」做网络情报简要解读（委托 utils 层，带缓存）。"""
        from utils.intel_llm_interpret import get_or_create_llm_interpretation

        return get_or_create_llm_interpretation(
            intel_brief,
            intel_report,
            stock_code,
            stock_name,
            tracked_at=tracked_at,
            gather_time=gather_time,
            force_refresh=force_refresh,
        )


__all__ = ['LLMIntelligence']
