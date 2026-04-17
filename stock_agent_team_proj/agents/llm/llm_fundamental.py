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
    
    DEFAULT_SYSTEM_PROMPT = """【身份定位】
你是投研团队中的"基本面分析员"（Fundamental Analyst），秉持价值投资与质量优先理念，负责对标的的企业质地、盈利质量、估值水平与成长性给出专业判断。服务于决策队长，不直接下达买卖指令。

【核心能力】
1. 财务三表分析：
   - 利润表：收入结构、毛利率、净利率、费用率、ROE/ROA 杜邦分解
   - 资产负债表：资产质量、负债结构、资产负债率、有息负债率、商誉占比、存货与应收质量
   - 现金流量表：经营性/投资性/融资性现金流、自由现金流、经营现金流/净利润比
2. 估值体系（按行业适配）：
   - 金融/周期：PB 为主，结合 ROE
   - 成熟/消费/公用事业：PE 为主，结合股息率
   - 成长/科技：PS、PEG、远期 PE
   - 重资产/资源：EV/EBITDA、NAV
3. 质量因子：
   - 护城河：品牌、网络效应、成本优势、切换成本、特许经营
   - 治理：股权结构、管理层稳定性、关联交易、分红政策
4. 成长性评估：驱动因素、市占率变化、渗透率、新业务贡献
5. 价值陷阱识别：低估值 + 基本面恶化的组合

【工作原则】
1. 现金为王：净利润与经营性现金流背离（OCF/净利润 < 0.8 持续多年）需在风险项中标注
2. 行业匹配：估值方法必须匹配行业属性，错用估值方法视为重大缺陷
3. 历史分位对比：PE/PB 必须与 3–5 年历史分位和行业均值对比后再给结论
4. 红线优先：触发红线清单的标的，无论其他指标如何，评分不得高于 4
5. 长期视角：拒绝为短期业绩波动过度调整判断

【红线清单（任一触发即评分 ≤ 4 并在 risks 中注明）】
- 审计意见为"非标准无保留"或以下
- 商誉 / 净资产 > 50%
- 控股股东股权质押比例 > 70%
- 连续两年经营性现金流为负
- 存在重大诉讼、监管立案、财务造假嫌疑

【输出纪律】
- 严格输出单一 JSON 对象，不得包裹解释性文字或 Markdown 代码块
- 缺少财务数据时 confidence 上限为 0.4，并在 data_quality.missing 注明
- 禁止编造财务数字与比率；所有引用必须来自输入的 fundamental_data
- 评分必须锚定 rubric

【边界声明（不做什么）】
- 不做技术面 K 线判断
- 不做主力资金/北向资金追踪
- 不做短线交易建议
- 不替代决策队长给出最终 buy/sell 指令
"""
    
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
            return self.build_agent_report(
                response=response,
                result=result,
                default_summary="基本面分析完成",
            )
        
        self.logger.info("基本面分析中...")
        
        # 构建分析提示词
        prompt = self.build_analysis_prompt(context)
        
        # 调用 LLM
        response = self.chat(prompt)
        
        # 解析结果
        result = self.parse_structured_response(response)
        
        return self.build_agent_report(
            response=response,
            result=result,
            default_summary="基本面分析完成",
            metadata={
                "valuation": result.get("valuation", {}),
                "financial_health": result.get("financial_health", "unknown"),
                "growth_potential": result.get("growth_potential", "unknown")
            }
        )
    
    def build_analysis_prompt(self, context: StockAnalysisContext) -> str:
        """构建基本面分析提示词"""
        fundamental = context.fundamental_data or {}
        market = context.market_data or {}

        prompt = f"""=== 任务 ===
对股票 {context.stock_name}({context.stock_code}) 进行基本面分析，输出结构化报告。
注意：本岗位只对企业质地、盈利质量、估值和成长性负责，不涉及技术形态与资金流向结论。

=== 上下文 ===
基本面数据: {fundamental if fundamental else "【缺失】"}
市场行情参考: {market if market else "【缺失】"}

=== 分析框架（按序推理） ===
1. 企业画像：所属行业、商业模式、主营结构、行业地位
2. 盈利能力：
   - 毛利率/净利率近 3 年趋势
   - ROE/ROA（杜邦分解：净利率 × 周转率 × 权益乘数）
   - 费用率是否可控
3. 成长性：
   - 营收与归母净利增速（近 3–5 年 CAGR）
   - 增长驱动（量、价、品类扩张、新业务）
   - 是否有明显增速下台阶
4. 财务质量（红线自检）：
   - 经营性现金流 / 净利润 是否 ≥ 0.8
   - 资产负债率、有息负债率是否在行业健康范围
   - 商誉 / 净资产 是否 ≤ 50%
   - 应收/存货周转是否异常变坏
   - 审计意见是否为标准无保留
5. 估值判定（行业适配）：
   - 根据行业属性选择主估值方法（金融→PB、成长→PS/PEG、消费→PE、资源→EV/EBITDA）
   - 与自身 3–5 年历史分位、行业均值比较
   - 给出估值级别：低估/合理/高估
6. 护城河与治理：品牌、规模、技术、成本、切换成本、股东结构、管理层
7. 价值陷阱筛查：是否出现"低 PE + 利润下滑 + 现金流恶化"组合
8. 综合判定：按 rubric 评分

=== 评分 Rubric（0–10，针对"企业内在价值吸引力"） ===
- 0–3：红线触发 / 价值陷阱嫌疑 / 盈利持续恶化
- 4–5：质地平庸或行业逆风，无突出亮点
- 6–7：质地良好但估值偏高 或 估值合理但成长一般
- 8–9：优质公司 + 合理偏低估值 + 稳健现金流
- 10：深度低估的高质量公司，罕见（需强证据）

=== 置信度给分规则 ===
- 缺乏财务核心数据（营收/利润/现金流）：confidence ≤ 0.4
- 只有最近一期数据无历史对比：confidence ≤ 0.6
- 具备 3 年财务数据 + 行业对比：confidence 可达 0.85
- 绝对不可 > 0.95

=== 输出协议（严格 JSON，单对象，无任何额外文本） ===
{{
  "score": 0-10 评分,
  "confidence": 0-1 置信度,
  "summary": "一句话基本面判断（≤40 字）",
  "analysis": "结构化详细分析，按上述 8 步展开",
  "risks": ["基本面风险点1", "基本面风险点2"],
  "opportunities": ["基本面机会点1", "基本面机会点2"],
  "valuation": {{
    "pe": 市盈率 或 null,
    "pb": 市净率 或 null,
    "ps": 市销率 或 null,
    "peg": 市盈增长比 或 null,
    "primary_method": "PE" | "PB" | "PS" | "PEG" | "EV/EBITDA" | "DCF",
    "historical_percentile": "近 3-5 年历史分位描述" 或 null,
    "industry_comparison": "相对行业描述" 或 null,
    "valuation_level": "低估" | "合理" | "高估"
  }},
  "financial_health": "优秀" | "良好" | "一般" | "较差",
  "growth_potential": "高成长" | "稳定成长" | "低速成长" | "衰退",
  "moat": "护城河简述（若无护城河明确写'无明显护城河'）",
  "profitability": {{"gross_margin_trend": "上升" | "下降" | "稳定", "roe": 数值 或 null}},
  "cashflow_quality": {{"ocf_to_net_income": 数值 或 null, "assessment": "优" | "良" | "一般" | "差"}},
  "redlines_triggered": ["触发的红线"],
  "value_trap_risk": "low" | "medium" | "high",
  "reasoning_steps": ["第1步结论", "第2步结论", "第3步结论", "第4步结论", "第5步结论", "第6步结论", "第7步结论", "第8步结论"],
  "evidence": ["引用自输入数据的关键财务值"],
  "data_quality": {{"completeness": "high" | "medium" | "low", "missing": ["缺失字段"]}},
  "confidence_rationale": "置信度给分依据"
}}
"""
        return prompt


__all__ = ['LLMFundamental']
