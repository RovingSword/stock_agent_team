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
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from main import StockAgentTeam
from agents.llm import create_team, AgentReport
from utils.data_fetcher import data_fetcher

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


LLM_ROLE_WEIGHTS = {
    "technical": 0.25,
    "intelligence": 0.25,
    "risk": 0.25,
    "fundamental": 0.25,
}


def get_team() -> StockAgentTeam:
    """获取StockAgentTeam实例"""
    if not hasattr(get_team, '_instance'):
        get_team._instance = StockAgentTeam()
    return get_team._instance


def _build_llm_agent_prompt(
    agent_name: str,
    role_name: str,
    stock_code: str,
    stock_name: str,
    current_price: Any,
    raw_data: Dict[str, Any],
    rule_reference: Dict[str, Any],
) -> str:
    missing_fields = [
        field_name
        for field_name, value in raw_data.items()
        if value in (None, {}, [])
    ]
    missing_text = "无" if not missing_fields else ", ".join(missing_fields)

    return f"""你是 {agent_name}，负责{role_name}。

请基于以下股票信息输出结构化 JSON，不要输出额外解释。

股票信息：
- 股票代码: {stock_code}
- 股票名称: {stock_name}
- 当前价格: {current_price}

真实原始数据（以下字段为空表示当前未获取到真实数据）：
{json.dumps(raw_data, ensure_ascii=False, indent=2)}

关键缺失字段：{missing_text}

规则引擎参考（仅供参考，不可当作原始事实）：
{json.dumps(rule_reference, ensure_ascii=False, indent=2)}

请优先依据真实原始数据分析；如果关键数据缺失，请在结论中明确说明“数据不足”。

请输出 JSON：
{{
  "score": 0-10 的评分,
  "confidence": 0-1 的置信度,
  "summary": "一句话总结",
  "analysis": "详细分析",
  "risks": ["风险1", "风险2"],
  "opportunities": ["机会1", "机会2"]
}}"""


def _as_dict(payload: Any) -> Dict[str, Any]:
    return payload if isinstance(payload, dict) else {}


def _as_list(payload: Any) -> List[Any]:
    return payload if isinstance(payload, list) else []


def _resolve_current_price(full_data: Dict[str, Any], fallback_execution: Dict[str, Any]) -> Any:
    quote_price = _as_dict(full_data.get("quote")).get("current_price")
    if quote_price not in (None, ""):
        return quote_price

    technical_price = _as_dict(full_data.get("technical")).get("current_price")
    if technical_price not in (None, ""):
        return technical_price

    return fallback_execution.get("current_price")


def _build_role_payloads(
    stock_code: str,
    full_data: Dict[str, Any],
    current_price: Any,
) -> Dict[str, Dict[str, Any]]:
    technical = _as_dict(full_data.get("technical"))
    quote = _as_dict(full_data.get("quote"))
    fund_flow = _as_dict(full_data.get("fund_flow"))
    north_bound = _as_dict(full_data.get("north_bound"))
    market = _as_dict(full_data.get("market"))
    financial = _as_dict(full_data.get("financial"))
    valuation = _as_dict(full_data.get("valuation"))
    news = _as_list(full_data.get("news"))

    return {
        "technical": {
            "quote": quote,
            "technical": technical,
            "current_price": current_price,
        },
        "intelligence": {
            "quote": quote,
            "fund_flow": fund_flow,
            "north_bound": north_bound,
            "market": market,
            "news": news,
            "current_price": current_price,
        },
        "risk": {
            "quote": quote,
            "market": market,
            "technical": {
                "current_price": technical.get("current_price"),
                "change_pct": technical.get("change_pct"),
                "support_levels": technical.get("support_levels"),
                "resistance_levels": technical.get("resistance_levels"),
            },
            "financial": financial,
            "valuation": valuation,
            "current_price": current_price,
        },
        "fundamental": {
            "quote": quote,
            "financial": financial,
            "valuation": valuation,
            "current_price": current_price,
            "stock_code": stock_code,
        },
    }


