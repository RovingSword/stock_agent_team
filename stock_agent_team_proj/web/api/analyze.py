"""
股票分析接口
POST /api/analyze - 执行规则引擎股票分析
POST /api/analyze_llm - 执行 LLM Agent Team 分析（支持SSE）
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from main import StockAgentTeam
from agents.llm import create_team, AgentReport

router = APIRouter()


class AnalyzeRequest(BaseModel):
    """股票分析请求"""
    stock_code: str = Field(..., description="股票代码", example="300750")
    stock_name: Optional[str] = Field(None, description="股票名称，不提供则自动获取")
    user_request: str = Field("", description="用户请求描述")


class AgentScore(BaseModel):
    """Agent评分"""
    agent_type: str
    agent_name: str
    score: float
    weight: float
    weighted_score: float
    comment: str
    key_points: list
    risk_points: list


class AnalyzeResponse(BaseModel):
    """股票分析响应"""
    success: bool
    message: str
    data: Optional[dict] = None


def get_team() -> StockAgentTeam:
    """获取StockAgentTeam实例"""
    if not hasattr(get_team, '_instance'):
        get_team._instance = StockAgentTeam()
    return get_team._instance


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_stock(request: AnalyzeRequest):
    """
    股票分析接口（规则引擎模式）
    
    输入股票代码，返回分析报告（评分、建议、各Agent意见）
    """
    try:
        # 参数验证
        if not request.stock_code:
            raise HTTPException(status_code=400, detail="股票代码不能为空")
        
        stock_code = request.stock_code.strip()
        stock_name = request.stock_name.strip() if request.stock_name else stock_code
        
        # 执行分析
        team = get_team()
        decision = team.analyze(
            stock_code=stock_code,
            stock_name=stock_name,
            user_request=request.user_request
        )
        
        # 提取Agent评分
        agent_scores = []
        score_breakdown = decision.score_breakdown or {}
        
        # 技术分析员
        if 'technical' in score_breakdown:
            tech = score_breakdown['technical']
            agent_scores.append(AgentScore(
                agent_type='technical',
                agent_name='技术分析员',
                score=tech.get('score', 0),
                weight=tech.get('weight', 0.35),
                weighted_score=tech.get('weighted_score', 0),
                comment=tech.get('comment', ''),
                key_points=tech.get('key_points', []),
                risk_points=tech.get('risk_points', [])
            ))
        
        # 情报员
        if 'intelligence' in score_breakdown:
            intel = score_breakdown['intelligence']
            agent_scores.append(AgentScore(
                agent_type='intelligence',
                agent_name='情报员',
                score=intel.get('score', 0),
                weight=intel.get('weight', 0.30),
                weighted_score=intel.get('weighted_score', 0),
                comment=intel.get('comment', ''),
                key_points=intel.get('key_points', []),
                risk_points=intel.get('risk_points', [])
            ))
        
        # 风控官
        if 'risk' in score_breakdown:
            risk = score_breakdown['risk']
            agent_scores.append(AgentScore(
                agent_type='risk',
                agent_name='风控官',
                score=risk.get('score', 0),
                weight=risk.get('weight', 0.20),
                weighted_score=risk.get('weighted_score', 0),
                comment=risk.get('comment', ''),
                key_points=risk.get('key_points', []),
                risk_points=risk.get('risk_points', [])
            ))
        
        # 基本面分析师
        if 'fundamental' in score_breakdown:
            fund = score_breakdown['fundamental']
            agent_scores.append(AgentScore(
                agent_type='fundamental',
                agent_name='基本面分析师',
                score=fund.get('score', 0),
                weight=fund.get('weight', 0.15),
                weighted_score=fund.get('weighted_score', 0),
                comment=fund.get('comment', ''),
                key_points=fund.get('key_points', []),
                risk_points=fund.get('risk_points', [])
            ))
        
        # 构建返回数据
        result_data = {
            'task_id': decision.header.message_id,
            'stock_code': decision.stock_code,
            'stock_name': decision.stock_name,
            'final_action': decision.final_action,
            'confidence': decision.confidence,
            'composite_score': decision.composite_score,
            'execution': {
                'entry_zone': decision.execution.get('entry_zone', []),
                'stop_loss': decision.execution.get('stop_loss', 0),
                'take_profit_1': decision.execution.get('take_profit_1', 0),
                'take_profit_2': decision.execution.get('take_profit_2', 0),
                'position_size': decision.execution.get('position_size', 0),
            },
            'rationale': {
                'buy_reasons': decision.rationale.get('buy_reasons', []),
                'risk_warnings': decision.rationale.get('risk_warnings', []),
            },
            'agent_scores': [s.model_dump() for s in agent_scores],
            'timestamp': decision.header.timestamp,
        }
        
        return AnalyzeResponse(
            success=True,
            message="分析完成",
            data=result_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        return AnalyzeResponse(
            success=False,
            message=f"分析失败: {str(e)}",
            data=None
        )


# ==================== LLM Agent Team SSE 分析接口 ====================

def get_llm_config():
    """获取LLM配置，优先从 llm_config.yaml 读取"""
    import yaml

    # 默认配置
    config = {
        "api_key": "",
        "base_url": "https://www.dmxapi.cn/v1",
        "provider": "openai_compatible",
        "model": "gpt-3.5-turbo",
    }

    # 尝试从 llm_config.yaml 读取
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "config", "llm_config.yaml"
    )
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                yaml_config = yaml.safe_load(f)

            llm_section = yaml_config.get("llm", {})
            providers = llm_section.get("providers", {})
            default_provider = llm_section.get("default_provider", "openai_compatible")

            provider_config = providers.get(default_provider, {})

            config["provider"] = default_provider
            config["api_key"] = provider_config.get("api_key", "")
            config["base_url"] = provider_config.get("base_url", config["base_url"])
            config["model"] = provider_config.get("model", config["model"])
            config["temperature"] = provider_config.get("temperature", 0.7)
            config["max_tokens"] = provider_config.get("max_tokens", 2000)
        except Exception as e:
            # YAML 读取失败，回退到环境变量
            pass

    # 环境变量覆盖（优先级更高）
    env_key = os.environ.get("OPENAI_API_KEY")
    if env_key:
        config["api_key"] = env_key
    env_url = os.environ.get("OPENAI_BASE_URL")
    if env_url:
        config["base_url"] = env_url
    env_model = os.environ.get("OPENAI_MODEL")
    if env_model:
        config["model"] = env_model

    return config


async def generate_sse_events(stock_code: str, stock_name: str):
    """
    生成SSE事件流
    
    事件类型:
    - agent_analysis: Agent分析结果
    - discussion: 讨论消息
    - final_decision: 最终决策
    - error: 错误
    - done: 完成
    """
    try:
        # 发送开始事件
        yield f"event: start\ndata: {json.dumps({'status': 'starting', 'message': 'LLM Agent Team 开始分析...'})}\n\n"
        
        # 获取LLM配置
        llm_config = get_llm_config()
        
        # 创建LLM Agent团队
        agent_names = {
            "leader": "👔 队长",
            "technical": "🔧 技术分析员",
            "intelligence": "📡 情报员",
            "risk": "🛡️ 风控官",
            "fundamental": "📈 基本面分析员"
        }
        
        team = create_team(
            provider=llm_config["provider"],
            custom_names=agent_names,
            api_key=llm_config["api_key"],
            base_url=llm_config["base_url"],
            model=llm_config["model"],
            temperature=0.7,
            max_tokens=1500
        )
        
        # 获取规则引擎的分析数据作为上下文
        rule_team = get_team()
        rule_decision = rule_team.analyze(
            stock_code=stock_code,
            stock_name=stock_name,
            user_request="中短线波段交易分析"
        )
        
        # 构建分析数据
        score_breakdown = rule_decision.score_breakdown or {}
        analysis_data = {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "current_price": rule_decision.execution.get("current_price", 0),
            "market_context": "震荡偏多",
            "technical": {
                "score": score_breakdown.get("technical", {}).get("score", 5),
                "comment": score_breakdown.get("technical", {}).get("comment", ""),
                "key_points": score_breakdown.get("technical", {}).get("key_points", [])
            },
            "intelligence": {
                "score": score_breakdown.get("intelligence", {}).get("score", 5),
                "comment": score_breakdown.get("intelligence", {}).get("comment", ""),
                "key_points": score_breakdown.get("intelligence", {}).get("key_points", [])
            },
            "risk": {
                "score": score_breakdown.get("risk", {}).get("score", 5),
                "comment": score_breakdown.get("risk", {}).get("comment", ""),
                "risk_points": score_breakdown.get("risk", {}).get("risk_points", [])
            },
            "fundamental": {
                "score": score_breakdown.get("fundamental", {}).get("score", 5),
                "comment": score_breakdown.get("fundamental", {}).get("comment", ""),
                "key_points": score_breakdown.get("fundamental", {}).get("key_points", [])
            }
        }
        
        # 发送规则引擎分析完成事件
        yield f"event: rule_analysis\ndata: {json.dumps({'status': 'complete', 'data': {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'composite_score': rule_decision.composite_score,
            'final_action': rule_decision.final_action
        }})}\n\n"
        
        await asyncio.sleep(0.5)
        
        # ===== 第一轮：各Agent独立分析 =====
        yield f"event: round_start\ndata: {json.dumps({'round': 1, 'type': 'independent', 'title': '📊 第一轮：独立分析'})}\n\n"
        
        # 为每个Agent生成分析
        agent_roles = ["technical", "intelligence", "risk", "fundamental"]
        agent_configs = {
            "technical": {"icon": "📈", "name": "技术分析员"},
            "intelligence": {"icon": "📡", "name": "情报员"},
            "risk": {"icon": "🛡️", "name": "风控官"},
            "fundamental": {"icon": "📈", "name": "基本面分析员"}
        }
        
        round1_reports = []
        
        for role in agent_roles:
            agent = team.get(role)
            if not agent:
                continue
                
            # 发送Agent开始分析事件
            config = agent_configs.get(role, {})
            yield f"event: agent_start\ndata: {json.dumps({
                'round': 1,
                'agent_name': config.get('name', role),
                'agent_role': role,
                'icon': config.get('icon', '🤖')
            })}\n\n"
            
            # 更新讨论状态
            agent_display_name = config.get('name', role)
            status_msg = f'{agent_display_name}正在分析...'
            yield f"event: status\ndata: {json.dumps({'status': 'analyzing', 'message': status_msg})}\n\n"

            await asyncio.sleep(0.3)  # 模拟思考时间
            
            # 准备分析提示词
            role_data = analysis_data.get(role, {})
            prompt = f"""你是 {agent.name}，负责{agent_configs.get(role, {}).get('name', role)}的分析。

