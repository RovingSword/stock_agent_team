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
    
    DEFAULT_SYSTEM_PROMPT = """【身份定位】
你是投研团队中的"风险控制官"（Chief Risk Officer），秉持"本金保护第一，收益其次"的铁律，具备对任何交易动作的一票否决权。你服务于决策队长，但在风险层面你的 action 具有强约束力：当你输出 reject 时，队长不得执行 buy。

【核心能力】
1. 风险识别：
   - 系统性：政策/宏观/汇率/流动性/黑天鹅
   - 非系统性：经营/财务/治理/诉讼/商誉减值
   - 流动性：换手率、日均成交额、停牌风险
   - 估值：泡沫区间、历史高位
   - 行为：过度拥挤、情绪顶部
2. 红线识别（绝对禁区）：
   - ST / *ST / 退市风险警示
   - 停牌或即将停牌
   - 连续跌停 / 一字板跌停
   - 日均成交额 < 行业流动性阈值
   - 重大诉讼 / 监管立案 / 财务造假嫌疑
   - 大股东高比例质押（>70%）
3. 仓位管理：
   - 单票上限 max_single_position（由实例参数提供）
   - 总仓位上限 max_total_position（由实例参数提供）
   - 凯利公式：f* = (p×b - q) / b（p 胜率、b 赔率、q = 1-p）
   - 金字塔加仓 vs 倒金字塔减仓
4. 止损止盈：
   - 固定比例止损（默认 default_stop_loss，由实例参数提供）
   - ATR 动态止损
   - 关键支撑破位止损
   - 时间止损（超过预设周期未达预期）
5. 风险收益比（R/R）：
   - R/R = (目标价 - 入场价) / (入场价 - 止损价)
   - 正常交易 R/R ≥ 2；高不确定性场景 R/R ≥ 3

【工作原则（不可违背）】
1. 任何一条红线触发 → action 必须为 "reject"，recommended_position 必须为 0
2. 风险收益比 < 2 → action 不可为 "approve"；< 1 → 必须 reject
3. 仓位建议不得超过 max_single_position
4. 止损比例不得超过 default_stop_loss（除非显式说明理由并仍在可控范围）
5. 宁可错过机会，不可承担不对称风险

【输出纪律】
- 严格输出单一 JSON 对象，不得包裹解释性文字或 Markdown 代码块
- 缺失必要数据（价格/波动率/财务）时应倾向保守：action 默认为 "watch"，risk_level 不低于 "medium"
- 禁止编造具体价格与财务数据
- 评分必须锚定 rubric（注意：评分高 = 风险低）

【边界声明（不做什么）】
- 不替代技术分析员做形态判定
- 不替代基本面分析员做估值
- 不对标的做"值得买"的结论（只判断风险是否可控）
- 不做组合层面的相关性管理（单票岗位）
"""
    
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
            return self.build_agent_report(
                response=response,
                result=result,
                default_summary="风控分析完成",
            )
        
        self.logger.info("风控分析中...")
        
        # 构建分析提示词
        prompt = self.build_analysis_prompt(context)
        
        # 调用 LLM
        response = self.chat(prompt)
        
        # 解析结果
        result = self.parse_structured_response(response)
        
        return self.build_agent_report(
            response=response,
            result=result,
            default_summary="风险评估完成",
            metadata={
                "risk_level": result.get("risk_level", "medium"),
                "recommended_position": result.get("recommended_position", 0),
                "stop_loss": result.get("stop_loss"),
                "take_profit": result.get("take_profit"),
                "risk_reward_ratio": result.get("risk_reward_ratio")
            }
        )
    
    def build_analysis_prompt(self, context: StockAnalysisContext) -> str:
        """构建风险评估提示词"""
        market = context.market_data or {}
        fundamental = context.fundamental_data or {}

        prompt = f"""=== 任务 ===
对股票 {context.stock_name}({context.stock_code}) 进行风险评估，输出结构化报告。
你的 action 字段对团队具有约束力：reject = 禁止买入；watch = 暂不参与；approve = 允许参与。

=== 实例约束参数（必须遵守） ===
- 单票仓位上限（max_single_position）：{self.max_single_position}%
- 总仓位上限（max_total_position）：{self.max_total_position}%
- 默认止损阈值（default_stop_loss）：{self.default_stop_loss}%
你给出的 recommended_position 不得超过 {self.max_single_position}。
你给出的 stop_loss_ratio 原则上不得超过 {self.default_stop_loss}（如需放大，必须在 analysis 中写明充分理由）。

=== 上下文 ===
市场数据: {market if market else "【缺失】"}
基本面数据: {fundamental if fundamental else "【缺失】"}

=== 分析框架（按序推理） ===
1. 红线核查（任一触发即 action = "reject"，recommended_position = 0）：
   - ST / *ST / 退市预警
   - 停牌或即将停牌
   - 连续跌停或一字板
   - 流动性枯竭（换手率 < 0.5% 或成交额异常低）
   - 大股东质押比例 > 70%
   - 审计非标 / 重大诉讼 / 监管立案 / 造假嫌疑
2. 系统性风险评估：宏观政策、行业周期、市场整体风险偏好
3. 非系统性风险评估：
   - 经营风险：业绩确定性、客户/供应商集中度
   - 财务风险：负债率、现金流、商誉
   - 治理风险：股权结构、管理层
4. 流动性与波动率风险：
   - 日均成交额、换手率
   - 波动率水平（低 < 2% / 中 2–4% / 高 > 4% / 极端 > 6%）
5. 估值风险：当前估值分位、泡沫风险
6. 仓位建议（必须量化计算）：
   - 基础仓位按风险等级映射：low → 上限；medium → 上限的 60–80%；high → 上限的 20–40%；critical → 0
   - 最终 recommended_position = min(映射值, max_single_position)
7. 止损止盈（必须给出具体价位）：
   - 若输入含当前价 P：stop_loss = P × (1 - stop_loss_ratio/100)，take_profit 根据 R/R 推算
   - 若未知当前价：以 null 填写并在 data_quality.missing 标注
   - 必须满足 stop_loss_ratio ≤ default_stop_loss 或在 analysis 说明理由
8. 风险收益比：
   - R/R = (take_profit - 当前价) / (当前价 - stop_loss)
   - R/R < 1 → action = "reject"
   - 1 ≤ R/R < 2 → action 至多为 "watch"
   - R/R ≥ 2 → action 可为 "approve"（若无红线）

=== 评分 Rubric（0–10，分数越高风险越低，越适合参与） ===
- 0–2：red line 触发 或 critical 级别风险
- 3–4：多项显著风险并存，不建议参与
- 5–6：中等风险，需谨慎小仓位
- 7–8：风险整体可控，可按建议仓位参与
- 9–10：风险极低（流动性充沛、财务稳健、无红线、估值合理）

=== risk_level 量化对齐 ===
- low：无红线 + 波动率 < 2% + 财务稳健 + R/R ≥ 3
- medium：无红线 + 波动率 2–4% + 无重大隐患
- high：存在 1 项显著风险（波动率 > 4% / 财务承压 / 流动性偏弱）
- critical：触发任一红线 或 波动率 > 6% + 重大不确定性

=== 置信度给分规则 ===
- 同时缺失价格与财务数据：confidence ≤ 0.4
- 只有价格无财务：confidence ≤ 0.6
- 价格 + 财务 + 流动性全备：confidence 可达 0.9
- 绝对不可 > 0.95

=== 输出协议（严格 JSON，单对象，无任何额外文本） ===
{{
  "score": 0-10 评分（高分 = 低风险）,
  "confidence": 0-1 置信度,
  "summary": "一句话风险判断（≤40 字）",
  "analysis": "结构化详细分析，按上述 8 步展开，必须显式说明是否触发红线",
  "risks": ["风险点1", "风险点2"],
  "opportunities": ["风控视角的正向因子1", "风控视角的正向因子2"],
  "risk_level": "low" | "medium" | "high" | "critical",
  "recommended_position": 0-{self.max_single_position} 的数值,
  "stop_loss": 建议止损价（数值）或 null,
  "stop_loss_ratio": 止损比例百分数（数值）或 null,
  "take_profit": 建议止盈价（数值）或 null,
  "take_profit_ratio": 止盈比例百分数（数值）或 null,
  "risk_reward_ratio": 风险收益比（数值）或 null,
  "action": "approve" | "reject" | "watch",
  "redlines_triggered": ["触发的红线（若无填空数组）"],
  "volatility_level": "low" | "medium" | "high" | "extreme" | "unknown",
  "liquidity_level": "充足" | "一般" | "偏弱" | "枯竭" | "未知",
  "reasoning_steps": ["第1步结论", "第2步结论", "第3步结论", "第4步结论", "第5步结论", "第6步结论", "第7步结论", "第8步结论"],
  "evidence": ["引用自输入数据的关键风险证据"],
  "data_quality": {{"completeness": "high" | "medium" | "low", "missing": ["缺失字段"]}},
  "confidence_rationale": "置信度给分依据"
}}
"""
        return prompt
    
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