def _build_rule_reference(rule_decision) -> Dict[str, Dict[str, Any]]:
    score_breakdown = getattr(rule_decision, "score_breakdown", {}) or {}
    execution = getattr(rule_decision, "execution", {}) or {}

    def get_reference(role: str) -> Dict[str, Any]:
        role_reference = score_breakdown.get(role, {}) or {}
        return {
            "score": role_reference.get("score", 5),
            "comment": role_reference.get("comment", ""),
            "key_points": role_reference.get("key_points", []),
            "risk_points": role_reference.get("risk_points", []),
        }

    references = {
        "technical": get_reference("technical"),
        "intelligence": get_reference("intelligence"),
        "risk": get_reference("risk"),
        "fundamental": get_reference("fundamental"),
    }

    for role_reference in references.values():
        role_reference["execution"] = {
            "entry_zone": execution.get("entry_zone", []),
            "stop_loss": execution.get("stop_loss", 0),
            "take_profit_1": execution.get("take_profit_1", 0),
            "take_profit_2": execution.get("take_profit_2", 0),
            "position_size": execution.get("position_size", 0),
        }

    return references


def _build_llm_analysis_data(stock_code: str, rule_decision) -> Dict[str, Any]:
    execution = getattr(rule_decision, "execution", {}) or {}
    full_data = data_fetcher.get_full_data(stock_code) or {}
    if "news" not in full_data:
        full_data["news"] = data_fetcher.get_news(stock_code, limit=5) or []

    current_price = _resolve_current_price(full_data, execution)
    role_payloads = _build_role_payloads(stock_code, full_data, current_price)
    rule_reference = _build_rule_reference(rule_decision)

    return {
        "stock_code": stock_code,
        "current_price": current_price,
        "full_data": full_data,
        "role_payloads": role_payloads,
        "rule_reference": rule_reference,
    }


def _serialize_agent_report(report: AgentReport, icon: str, round_number: int) -> Dict[str, Any]:
    payload = report.to_dict()
    payload["icon"] = icon
    payload["round"] = round_number
    return payload


def _normalize_final_action(action: Optional[str], score: float) -> str:
    normalized = (action or "").strip().lower()
    alias_map = {
        "建议买入": "buy",
        "买入": "buy",
        "buy": "buy",
        "强烈买入": "buy",
        "sell": "sell",
        "卖出": "sell",
        "watch": "watch",
        "观望": "watch",
        "hold": "hold",
        "持有": "hold",
        "avoid": "avoid",
        "回避": "avoid",
    }
    if normalized in alias_map:
        return alias_map[normalized]

    if score >= 7.0:
        return "buy"
    if score >= 5.0:
        return "watch"
    return "avoid"


def _get_action_text(final_action: str, leader_report: AgentReport) -> str:
    action_text = leader_report.metadata.get("action") if leader_report.metadata else None
    if action_text:
        return str(action_text)

    action_map = {
        "buy": "建议买入",
        "sell": "建议卖出",
        "watch": "观望",
        "hold": "继续持有",
        "avoid": "建议回避",
    }
    return action_map.get(final_action, final_action)


