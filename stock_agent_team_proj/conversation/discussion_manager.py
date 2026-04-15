"""
多轮讨论管理器 - 实现 Agent 团队的多轮讨论流程
"""
import asyncio
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from .message import (
    Message, AgentReport, DiscussionRound, 
    DiscussionHistory, DiscussionResult, AgentRole
)
from .prompts import (
    LEADER_START_DISCUSSION, LEADER_SUMMARY, LEADER_FINAL_SUMMARY,
    AGENT_RESPONSE_TEMPLATE, AGENT_INITIAL_REPORT,
    format_agent_reports, format_discussion_context, format_other_views,
    ROUND_INSTRUCTIONS
)


class BaseLLMAgent:
    """基础 LLM Agent 接口"""
    
    def __init__(self, name: str, role: AgentRole, role_description: str):
        self.name = name
        self.role = role
        self.role_description = role_description
    
    async def analyze(self, prompt: str) -> str:
        """执行分析"""
        raise NotImplementedError
    
    def generate_report(self, stock_info: dict, data: dict) -> AgentReport:
        """生成分析报告"""
        raise NotImplementedError


class DiscussionManager:
    """
    多轮讨论管理器
    
    实现 3 轮讨论机制：
    - Round 1: 各 Agent 独立分析
    - Round 2: Leader 组织讨论
    - Round 3: 达成共识，输出最终决策
    """
    
    def __init__(
        self, 
        leader: BaseLLMAgent, 
        agents: List[BaseLLMAgent], 
        max_rounds: int = 3,
        llm_callable: Optional[Callable] = None  # LLM 调用接口
    ):
        self.leader = leader
        self.agents = agents
        self.max_rounds = max_rounds
        self.llm_callable = llm_callable
        self.history: Optional[DiscussionHistory] = None
        self._executor = ThreadPoolExecutor(max_workers=4)
    
    async def start_discussion(
        self, 
        stock_code: str, 
        stock_name: str,
        data: dict
    ) -> DiscussionResult:
        """
        启动讨论流程
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            data: 包含分析数据的字典
            
        Returns:
            DiscussionResult: 讨论结果
        """
        # 初始化讨论历史
        self.history = DiscussionHistory(
            stock_code=stock_code,
            stock_name=stock_name
        )
        
        # 第一轮：各 Agent 独立分析
        round1 = await self._round1_individual_analysis(stock_code, stock_name, data)
        self.history.add_round(round1)
        
        # 第二轮：Leader 组织讨论
        round2 = await self._round2_group_discussion(round1)
        self.history.add_round(round2)
        
        # 第三轮：达成共识
        round3 = await self._round3_consensus(round2)
        self.history.add_round(round3)
        
        # 生成最终决策
        return self._generate_final_result(round3)
    
    async def _round1_individual_analysis(
        self, 
        stock_code: str, 
        stock_name: str,
        data: dict
    ) -> DiscussionRound:
        """
        第一轮：各 Agent 独立分析
        
        每个 Agent 基于自己的专业领域进行独立分析，不与其他 Agent 交流
        """
        round_obj = DiscussionRound(
            round_number=1,
            round_type="independent",
            summary="各 Agent 完成独立分析"
        )
        
        # 并行执行所有 Agent 的分析
        tasks = []
        for agent in self.agents:
            task = self._agent_analyze(agent, stock_code, stock_name, data)
            tasks.append(task)
        
        reports = await asyncio.gather(*tasks)
        
        for report in reports:
            round_obj.add_report(report)
            # 添加系统消息记录
            round_obj.add_message(Message(
                role="assistant",
                content=f"{report.agent_name} 完成独立分析：评分 {report.score}，置信度 {report.confidence:.0%}",
                agent_name=report.agent_name,
                agent_role=report.agent_role
            ))
        
        round_obj.summary = self._summarize_round1(round_obj)
        return round_obj
    
    async def _agent_analyze(
        self, 
        agent: BaseLLMAgent, 
        stock_code: str, 
        stock_name: str,
        data: dict
    ) -> AgentReport:
        """单个 Agent 执行分析"""
        # 准备提示词
        prompt = self._prepare_initial_prompt(agent, stock_code, stock_name, data)
        
        if self.llm_callable:
            # 使用提供的 LLM 调用接口
            response = await self.llm_callable(prompt)
        else:
            # 默认实现：调用 agent 的 analyze 方法
            response = await agent.analyze(prompt)
        
        # 解析响应生成报告
        report = self._parse_report(agent, response)
        return report
    
    def _prepare_initial_prompt(
        self, 
        agent: BaseLLMAgent, 
        stock_code: str, 
        stock_name: str,
        data: dict
    ) -> str:
        """准备初始分析提示词"""
        prompt = AGENT_INITIAL_REPORT.format(
            name=agent.name,
            role_description=agent.role_description,
            stock_name=stock_name,
            stock_code=stock_code,
            current_price=data.get('current_price', 'N/A'),
            market_context=data.get('market_context', '震荡市'),
            available_data=self._format_data_for_agent(agent.role, data)
        )
        return prompt
    
    def _format_data_for_agent(self, role: AgentRole, data: dict) -> str:
        """根据 Agent 角色格式化数据"""
        if role == AgentRole.TECHNICAL:
            return f"技术指标数据:\n{data.get('technical', {})}"
        elif role == AgentRole.INTELLIGENCE:
            return f"市场情报:\n{data.get('intelligence', {})}"
        elif role == AgentRole.RISK:
            return f"风险指标:\n{data.get('risk', {})}"
        elif role == AgentRole.FUNDAMENTAL:
            return f"基本面数据:\n{data.get('fundamental', {})}"
        return str(data)
    
    async def _round2_group_discussion(self, round1: DiscussionRound) -> DiscussionRound:
        """
        第二轮：组织讨论
        
        Leader 发起讨论，各 Agent 可以质疑和辩论
        """
        round_obj = DiscussionRound(
            round_number=2,
            round_type="discussion",
            summary="讨论进行中"
        )
        
        # Leader 发起讨论
        leader_prompt = self._prepare_leader_discussion_prompt(round1)
        leader_intro = await self._call_leader(leader_prompt)
        
        round_obj.add_message(Message(
            role="assistant",
            content=leader_intro,
            agent_name=self.leader.name,
            agent_role=AgentRole.LEADER
        ))
        
        # 收集各 Agent 对讨论的回应
        reports_dict = {r.agent_role: r for r in round1.agent_reports}
        
        # 进行多轮问答（最多 2 轮）
        current_messages = [
            {"agent_name": self.leader.name, "content": leader_intro}
        ]
        
        for q_round in range(2):
            # 各 Agent 依次回应
            for agent in self.agents:
                # 检查是否有针对此 Agent 的问题
                relevant_question = self._extract_relevant_question(
                    agent.role, current_messages
                )
                
                if relevant_question:
                    response = await self._agent_discuss(
                        agent, current_messages, reports_dict[agent.role]
                    )
                else:
                    response = await self._agent_discuss(
                        agent, current_messages, reports_dict[agent.role],
                        free_comment=True
                    )
                
                current_messages.append({
                    "agent_name": agent.name,
                    "content": response
                })
                
                round_obj.add_message(Message(
                    role="assistant",
                    content=response,
                    agent_name=agent.name,
                    agent_role=agent.role
                ))
        
        # Leader 总结讨论
        summary_prompt = self._prepare_discussion_summary_prompt(current_messages)
        leader_summary = await self._call_leader(summary_prompt)
        
        round_obj.add_message(Message(
            role="assistant",
            content=leader_summary,
            agent_name=self.leader.name,
            agent_role=AgentRole.LEADER
        ))
        
        round_obj.summary = "第二轮讨论完成，各方观点已充分表达"
        return round_obj
    
    async def _round3_consensus(self, round2: DiscussionRound) -> DiscussionRound:
        """
        第三轮：达成共识
        
        各 Agent 根据讨论调整评分，给出最终建议
        """
        round_obj = DiscussionRound(
            round_number=3,
            round_type="consensus",
            summary="共识达成中"
        )
        
        # Leader 发起最终评分请求
        consensus_prompt = LEADER_SUMMARY
        leader_request = await self._call_leader(consensus_prompt)
        
        round_obj.add_message(Message(
            role="assistant",
            content=leader_request,
            agent_name=self.leader.name,
            agent_role=AgentRole.LEADER
        ))
        
        # 各 Agent 给出最终报告
        tasks = []
        for agent in self.agents:
            task = self._agent_final_report(
                agent, 
                round2.agent_reports,
                [m.content for m in round2.messages if m.agent_name == agent.name]
            )
            tasks.append(task)
        
        final_reports = await asyncio.gather(*tasks)
        
        for report in final_reports:
            round_obj.add_report(report)
        
        # Leader 给出最终决策
        final_decision_prompt = self._prepare_final_decision_prompt(round_obj.agent_reports)
        leader_decision = await self._call_leader(final_decision_prompt)
        
        round_obj.add_message(Message(
            role="assistant",
            content=leader_decision,
            agent_name=self.leader.name,
            agent_role=AgentRole.LEADER
        ))
        
        round_obj.summary = leader_decision
        return round_obj
    
    # ==================== 辅助方法 ====================
    
    async def _call_leader(self, prompt: str) -> str:
        """调用 Leader Agent"""
        if self.llm_callable:
            return await self.llm_callable(prompt)
        return await self.leader.analyze(prompt)
    
    async def _agent_discuss(
        self, 
        agent: BaseLLMAgent,
        context: List[Dict],
        original_report: AgentReport,
        free_comment: bool = False
    ) -> str:
        """Agent 参与讨论"""
        if free_comment:
            prompt = f"""你是 {agent.name}（{agent.role_description}）。

当前讨论已进行一轮，请分享你的补充观点或对讨论的总体看法。

你的原始分析：{original_report.analysis[:100]}...

请发表补充意见（100字以内）：
"""
        else:
            prompt = AGENT_RESPONSE_TEMPLATE.format(
                name=agent.name,
                role_description=agent.role_description,
                discussion_context=format_discussion_context(context),
                other_views=format_other_views(agent.name, [
                    {"agent_name": r.agent_name, "analysis": r.analysis}
                    for r in self.history.rounds[0].agent_reports
                    if r.agent_name != agent.name
                ])
            )
        
        if self.llm_callable:
            return await self.llm_callable(prompt)
        return await agent.analyze(prompt)
    
    async def _agent_final_report(
        self,
        agent: BaseLLMAgent,
        previous_reports: List[AgentReport],
        agent_discussion_content: List[str]
    ) -> AgentReport:
        """生成最终报告"""
        context = f"""
你的原始评分：{previous_reports[[r.agent_name for r in previous_reports].index(agent.name)].score}
你的讨论发言：{''.join(agent_discussion_content)}

请给出最终评分、置信度和简短理由。
"""
        
        prompt = f"""你是 {agent.name}（{agent.role_description}）。

{LEADER_SUMMARY}

{context}

请给出最终报告：
"""
        
        if self.llm_callable:
            response = await self.llm_callable(prompt)
        else:
            response = await agent.analyze(prompt)
        
        return self._parse_report(agent, response)
    
    def _prepare_leader_discussion_prompt(self, round1: DiscussionRound) -> str:
        """准备 Leader 发起讨论的提示词"""
        reports = [r.to_dict() for r in round1.agent_reports]
        return LEADER_START_DISCUSSION.format(
            stock_name=self.history.stock_name,
            stock_code=self.history.stock_code,
            agent_reports=format_agent_reports(reports)
        )
    
    def _prepare_discussion_summary_prompt(self, messages: List[Dict]) -> str:
        """准备讨论总结提示词"""
        context = "\n\n".join([
            f"**{m['agent_name']}**：{m['content']}"
            for m in messages[:8]  # 取前8条消息
        ])
        return f"""基于以上讨论，请总结：
1. 各方观点的主要分歧
2. 已达成共识的内容
3. 需要进一步关注的问题

讨论内容：
{context}
"""
    
    def _prepare_final_decision_prompt(self, reports: List[AgentReport]) -> str:
        """准备最终决策提示词"""
        reports_dict = [r.to_dict() for r in reports]
        return LEADER_FINAL_SUMMARY + "\n\n最终报告汇总：\n" + format_agent_reports(reports_dict)
    
    def _extract_relevant_question(
        self, 
        role: AgentRole, 
        messages: List[Dict]
    ) -> Optional[str]:
        """提取与特定角色相关的问题"""
        # 简化的实现，实际可能需要更复杂的逻辑
        for msg in reversed(messages):
            content = msg.get('content', '').lower()
            # 检查是否提到了该角色
            if role.value in content or role.name.lower() in content:
                return msg.get('content')
        return None
    
    def _parse_report(self, agent: BaseLLMAgent, response: str) -> AgentReport:
        """解析 LLM 响应生成报告"""
        # 简化的解析逻辑
        # 实际可能需要更复杂的解析或使用结构化输出
        score = 5.0
        confidence = 0.5
        
        # 尝试提取评分
        import re
        score_match = re.search(r'评分[：:]?\s*(\d+\.?\d*)', response)
        if score_match:
            score = float(score_match.group(1))
        
        confidence_match = re.search(r'置信[度:]?\s*(\d+\.?\d*)', response)
        if confidence_match:
            confidence = float(confidence_match.group(1))
        
        return AgentReport(
            agent_name=agent.name,
            agent_role=agent.role,
            score=score,
            confidence=confidence,
            analysis=response
        )
    
    def _summarize_round1(self, round_obj: DiscussionRound) -> str:
        """总结第一轮分析"""
        scores = [r.score for r in round_obj.agent_reports]
        avg_score = sum(scores) / len(scores) if scores else 0
        return f"独立分析完成，平均评分 {avg_score:.1f}，共 {len(round_obj.agent_reports)} 位分析师参与"
    
    def _generate_final_result(self, round3: DiscussionRound) -> DiscussionResult:
        """生成最终讨论结果"""
        reports = round3.agent_reports
        avg_score = sum(r.score for r in reports) / len(reports) if reports else 0
        avg_confidence = sum(r.confidence for r in reports) / len(reports) if reports else 0
        
        # 解析最终决策
        final_summary = round3.summary
        
        # 提取推荐操作
        import re
        recommendation = "持有"
        position = "50%"
        
        op_match = re.search(r'操作[:：]\s*(\w+)', final_summary)
        if op_match:
            recommendation = op_match.group(1)
        
        pos_match = re.search(r'仓位[:：]\s*(\d+%)', final_summary)
        if pos_match:
            position = pos_match.group(1)
        
        return DiscussionResult(
            stock_code=self.history.stock_code,
            stock_name=self.history.stock_name,
            final_reports=reports,
            final_summary=final_summary,
            discussion_history=self.history,
            recommendation=recommendation,
            overall_score=avg_score,
            confidence=avg_confidence
        )
    
    # ==================== 同步版本接口 ====================
    
    def start_discussion_sync(
        self, 
        stock_code: str, 
        stock_name: str,
        data: dict
    ) -> DiscussionResult:
        """同步版本的启动讨论"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.start_discussion(stock_code, stock_name, data)
            )
        finally:
            loop.close()


# ==================== 示例 Agent 实现 ====================

class SimpleLLMAgent(BaseLLMAgent):
    """简单的 LLM Agent 实现（用于测试）"""
    
    def __init__(self, name: str, role: AgentRole, role_description: str):
        super().__init__(name, role, role_description)
    
    async def analyze(self, prompt: str) -> str:
        """简单的分析实现"""
        # 实际使用时应该调用真实的 LLM
        return f"[{self.name}] 基于 {self.role.value} 分析，已完成评估"
    
    def generate_report(self, stock_info: dict, data: dict) -> AgentReport:
        """生成报告"""
        return AgentReport(
            agent_name=self.name,
            agent_role=self.role,
            score=5.0,
            confidence=0.5,
            analysis="分析完成"
        )