股票信息：
- 股票代码: {stock_code}
- 股票名称: {stock_name}
- 当前价格: {analysis_data.get('current_price', 'N/A')}

你的分析数据：
- 评分: {role_data.get('score', 5)}
- 评价: {role_data.get('comment', '')}
- 关键点: {', '.join(role_data.get('key_points', [])[:3])}

请给出你的专业分析，包括：
1. 评分（0-10）
2. 置信度（0-1）
3. 简短分析（100字以内）

格式：
评分: X.X
置信度: X.X
分析: XXX
"""
            
            try:
                # agent.analyze() 是同步方法，需要在线程池中运行以避免阻塞事件循环
                agent_report = await asyncio.to_thread(agent.analyze, prompt)
                
                # agent.analyze() 返回 AgentReport 对象
                if isinstance(agent_report, AgentReport):
                    score = agent_report.score
                    confidence = agent_report.confidence
                    analysis_text = agent_report.analysis
                    summary = agent_report.summary
                else:
                    # 兼容字符串返回
                    score = role_data.get('score', 5.0)
                    confidence = 0.7
                    analysis_text = str(agent_report)
                    summary = analysis_text[:100] if len(analysis_text) > 100 else analysis_text
                
                report = {
                    'agent_name': config.get('name', role),
                    'agent_role': role,
                    'icon': config.get('icon', '🤖'),
                    'score': score,
                    'confidence': confidence,
                    'analysis': analysis_text,
                    'summary': summary,
                    'round': 1
                }
                round1_reports.append(report)
                
                # 发送分析完成事件
                yield f"event: agent_analysis\ndata: {json.dumps(report)}\n\n"
                
            except Exception as e:
                # 发送错误事件
                yield f"event: error\ndata: {json.dumps({
                    'agent': config.get('name', role),
                    'error': str(e)
                })}\n\n"
        
        await asyncio.sleep(0.5)
        
        # ===== 第二轮：讨论 =====
        yield f"event: round_start\ndata: {json.dumps({'round': 2, 'type': 'discussion', 'title': '💬 第二轮：讨论'})}\n\n"
        
        # Leader发起讨论
        leader = team.get("leader")
        if leader:
            discussion_prompt = f"""股票 {stock_name}({stock_code}) 分析团队讨论开始。