def _build_final_decision(
    stock_code: str,
    stock_name: str,
    rule_decision,
    round1_reports: List[Dict[str, Any]],
    leader_report: AgentReport,
) -> Dict[str, Any]:
    leader_score = leader_report.score if leader_report.score is not None else 0.0
    final_action = _normalize_final_action(
        leader_report.metadata.get("decision") if leader_report.metadata else None,
        leader_score,
    )

    return {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "final_action": final_action,
        "action_text": _get_action_text(final_action, leader_report),
        "composite_score": round(leader_score, 1),
        "confidence": leader_report.confidence,
        "summary": leader_report.summary,
        "analysis": leader_report.analysis,
        "risks": leader_report.risks,
        "opportunities": leader_report.opportunities,
        "entry_zone": rule_decision.execution.get("entry_zone", []),
        "stop_loss": leader_report.metadata.get("stop_loss") if leader_report.metadata and leader_report.metadata.get("stop_loss") is not None else rule_decision.execution.get("stop_loss", 0),
        "take_profit_1": rule_decision.execution.get("take_profit_1", 0),
        "take_profit_2": rule_decision.execution.get("take_profit_2", 0),
        "position_size": (
            leader_report.metadata.get("position_ratio", 0) / 100
            if leader_report.metadata and leader_report.metadata.get("position_ratio") not in (None, "")
            else rule_decision.execution.get("position_size", 0)
        ),
        "agent_scores": [
            {
                "agent_name": r["agent_name"],
                "agent_role": r["agent_role"],
                "icon": r["icon"],
                "score": r["score"],
                "confidence": r["confidence"],
                "summary": r["summary"],
                "analysis": r["analysis"],
                "risks": r.get("risks", []),
                "opportunities": r.get("opportunities", []),
                "weight": LLM_ROLE_WEIGHTS.get(r["agent_role"], 0),
                "weighted_score": round(r["score"] * LLM_ROLE_WEIGHTS.get(r["agent_role"], 0), 2),
            }
            for r in round1_reports
        ],
        "buy_reasons": rule_decision.rationale.get("buy_reasons", [])[:3],
        "risk_warnings": rule_decision.rationale.get("risk_warnings", [])[:3],
        "timestamp": datetime.now().isoformat(),
    }


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
        
        # 构建 LLM 使用的真实原始数据与规则引擎参考
        analysis_data = _build_llm_analysis_data(stock_code, rule_decision)
        
        # 发送规则引擎分析完成事件
        rule_analysis_payload = {
            "status": "complete",
            "data": {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "composite_score": rule_decision.composite_score,
                "final_action": rule_decision.final_action,
            },
        }
        yield f"event: rule_analysis\ndata: {json.dumps(rule_analysis_payload)}\n\n"
        
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
        discussion_messages = []
        
        for role in agent_roles:
            agent = team.get(role)
            if not agent:
                continue
                
            # 发送Agent开始分析事件
            config = agent_configs.get(role, {})
            agent_start_payload = {
                'round': 1,
                'agent_name': config.get('name', role),
                'agent_role': role,
                'icon': config.get('icon', '🤖')
            }
            yield f"event: agent_start\ndata: {json.dumps(agent_start_payload)}\n\n"
            
            # 更新讨论状态
            agent_display_name = config.get('name', role)
            status_msg = f'{agent_display_name}正在分析...'
            yield f"event: status\ndata: {json.dumps({'status': 'analyzing', 'message': status_msg})}\n\n"

            await asyncio.sleep(0.3)  # 模拟思考时间
            
            # 准备分析提示词
            raw_data = analysis_data["role_payloads"].get(role, {})
            rule_reference = analysis_data["rule_reference"].get(role, {})
            prompt = _build_llm_agent_prompt(
                agent_name=agent.name,
                role_name=agent_configs.get(role, {}).get('name', role),
                stock_code=stock_code,
                stock_name=stock_name,
                current_price=analysis_data.get('current_price', 'N/A'),
                raw_data=raw_data,
                rule_reference=rule_reference,
            )
            
            try:
                # agent.analyze() 是同步方法，需要在线程池中运行以避免阻塞事件循环
                agent_report = await asyncio.to_thread(agent.analyze, prompt)
                
                # agent.analyze() 返回 AgentReport 对象
                if isinstance(agent_report, AgentReport):
                    report = _serialize_agent_report(
                        agent_report,
                        icon=config.get('icon', '🤖'),
                        round_number=1,
                    )
                else:
                    analysis_text = str(agent_report)
                    report = {
                        'agent_name': config.get('name', role),
                        'agent_role': role,
                        'icon': config.get('icon', '🤖'),
                        'score': rule_reference.get('score', 0.0),
                        'confidence': 0.5,
                        'summary': analysis_text[:100] if len(analysis_text) > 100 else analysis_text,
                        'analysis': analysis_text,
                        'risks': [],
                        'opportunities': [],
                        'round': 1,
                    }
                round1_reports.append(report)
                
                # 发送分析完成事件
                yield f"event: agent_analysis\ndata: {json.dumps(report)}\n\n"
                
            except Exception as e:
                # 发送错误事件
                error_payload = {
                    'agent': config.get('name', role),
                    'error': str(e)
                }
                yield f"event: error\ndata: {json.dumps(error_payload)}\n\n"
        
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

                leader_event = {
                    'round': 2,
                    'agent_name': '👔 队长',
                    'agent_role': 'leader',
                    'content': leader_content,
                    'type': 'opening'
                }
                discussion_messages.append(leader_event)
                yield f"event: discussion\ndata: {json.dumps(leader_event)}\n\n"
                
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

                        response_event = {
                            'round': 2,
                            'agent_name': report['icon'] + ' ' + report['agent_name'],
                            'agent_role': role,
                            'content': response_content,
                            'type': 'response'
                        }
                        discussion_messages.append(response_event)
                        yield f"event: discussion\ndata: {json.dumps(response_event)}\n\n"
                        
                        await asyncio.sleep(0.3)
                        
                    except Exception as e:
                        error_payload = {
                            'agent': report['agent_name'],
                            'error': str(e)
                        }
                        yield f"event: error\ndata: {json.dumps(error_payload)}\n\n"
                        
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': f'Leader讨论失败: {str(e)}'})}\n\n"
        
        await asyncio.sleep(0.5)
        
        # ===== 第三轮：达成共识 =====
        yield f"event: round_start\ndata: {json.dumps({'round': 3, 'type': 'consensus', 'title': '🤝 第三轮：达成共识'})}\n\n"
        
        final_prompt = f"""你是投资决策队长，请基于以下信息输出最终 JSON 决策，不要输出额外解释。

股票信息：
- 股票代码: {stock_code}
- 股票名称: {stock_name}

第一轮独立分析：
{chr(10).join([f"- {r['agent_name']}({r['agent_role']}): 评分 {r['score']:.1f}，摘要：{r['summary']}，分析：{r['analysis']}" for r in round1_reports])}

第二轮讨论摘录：
{chr(10).join([f"- {m['agent_name']}: {m['content']}" for m in discussion_messages]) if discussion_messages else "- 暂无讨论记录"}

请输出 JSON：
{{
  "score": 综合评分(0-10),
  "confidence": 置信度(0-1),
  "summary": "一句话决策",
  "analysis": "最终决策理由",
  "risks": ["主要风险"],
  "opportunities": ["主要机会"],
  "decision": "buy/sell/watch/hold/avoid",
  "action": "展示给用户的中文动作",
  "stop_loss": 止损价,
  "position_ratio": 建议仓位百分比
}}"""

        final_decision = None
        if leader:
            try:
                final_report = await asyncio.to_thread(leader.analyze, final_prompt)
                if isinstance(final_report, AgentReport):
                    final_decision = _build_final_decision(
                        stock_code=stock_code,
                        stock_name=stock_name,
                        rule_decision=rule_decision,
                        round1_reports=round1_reports,
                        leader_report=final_report,
                    )
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': f'Leader最终决策失败: {str(e)}'})}\n\n"

        if final_decision is None:
            fallback_score = sum(r['score'] for r in round1_reports) / len(round1_reports) if round1_reports else 0.0
            fallback_action = _normalize_final_action(None, fallback_score)
            final_decision = {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'final_action': fallback_action,
                'action_text': _get_action_text(fallback_action, AgentReport(
                    agent_name='👔 队长',
                    agent_role='leader',
                    score=fallback_score,
                    confidence=0.5,
                    summary='综合分析完成',
                    analysis='未能获取队长最终决策，使用各 Agent 综合结果兜底。',
                )),
                'composite_score': round(fallback_score, 1),
                'confidence': 0.5,
                'summary': '综合分析完成',
                'analysis': '未能获取队长最终决策，使用各 Agent 综合结果兜底。',
                'risks': [],
                'opportunities': [],
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
                    'summary': r['summary'],
                    'analysis': r['analysis'],
                    'risks': r.get('risks', []),
                    'opportunities': r.get('opportunities', []),
                    'weight': LLM_ROLE_WEIGHTS.get(r['agent_role'], 0),
                    'weighted_score': round(r['score'] * LLM_ROLE_WEIGHTS.get(r['agent_role'], 0), 2),
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
