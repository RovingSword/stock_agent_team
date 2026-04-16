"""
多轮讨论管理器 - 实现 Agent 团队的多轮讨论流程
"""
import asyncio
import inspect
from typing import List, Optional, Dict, Any, Callable, Union
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

# 尝试导入实际的 LLM Agent 基类
try:
    from agents.llm.base_llm_agent import BaseLLMAgent as RealLLMAgent
    from agents.llm.models import StockAnalysisContext
    HAS_REAL_AGENT = True
except ImportError:
    HAS_REAL_AGENT = False
    RealLLMAgent = None
    StockAnalysisContext = None

# 类型别名，用于类型注解
BaseLLMAgent = RealLLMAgent if RealLLMAgent else object


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
        agent, 
        stock_code: str, 
        stock_name: str,
        data: dict
    ) -> AgentReport:
        """单个 Agent 执行分析（兼容同步/异步 Agent）"""
        # 准备提示词
        prompt = self._prepare_initial_prompt(agent, stock_code, stock_name, data)
        
        if self.llm_callable:
            # 使用提供的 LLM 调用接口
            response = await self.llm_callable(prompt)
            return self._parse_report(agent, response)
        
        # 检查 agent.analyze 方法
        analyze_method = getattr(agent, 'analyze', None)
        if analyze_method is None:
            raise ValueError(f"Agent {agent.name} 没有 analyze 方法")
        
        # 判断是异步方法还是同步方法
        is_async = inspect.iscoroutinefunction(analyze_method)
        
        if is_async:
            # 异步方法，直接 await
            result = await analyze_method(prompt)
        else:
            # 同步方法，用 run_in_executor 包装
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self._executor, lambda: analyze_method(prompt))
        
        # 根据返回类型处理
        if isinstance(result, AgentReport):
            # 直接返回 AgentReport 对象
            return result
        elif isinstance(result, str):
            # 字符串响应，需要解析
            return self._parse_report(agent, result)
        else:
            # 其他类型，尝试解析
            return self._parse_report(agent, str(result))
    
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
        # 创建支持字符串和枚举两种 key 的字典
        reports_dict = {}
        for r in round1.agent_reports:
            # 使用枚举作为 key
            reports_dict[r.agent_role] = r
            # 同时添加字符串版本的 key（兼容实际 Agent 的 role 属性）
            if hasattr(r.agent_role, 'value'):
                reports_dict[r.agent_role.value] = r
            else:
                reports_dict[str(r.agent_role)] = r
        
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
        """调用 Leader Agent（兼容同步/异步）"""
        if self.llm_callable:
            return await self.llm_callable(prompt)
        
        # 检查 leader 的 analyze 方法
        analyze_method = getattr(self.leader, 'analyze', None)
        if analyze_method is None:
            raise ValueError("Leader 没有 analyze 方法")
        
        # 判断是异步还是同步
        is_async = inspect.iscoroutinefunction(analyze_method)
        
        if is_async:
            result = await analyze_method(prompt)
        else:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor, 
                lambda: analyze_method(prompt)
            )
        
        # 如果返回的是 AgentReport，提取 analysis 字段
        if isinstance(result, AgentReport):
            return result.analysis
        return str(result)
    
    async def _agent_discuss(
        self, 
        agent,
        context: List[Dict],
        original_report: AgentReport,
        free_comment: bool = False
    ) -> str:
        """Agent 参与讨论（兼容同步/异步）"""
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
                    {"agent_name": r.agent_name, "analysis": r.analysis, "score": r.score}
                    for r in self.history.rounds[0].agent_reports
                    if r.agent_name != agent.name
                ])
            )
        
        if self.llm_callable:
            return await self.llm_callable(prompt)
        
        # 兼容同步/异步 Agent
        analyze_method = getattr(agent, 'analyze', None)
        if analyze_method is None:
            raise ValueError(f"Agent {agent.name} 没有 analyze 方法")
        
        is_async = inspect.iscoroutinefunction(analyze_method)
        
        if is_async:
            result = await analyze_method(prompt)
        else:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                lambda: analyze_method(prompt)
            )
        
        if isinstance(result, AgentReport):
            return result.analysis
        return str(result)
    
    async def _agent_final_report(
        self,
        agent,
        previous_reports: List[AgentReport],
        agent_discussion_content: List[str]
    ) -> AgentReport:
        """生成最终报告（兼容同步/异步）"""
        # 安全地获取原始评分
        agent_names = [r.agent_name for r in previous_reports]
        original_score = 5.0  # 默认评分
        if agent.name in agent_names:
            original_score = previous_reports[agent_names.index(agent.name)].score
        
        context = f"""
你的原始评分：{original_score}
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
            return self._parse_report(agent, response)
        
        # 兼容同步/异步 Agent
        analyze_method = getattr(agent, 'analyze', None)
        if analyze_method is None:
            raise ValueError(f"Agent {agent.name} 没有 analyze 方法")
        
        is_async = inspect.iscoroutinefunction(analyze_method)
        
        if is_async:
            result = await analyze_method(prompt)
        else:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                lambda: analyze_method(prompt)
            )
        
        return self._parse_report(agent, result)
    
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
        # 处理 role 可能是字符串或枚举的情况
        role_value = role.value if hasattr(role, 'value') else str(role)
        role_name = role.name.lower() if hasattr(role, 'name') else str(role).lower()
        
        # 简化的实现，实际可能需要更复杂的逻辑
        for msg in reversed(messages):
            content = msg.get('content', '').lower()
            # 检查是否提到了该角色
            if role_value in content or role_name in content:
                return msg.get('content')
        return None
    
    def _parse_report(self, agent, response) -> AgentReport:
        """解析 LLM 响应生成报告（兼容多种输入类型）"""
        import re
        
        # 如果已经是 AgentReport 对象，直接返回
        if isinstance(response, AgentReport):
            return response
        
        # 如果不是字符串，转为字符串
        if not isinstance(response, str):
            response = str(response)
        
        # 简化的解析逻辑
        score = 5.0
        confidence = 0.5
        
        # 尝试提取评分
        score_match = re.search(r'评分[：:]?\s*(\d+\.?\d*)', response)
        if score_match:
            score = float(score_match.group(1))
        
        confidence_match = re.search(r'置信[度:]?\s*(\d+\.?\d*)', response)
        if confidence_match:
            confidence = float(confidence_match.group(1))
        
        # 尝试从 JSON 格式解析
        try:
            import json
            json_start = response.find('{')
            json_end = response.rfind('}')
            if json_start != -1 and json_end != -1:
                data = json.loads(response[json_start:json_end+1])
                if 'score' in data:
                    score = float(data['score'])
                if 'confidence' in data:
                    confidence = float(data['confidence'])
        except (json.JSONDecodeError, ValueError):
            pass
        
        # 获取 agent 的 role（兼容不同类型）
        agent_role = getattr(agent, 'role', AgentRole.TECHNICAL)
        if isinstance(agent_role, str):
            # 将字符串转为 AgentRole 枚举
            role_map = {
                'technical': AgentRole.TECHNICAL,
                'intelligence': AgentRole.INTELLIGENCE,
                'risk': AgentRole.RISK,
                'fundamental': AgentRole.FUNDAMENTAL,
                'leader': AgentRole.LEADER,
            }
            agent_role = role_map.get(agent_role.lower(), AgentRole.TECHNICAL)
        
        return AgentReport(
            agent_name=agent.name,
            agent_role=agent_role,
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

class SimpleLLMAgent:
    """简单的 LLM Agent 实现（用于测试）"""
    
    def __init__(self, name: str, role: AgentRole, role_description: str):
        self.name = name
        self.role = role
        self.role_description = role_description
    
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