各分析师的初步意见：
{chr(10).join([f"- {r['agent_name']}: 评分 {r['score']}分，{r['summary']}" for r in round1_reports])}

请作为队长，引导讨论并总结各方观点。
"""
            
            try:
                leader_report = await asyncio.to_thread(leader.analyze, discussion_prompt)
                
                # 处理 AgentReport 返回值
                leader_content = leader_report.analysis if isinstance(leader_report, AgentReport) else str(leader_report)

                yield f"event: discussion\ndata: {json.dumps({
                    'round': 2,
                    'agent_name': '👔 队长',
                    'agent_role': 'leader',
                    'content': leader_content,
                    'type': 'opening'
                })}\n\n"
                
                await asyncio.sleep(0.5)
                
                # 各Agent回应
                for report in round1_reports:
                    role = report['agent_role']
                    agent = team.get(role)
                    if not agent:
                        continue
                    
                    response_prompt = f"""作为 {report['agent_name']}，你收到了队长的讨论引导：

{leader_content}

请基于你的专业角度，回应讨论并发表你的观点（100字以内）。
"""
                    
                    try:
                        agent_report = await asyncio.to_thread(agent.analyze, response_prompt)
                        
                        # 处理 AgentReport 返回值
                        response_content = agent_report.analysis if isinstance(agent_report, AgentReport) else str(agent_report)

                        yield f"event: discussion\ndata: {json.dumps({
                            'round': 2,
                            'agent_name': report['icon'] + ' ' + report['agent_name'],
                            'agent_role': role,
                            'content': response_content,
                            'type': 'response'
                        })}\n\n"
                        
                        await asyncio.sleep(0.3)
                        
                    except Exception as e:
                        yield f"event: error\ndata: {json.dumps({
                            'agent': report['agent_name'],
                            'error': str(e)
                        })}\n\n"
                        
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': f'Leader讨论失败: {str(e)}'})}\n\n"
        
        await asyncio.sleep(0.5)
        
        # ===== 第三轮：达成共识 =====
        yield f"event: round_start\ndata: {json.dumps({'round': 3, 'type': 'consensus', 'title': '🤝 第三轮：达成共识'})}\n\n"
        
        # 计算综合评分
        avg_score = sum(r['score'] for r in round1_reports) / len(round1_reports) if round1_reports else 5.0
        
        # 确定最终决策
        if avg_score >= 7.0:
            action = "buy"
            action_text = "建议买入"
        elif avg_score >= 5.0:
            action = "watch"
            action_text = "观望"
        else:
            action = "avoid"
            action_text = "建议回避"
        
        # 生成最终决策
        final_decision = {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'final_action': action,
            'action_text': action_text,
            'composite_score': round(avg_score, 1),
            'confidence': rule_decision.confidence,
            'entry_zone': rule_decision.execution.get('entry_zone', []),
            'stop_loss': rule_decision.execution.get('stop_loss', 0),
            'take_profit_1': rule_decision.execution.get('take_profit_1', 0),
            'take_profit_2': rule_decision.execution.get('take_profit_2', 0),
            'position_size': rule_decision.execution.get('position_size', 0),
            'agent_scores': [{
                'agent_name': r['agent_name'],
                'agent_role': r['agent_role'],
                'icon': r['icon'],
                'score': r['score'],
                'confidence': r['confidence'],
                'summary': r['summary']
            } for r in round1_reports],
            'buy_reasons': rule_decision.rationale.get('buy_reasons', [])[:3],
            'risk_warnings': rule_decision.rationale.get('risk_warnings', [])[:3],
            'timestamp': datetime.now().isoformat()
        }
        
        yield f"event: final_decision\ndata: {json.dumps(final_decision)}\n\n"
        
        # 发送完成事件（携带完整分析结果数据）
        yield f"event: done\ndata: {json.dumps(final_decision)}\n\n"

    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"


@router.post("/analyze_llm")
async def analyze_stock_llm(request: AnalyzeRequest):
    """
    LLM Agent Team 分析接口（SSE实时推送）
    
    输入股票代码，返回实时讨论过程和分析结果
    """
    try:
        # 参数验证
        if not request.stock_code:
            raise HTTPException(status_code=400, detail="股票代码不能为空")
        
        stock_code = request.stock_code.strip()
        stock_name = request.stock_name.strip() if request.stock_name else stock_code
        
        # 返回SSE流
        return StreamingResponse(
            generate_sse_events(stock_code, stock_name),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        async def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        return StreamingResponse(error_gen(), media_type="text/event-stream")
