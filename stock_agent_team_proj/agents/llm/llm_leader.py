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
    
    DEFAULT_SYSTEM_PROMPT = """【身份定位】
你是多智能体投研团队的"决策队长"（Chief Decision Officer），负责主持讨论、消解分歧、综合各专业 Agent（技术/基本面/情报/风控）的产出，并对最终投资建议负全部责任。你不是分析员的替代品，而是基于他们报告的最终仲裁者。

【核心能力】
1. 多视角综合：对齐不同 Agent 在同一标的上的判断，识别共识与分歧
2. 加权推理：按各 Agent 的置信度与信号强度动态加权，而非机械平均
3. 冲突消解：依据时间周期、市场环境、风险-收益比决定采信哪一方
4. 情景决策：对牛市/熊市/震荡市适配不同的仓位与节奏
5. 事后纠偏：对历史决策具有自我审视与修正能力

【工作原则】
1. 风控一票否决：若风控 Agent 的 action 为 reject，或识别出 ST/停牌/退市/流动性枯竭等红线，禁止输出 decision = "buy"
2. 仓位上限约束：position_ratio 不得超过风控 Agent 建议的 recommended_position
3. 周期匹配：技术面与基本面冲突时，按用户持有周期取舍——短线以技术为主、长线以基本面为主
4. 证据优先：每一条结论必须能追溯到至少一条 Agent 报告或原始数据
5. 不确定性诚实：信号不足或分歧严重时，优先输出 decision = "watch"，不强行下注

【输出纪律】
- 严格输出单一 JSON 对象，不得包裹额外解释文字或 Markdown 代码块
- 数据缺失时应显式在 data_quality.missing 中声明，并降低 confidence
- 禁止编造价格、财务数字、资金流向等任何未在输入中出现的具体数值
- 评分必须锚定 rubric，position_ratio/target_price/stop_loss 必须给出可执行数字或显式为 null

【边界声明（不做什么）】
- 不替代专业 Agent 的底层分析：技术形态、财务数据、资金流向的细节推演不在本岗位范围
- 不做跨标的组合配置建议
- 不提供税务、法律、合规类建议
- 不对未在输入上下文中出现的信息进行"推测性补全"
"""
    
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
            return self.build_agent_report(
                response=response,
                result=result,
                default_summary="分析完成",
                metadata={
                    "decision": result.get("decision", "watch"),
                    "action": result.get("action", "观望"),
                    "target_price": result.get("target_price"),
                    "stop_loss": result.get("stop_loss"),
                    "position_ratio": result.get("position_ratio", 0),
                }
            )
        
        self.logger.info("Leader分析中...")
        
        # 1. 整合各 Worker 的分析结果（完整报告，而非仅 summary）
        if not self.worker_reports:
            return self._direct_analyze(context)

        combined_analysis = self._format_worker_reports(self.worker_reports)

        # 2. 构建综合分析提示词
        prompt = self._build_final_decision_prompt(context, combined_analysis)
        
        # 4. 调用 LLM
        response = self.chat(prompt)
        
        # 5. 解析结果
        result = self.parse_structured_response(response)
        
        report = self.build_agent_report(
            response=response,
            result=result,
            default_summary="综合分析完成",
            metadata={
                "decision": result.get("decision", "watch"),
                "action": result.get("action", "观望"),
                "worker_count": len(self.worker_reports),
                "target_price": result.get("target_price"),
                "stop_loss": result.get("stop_loss"),
                "position_ratio": result.get("position_ratio", 0),
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
        prompt = self._build_direct_analysis_prompt(context)
        response = self.chat(prompt)
        result = self.parse_structured_response(response)

        return self.build_agent_report(
            response=response,
            result=result,
            default_summary="分析完成",
            metadata={
                "decision": result.get("decision", "watch"),
                "action": result.get("action", "观望"),
                "target_price": result.get("target_price"),
                "stop_loss": result.get("stop_loss"),
                "position_ratio": result.get("position_ratio", 0)
            }
        )

    def _build_direct_analysis_prompt(self, context: StockAnalysisContext) -> str:
        """无 Worker 报告时的直接分析提示词（置信度需自降）"""
        return f"""=== 任务 ===
作为投资决策队长，现阶段尚未收到各专业 Agent 的独立报告，请基于以下上下文直接给出审慎的初步决策。
注意：独立决策缺少多视角交叉验证，confidence 不得高于 0.6。

=== 上下文 ===
{context.to_prompt_context()}

=== 分析框架（按序推理） ===
1. 数据盘点：列出上下文中可用的数据字段与缺失项；缺失严重时应倾向 watch
2. 趋势定位：判断当前处于上升/下降/震荡，以及在该趋势中的位置
3. 估值与情绪：简评价格是否处于合理区间、市场情绪偏向
4. 风险排查：识别明显的红线（ST/停牌/业绩爆雷/监管风险）
5. 决策合成：在信号不足以支撑 buy/sell 时一律输出 watch

=== 评分 Rubric（0–10） ===
- 0–3：明确利空/红线触发，建议回避
- 4–5：信号矛盾或信息不足，倾向观望
- 6–7：结构向好但缺乏多维度确认，小仓位试探
- 8–9：多维度共振（在独立决策场景下不建议使用）
- 10：极端强势，需有充分证据支撑（独立决策禁止使用）

=== 输出协议（严格 JSON，单对象，无额外文本） ===
{{
  "score": 0-10 的数值（遵循 rubric）,
  "confidence": 0-0.6 的数值（独立决策上限）,
  "summary": "一句话决策结论（≤40 字）",
  "analysis": "结构化详细分析，按上述 5 步展开",
  "risks": ["风险点1", "风险点2"],
  "opportunities": ["机会点1", "机会点2"],
  "decision": "buy" | "sell" | "watch" | "hold",
  "action": "具体可执行的操作描述",
  "target_price": 目标价格数字 或 null,
  "stop_loss": 止损价格数字 或 null,
  "position_ratio": 0-100 的数字（建议仓位百分比，独立决策建议 ≤20）,
  "reasoning_steps": ["第1步结论", "第2步结论", "第3步结论", "第4步结论", "第5步结论"],
  "evidence": ["引用自上下文的关键数据点"],
  "data_quality": {{"completeness": "high" | "medium" | "low", "missing": ["缺失的关键数据"]}},
  "confidence_rationale": "本次置信度给分的依据"
}}
"""
    
    def _format_worker_reports(
        self,
        worker_reports: Dict[str, AgentReport]
    ) -> str:
        """将各 Worker 的完整报告格式化为结构化上下文块"""
        role_labels = {
            "technical": "技术面",
            "fundamental": "基本面",
            "intelligence": "资金面/情报",
            "risk": "风险控制",
        }

        blocks: List[str] = []
        for role, report in worker_reports.items():
            label = role_labels.get(role, role)
            risks = "；".join(report.risks) if report.risks else "（无）"
            opportunities = "；".join(report.opportunities) if report.opportunities else "（无）"

            metadata_str = ""
            if report.metadata:
                md_items = [f"{k}={v}" for k, v in report.metadata.items() if v not in (None, "", {}, [])]
                if md_items:
                    metadata_str = "\n  - 关键指标：" + "；".join(md_items)

            block = (
                f"【{label} / {report.agent_name}】\n"
                f"  - 评分：{report.score} / 10，置信度：{report.confidence}\n"
                f"  - 结论：{report.summary}\n"
                f"  - 分析摘要：{report.analysis[:400]}\n"
                f"  - 风险：{risks}\n"
                f"  - 机会：{opportunities}"
                f"{metadata_str}"
            )
            blocks.append(block)

        return "\n\n".join(blocks)

    def _build_final_decision_prompt(
        self,
        context: StockAnalysisContext,
        combined_analysis: str
    ) -> str:
        """构建最终决策提示词（按置信度加权 + 风控 veto + 周期匹配）"""
        return f"""=== 任务 ===
作为投资决策队长，请基于以下各专业 Agent 的完整报告，对股票 {context.stock_name}({context.stock_code}) 做出最终投资决策。
你的决策对执行层直接可用，必须明确、可执行、可追溯。

=== 标的基础上下文 ===
股票：{context.stock_name}（{context.stock_code}）
用户请求：{context.user_request or "综合决策"}

=== 各专业 Agent 报告 ===
{combined_analysis}

=== 决策协议（必须遵守，违反任一条视为无效输出） ===
1. 风控一票否决：
   - 若 risk Agent 的 action 为 "reject"，decision 不得为 "buy"，且 position_ratio 必须为 0
   - 若 risk Agent 的 risk_level 为 "critical"，decision 至多为 "watch"
2. 仓位上限约束：
   - 最终 position_ratio = min(你的建议仓位, risk Agent 的 recommended_position)
   - 若风控未提供 recommended_position，position_ratio 上限为 30
3. 加权综合规则：
   - 各 Agent 的初始权重为 25%，按其 confidence 动态调整：adj_weight_i ∝ base_weight_i × confidence_i，再归一化
   - 在输出的 analysis 中显式写出最终权重
4. 周期匹配（冲突消解）：
   - 技术面与基本面给出相反信号时：
     · 用户请求偏短线（日内/周内）→ 技术面优先
     · 用户请求偏长线或未明确 → 基本面优先
     · 若情报面与一方共振，该方优先级提升
5. 诚实阈值：
   - 各 Agent 加权综合分在 4–6 之间且分歧显著（最大分-最小分 > 3），强制 decision = "watch"
   - 数据关键字段缺失（价格、财务、资金流任一为空）时，confidence 上限为 0.7
6. 价格三元组一致性：
   - 若 decision = "buy"：target_price > 当前价 > stop_loss；若 decision = "sell"：反之
   - 目标价与止损必须可从技术 Agent 的支撑/压力位或基本面合理估值中溯源，禁止拍脑袋

=== 评分 Rubric（0–10，针对"作为投资机会"的综合吸引力） ===
- 0–3：风控 reject 或多维利空共振，回避
- 4–5：信号矛盾或置信度普遍偏低，观望
- 6–7：主导逻辑清晰但缺少一类确认，小仓位参与
- 8–9：技术/基本面/资金面至少两维共振且风控不反对，标准仓位
- 10：三维共振 + 低估值 + 风险收益比 ≥ 3，罕见机会

=== 分析框架（按序推理，写入 reasoning_steps） ===
1. 汇总：列出四路 Agent 的评分、置信度、动态权重与核心结论
2. 共识与分歧：指出共识项与关键分歧点
3. 冲突消解：说明按哪条规则（周期匹配/风控优先/证据强度）取舍
4. 风险核查：逐条检查风控红线是否触发
5. 决策合成：给出 decision/position/价格三元组，并写明为何选择此动作

=== 输出协议（严格 JSON，单对象，无任何额外文本） ===
{{
  "score": 综合评分 0-10,
  "confidence": 置信度 0-1,
  "summary": "一句话最终决策（≤40 字）",
  "analysis": "结构化决策理由，必须包含：各 Agent 最终加权、分歧消解路径、风险复核结果",
  "risks": ["主要风险1", "主要风险2"],
  "opportunities": ["主要机会1", "主要机会2"],
  "decision": "buy" | "sell" | "watch" | "hold",
  "action": "具体可执行操作（含买入区间/卖出时机）",
  "target_price": 目标价格数字 或 null,
  "stop_loss": 止损价格数字 或 null,
  "position_ratio": 建议仓位 0-100,
  "agent_weights": {{"technical": 0-1, "fundamental": 0-1, "intelligence": 0-1, "risk": 0-1}},
  "veto_triggered": true 或 false,
  "conflict_resolution": "描述如何消解分歧（若无分歧填 '无分歧'）",
  "reasoning_steps": ["第1步结论", "第2步结论", "第3步结论", "第4步结论", "第5步结论"],
  "evidence": ["引用自 Agent 报告或上下文的关键证据"],
  "data_quality": {{"completeness": "high" | "medium" | "low", "missing": ["缺失字段"]}},
  "confidence_rationale": "置信度给分依据"
}}
"""
    
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
