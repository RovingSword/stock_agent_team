"""
股票分析接口
POST /api/analyze - 执行规则引擎股票分析
POST /api/analyze_llm - 执行 LLM Agent Team 分析（支持SSE）
"""
import asyncio
import copy
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

from config.project_paths import ensure_project_root_on_path

ensure_project_root_on_path()

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from main import StockAgentTeam
from agents.llm import create_team, AgentReport
from utils.data_fetcher import data_fetcher
from utils.intel_pipeline import (
    cache_intel_has_search_lists,
    format_brief_for_prompt,
    prepare_intel_package_for_analysis,
    slice_brief_for_agent_role,
)
from utils.logger import get_logger

router = APIRouter()
_analyze_logger = get_logger("web.api.analyze")


class AnalyzeRequest(BaseModel):
    """股票分析请求"""
    stock_code: str = Field(..., description="股票代码", example="300750")
    stock_name: Optional[str] = Field(None, description="股票名称，不提供则自动获取")
    user_request: str = Field("", description="用户请求描述")
    force_refresh: bool = Field(False, description="是否强制刷新情报缓存")


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


from config.settings import LLM_ROLE_WEIGHTS

# LLM_ROLE_WEIGHTS 已从 config/settings.py 统一导入（与规则引擎权重配置对齐）


def get_team() -> StockAgentTeam:
    """获取StockAgentTeam实例"""
    if not hasattr(get_team, '_instance'):
        get_team._instance = StockAgentTeam()
    return get_team._instance


def _trim_role_payload_for_llm(
    role: str, raw_data: Dict[str, Any], use_intel_brief: bool
) -> Dict[str, Any]:
    """有 IntelBrief 时压缩部分 raw JSON，腾出 token 给摘要层。"""
    data = copy.deepcopy(raw_data)
    if not use_intel_brief:
        return data
    if role == "intelligence":
        news = data.get("news")
        if isinstance(news, list) and len(news) > 3:
            data["news"] = news[:3]
    elif role == "fundamental":
        fin = data.get("financial")
        if isinstance(fin, dict) and len(fin) > 28:
            keys = sorted(fin.keys())[:28]
            data["financial"] = {k: fin[k] for k in keys}
    elif role == "technical":
        tech = data.get("technical")
        if isinstance(tech, dict):
            preferred = (
                "current_price",
                "change_pct",
                "rsi",
                "macd",
                "volume",
                "volume_ratio",
                "support_levels",
                "resistance_levels",
                "ma5",
                "ma10",
                "ma20",
                "ma60",
                "boll",
            )
            data["technical"] = {k: tech[k] for k in preferred if k in tech}
    return data


def _build_llm_agent_prompt(
    agent_name: str,
    role_name: str,
    stock_code: str,
    stock_name: str,
    current_price: Any,
    raw_data: Dict[str, Any],
    rule_reference: Dict[str, Any],
    web_intelligence: Optional[Dict[str, Any]] = None,
    agent_role: str = "",
    intel_brief_slice: Optional[Dict[str, Any]] = None,
) -> str:
    missing_fields = [
        field_name
        for field_name, value in raw_data.items()
        if value in (None, {}, [])
    ]
    missing_text = "无" if not missing_fields else ", ".join(missing_fields)

    brief_section = ""
    if intel_brief_slice:
        brief_section = "\n\n" + format_brief_for_prompt(intel_brief_slice)

    # 结构化网络情报明细仅给情报员（与 CLI build_report 一致）；其他角色依赖 Brief 切片以免注意力分散
    intel_section = ""
    if web_intelligence and agent_role == "intelligence":
        intel_items = []
        list_keys = ("news", "research", "sentiment", "industry", "macro")
        for intel_type in list_keys:
            items = web_intelligence.get(intel_type)
            if items and isinstance(items, list):
                type_label = {
                    "news": "最新新闻",
                    "research": "研报",
                    "sentiment": "舆情",
                    "industry": "行业动态",
                    "macro": "宏观信息",
                }.get(intel_type, intel_type)
                cap = 8
                for item in items[:cap]:
                    if isinstance(item, dict):
                        title = item.get("title", "")
                        summary = item.get("summary", item.get("snippet", ""))
                        time_str = item.get("time", item.get("date", ""))
                        cred = item.get("credibility") or {}
                        cred_note = ""
                        if isinstance(cred, dict) and cred.get("score") is not None:
                            cred_note = f" [可信度{cred.get('score')}]"
                        warn = item.get("warning")
                        wnote = f" ⚠{warn}" if warn else ""
                        intel_items.append(
                            f"  [{type_label}]{cred_note}{wnote} {title} "
                            f"{'(' + str(time_str) + ')' if time_str else ''}\n    {summary}"
                        )
                    else:
                        intel_items.append(f"  [{type_label}] {item}")
        summary_bits = []
        if web_intelligence.get("overall_sentiment"):
            summary_bits.append(f"整体情绪: {web_intelligence.get('overall_sentiment')}")
        if web_intelligence.get("key_positive"):
            summary_bits.append("利好要点: " + "；".join(str(x) for x in (web_intelligence.get("key_positive") or [])[:3]))
        if web_intelligence.get("key_negative"):
            summary_bits.append("利空要点: " + "；".join(str(x) for x in (web_intelligence.get("key_negative") or [])[:3]))
        head = "\n".join(summary_bits) if summary_bits else ""
        if intel_items:
            intel_section = (
                f"\n\n网络情报结构化报告（已做时效/可信度过滤，条目明细如下）：\n{head}\n"
                + "\n".join(intel_items)
            )
        elif head:
            intel_section = f"\n\n网络情报结构化报告：\n{head}"

    role_focus = ""
    if agent_role == "intelligence":
        role_focus = "\n你是情报员：请重点把「Brief 叙事」与「资金流向/北向/新闻明细」交叉验证，在 analysis 中写明依据类型（盘面/舆情/研报）。"
    elif agent_role == "technical":
        role_focus = "\n你是技术分析员：Brief 仅辅助事件与情绪背景，交易结论须以量价结构为主。"
    elif agent_role == "fundamental":
        role_focus = "\n你是基本面分析员：Brief 中的研报数字须与财报/估值原始数据核对，不得单独采信。"
    elif agent_role == "risk":
        role_focus = "\n你是风控官：优先审视 Brief 风险标记与规则引擎红线，给出可执行风控结论。"

    return f"""你是 {agent_name}，负责{role_name}。
{role_focus}

请基于以下股票信息输出结构化 JSON，不要输出额外解释。

股票信息：
- 股票代码: {stock_code}
- 股票名称: {stock_name}
- 当前价格: {current_price}
{brief_section}

真实原始数据（以下字段为空表示当前未获取到真实数据）：
{json.dumps(raw_data, ensure_ascii=False, indent=2)}

关键缺失字段：{missing_text}

规则引擎参考（仅供参考，不可当作原始事实）：
{json.dumps(rule_reference, ensure_ascii=False, indent=2)}{intel_section}

请优先依据真实原始数据分析；如果关键数据缺失，请在结论中明确说明"数据不足"。

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
            "score": role_reference.get("score"),
            "comment": role_reference.get("comment") or "",
            "key_points": role_reference.get("key_points") or [],
            "risk_points": role_reference.get("risk_points") or [],
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


def _list_llm_data_gaps(full_data: Dict[str, Any], current_price: Any) -> List[str]:
    """标出主要原始数据缺口，供日志与 API 元信息（不伪造事实）。"""
    gaps: List[str] = []
    if current_price in (None, ""):
        gaps.append("current_price")
    if not _as_dict(full_data.get("quote")):
        gaps.append("quote")
    if not _as_dict(full_data.get("technical")):
        gaps.append("technical")
    if not _as_dict(full_data.get("financial")):
        gaps.append("financial")
    if not _as_list(full_data.get("news")):
        gaps.append("news")
    return gaps


def _normalize_chart_key_levels(raw: Any) -> List[Dict[str, Any]]:
    """统一关键价位结构，供 K 线图 markLine 与前端药丸使用。"""
    out: List[Dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    kind_alias = {"支撑": "support", "阻力": "resistance", "压力": "resistance"}
    for item in raw[:8]:
        if not isinstance(item, dict):
            continue
        try:
            pf = float(item.get("price"))
        except (TypeError, ValueError):
            continue
        if pf <= 0:
            continue
        kind = str(item.get("kind") or item.get("type") or "other").lower()
        if kind in kind_alias:
            kind = kind_alias[kind]
        label = item.get("label") or item.get("name") or kind
        out.append({"kind": kind, "price": round(pf, 4), "label": str(label)[:48]})
    return out


def _chart_key_levels_from_technical(technical: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从规则引擎技术指标生成关键价位（与 K 线支撑阻力同源）。"""
    out: List[Dict[str, Any]] = []
    if not technical:
        return out
    for i, p in enumerate(technical.get("support_levels") or []):
        try:
            pf = float(p)
            if pf > 0:
                out.append({"kind": "support", "price": round(pf, 4), "label": f"规则支撑{i + 1}"})
        except (TypeError, ValueError):
            pass
    for i, p in enumerate(technical.get("resistance_levels") or []):
        try:
            pf = float(p)
            if pf > 0:
                out.append({"kind": "resistance", "price": round(pf, 4), "label": f"规则阻力{i + 1}"})
        except (TypeError, ValueError):
            pass
    return out[:8]


def _build_llm_analysis_data(stock_code: str, rule_decision) -> Dict[str, Any]:
    execution = getattr(rule_decision, "execution", {}) or {}
    full_data = data_fetcher.get_full_data(stock_code) or {}
    if "news" not in full_data:
        full_data["news"] = data_fetcher.get_news(stock_code, limit=5) or []

    current_price = _resolve_current_price(full_data, execution)
    role_payloads = _build_role_payloads(stock_code, full_data, current_price)
    rule_reference = _build_rule_reference(rule_decision)
    data_gaps = _list_llm_data_gaps(full_data, current_price)

    return {
        "stock_code": stock_code,
        "current_price": current_price,
        "full_data": full_data,
        "role_payloads": role_payloads,
        "rule_reference": rule_reference,
        "data_gaps": data_gaps,
    }


def _serialize_agent_report(report: AgentReport, icon: str, round_number: int) -> Dict[str, Any]:
    payload = report.to_dict()
    payload["icon"] = icon
    payload["round"] = round_number
    return payload


def _round1_divergence_meta(reports: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """从第一轮评分中提取最大分歧双方，供讨论引导与前端高亮。"""
    if len(reports) < 2:
        return None
    scored: List[tuple] = []
    for r in reports:
        try:
            sc = float(r.get("score") or 0)
        except (TypeError, ValueError):
            sc = 0.0
        scored.append((r, sc))
    scored.sort(key=lambda x: x[1], reverse=True)
    hi_r, hi_s = scored[0]
    lo_r, lo_s = scored[-1]
    spread = hi_s - lo_s
    if spread < 0.25:
        return None
    return {
        "high_agent": hi_r.get("agent_name", ""),
        "high_role": hi_r.get("agent_role", ""),
        "high_score": round(hi_s, 1),
        "low_agent": lo_r.get("agent_name", ""),
        "low_role": lo_r.get("agent_role", ""),
        "low_score": round(lo_s, 1),
        "spread": round(spread, 1),
    }


def _divergence_prompt_suffix(meta: Optional[Dict[str, Any]]) -> str:
    if not meta:
        return ""
    return (
        "\n【程序标注·分歧焦点】"
        f"{meta['high_agent']}（{meta['high_score']:.1f} 分）与 "
        f"{meta['low_agent']}（{meta['low_score']:.1f} 分）差距最大（{meta['spread']:.1f} 分）。"
        "请点名引导双方对齐依据，并邀请其他角色补充或表态。\n"
    )


def _clip_text(text: str, max_len: int = 500) -> str:
    t = (text or "").strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


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
    current_price: Any = None,
    data_uses_mock: bool = False,
    data_gaps: Optional[List[str]] = None,
    fallback_chart_key_levels: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    leader_score = leader_report.score if leader_report.score is not None else 0.0
    final_action = _normalize_final_action(
        leader_report.metadata.get("decision") if leader_report.metadata else None,
        leader_score,
    )
    meta_levels = _normalize_chart_key_levels(
        (leader_report.metadata or {}).get("chart_key_levels")
    )
    chart_key_levels = meta_levels if meta_levels else (fallback_chart_key_levels or [])

    return {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "current_price": current_price,
        "data_uses_mock": data_uses_mock,
        "data_gaps": data_gaps or [],
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
        "chart_key_levels": chart_key_levels,
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
                "weighted_score": round(
                    (r.get("score") or 0) * LLM_ROLE_WEIGHTS.get(r["agent_role"], 0), 2
                ),
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
        post_fd = data_fetcher.get_full_data(stock_code) or {}
        ex = decision.execution or {}
        result_data['current_price'] = _resolve_current_price(post_fd, ex)
        result_data['data_uses_mock'] = data_fetcher.is_mock_data(stock_code)
        result_data['data_gaps'] = _list_llm_data_gaps(post_fd, result_data['current_price'])
        tech_fd = post_fd.get("technical") or {}
        result_data["chart_key_levels"] = _chart_key_levels_from_technical(
            tech_fd if isinstance(tech_fd, dict) else {}
        )
        
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
    """获取 LLM 配置，统一复用正式配置加载器。

    当 default_provider 为 openai_compatible 时，可用 .env 覆盖 YAML：
    - OPENAI_BASE_URL：API 根地址（未设置则使用 llm_config.yaml 中的 base_url）
    - OPENAI_MODEL：模型名（未设置则使用 yaml 中的 model）
    API Key 仍由 yaml 的 api_key_env（一般为 OPENAI_API_KEY）从环境变量读取。
    """
    import os

    from config.config_loader import get_llm_config as get_project_llm_config

    loader = get_project_llm_config()
    provider = loader.get_provider()
    provider_name = loader.default_provider

    base_url = provider.base_url
    model = provider.model
    if provider_name == "openai_compatible":
        env_base = (os.environ.get("OPENAI_BASE_URL") or "").strip()
        if env_base:
            base_url = env_base
        env_model = (os.environ.get("OPENAI_MODEL") or "").strip()
        if env_model:
            model = env_model

    return {
        "api_key": provider.api_key or "",
        "base_url": base_url,
        "provider": provider_name,
        "model": model,
        "temperature": provider.temperature,
        "max_tokens": provider.max_tokens,
    }


async def generate_sse_events(
    stock_code: str,
    stock_name: str,
    force_refresh: bool = False,
    user_request: str = "",
):
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
            max_tokens=2000,
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
        uses_mock = data_fetcher.is_mock_data(stock_code)
        if analysis_data.get("data_gaps"):
            _analyze_logger.info(
                "LLM 分析 %s 数据缺口: %s", stock_code, analysis_data.get("data_gaps")
            )

        # 发送规则引擎分析完成事件
        rule_analysis_payload = {
            "status": "complete",
            "data": {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "composite_score": rule_decision.composite_score,
                "final_action": rule_decision.final_action,
                "data_uses_mock": uses_mock,
                "data_gaps": analysis_data.get("data_gaps", []),
            },
        }
        yield f"event: rule_analysis\ndata: {json.dumps(rule_analysis_payload)}\n\n"
        
        await asyncio.sleep(0.5)
        
        # ===== 注入缓存情报（与 CLI 对齐：build_report + IntelBrief）=====
        cached_intel_data = None
        intel_cache_meta = None
        try:
            from utils.intel_cache import get_intel

            raw_intel = get_intel(
                stock_code=stock_code,
                stock_name=stock_name,
                force_refresh=force_refresh,
            )
            intel_cache_meta = raw_intel.pop("_cache_meta", None)
            tracked_at = str(raw_intel.get("tracked_at") or "")

            has_lists = cache_intel_has_search_lists(raw_intel)
            has_legacy = any(
                raw_intel.get(k) for k in ["news", "research", "sentiment", "industry", "macro"]
            )
            if has_lists:
                pkg = prepare_intel_package_for_analysis(
                    stock_code,
                    stock_name,
                    raw_intel,
                    tracked_at=tracked_at,
                    user_request=user_request or "中短线波段交易分析",
                )
                if pkg:
                    intel_report_dict, intel_brief = pkg
                    analysis_data["web_intelligence"] = intel_report_dict
                    analysis_data["intel_brief"] = intel_brief
                    cached_intel_data = raw_intel
                else:
                    analysis_data["web_intelligence"] = raw_intel
                    cached_intel_data = raw_intel
            elif has_legacy:
                analysis_data["web_intelligence"] = raw_intel
                cached_intel_data = raw_intel
        except Exception:
            pass

        # 发送情报注入事件
        if cached_intel_data and intel_cache_meta:
            wr = analysis_data.get("web_intelligence") or {}
            intel_summary = {
                "stock_code": stock_code,
                "news_count": len(cached_intel_data.get("news", [])),
                "research_count": len(cached_intel_data.get("research", [])),
                "sentiment_count": len(cached_intel_data.get("sentiment", [])),
                "cache_status": "fresh"
                if intel_cache_meta.get("is_fresh")
                else "stale"
                if intel_cache_meta.get("is_stale")
                else "expired",
                "cache_age_days": intel_cache_meta.get("age_days"),
                "intel_report": bool(wr.get("gather_time")),
                "overall_sentiment": wr.get("overall_sentiment"),
                "intel_brief": bool(analysis_data.get("intel_brief")),
            }
            yield f"event: intel_injected\ndata: {json.dumps(intel_summary)}\n\n"
            await asyncio.sleep(0.3)

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
            
            # 准备分析提示词（Brief 分角色裁剪 + 结构化情报仅给情报员）
            ib_full = analysis_data.get("intel_brief")
            intel_brief_slice = (
                slice_brief_for_agent_role(ib_full, role) if ib_full else None
            )
            raw_data = analysis_data["role_payloads"].get(role, {})
            raw_data = _trim_role_payload_for_llm(role, raw_data, bool(intel_brief_slice))
            rule_reference = analysis_data["rule_reference"].get(role, {})
            web_intel_for_prompt = (
                analysis_data.get("web_intelligence") if role == "intelligence" else None
            )
            prompt = _build_llm_agent_prompt(
                agent_name=agent.name,
                role_name=agent_configs.get(role, {}).get("name", role),
                stock_code=stock_code,
                stock_name=stock_name,
                current_price=analysis_data.get("current_price", "N/A"),
                raw_data=raw_data,
                rule_reference=rule_reference,
                web_intelligence=web_intel_for_prompt,
                agent_role=role,
                intel_brief_slice=intel_brief_slice,
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
                        'score': 0.0,
                        'confidence': 0.2,
                        'summary': (
                            f"[模型输出未解析为结构化结果] {analysis_text[:80]}"
                            if analysis_text
                            else "模型输出未解析为结构化结果"
                        ),
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
        
        diverge_meta = _round1_divergence_meta(round1_reports)
        if diverge_meta:
            yield f"event: discussion_focus\ndata: {json.dumps(diverge_meta)}\n\n"
            await asyncio.sleep(0.2)
        
        # Leader发起讨论（自然语言主持，与最终 JSON 决策分离）
        leader = team.get("leader")
        if leader:
            discussion_prompt = f"""股票 {stock_name}({stock_code}) 分析团队讨论开始。

各分析师的初步意见：
{chr(10).join([f"- {r['agent_name']}: 评分 {r.get('score') if r.get('score') is not None else 0}分，{r['summary']}" for r in round1_reports])}
{_divergence_prompt_suffix(diverge_meta)}
请主持本轮讨论：帮助团队对齐共识、澄清分歧，必要时提出追问。本环节仅输出可读中文，不要输出 JSON。
"""
            
            try:
                if hasattr(leader, "facilitate_discussion"):
                    leader_content = await asyncio.to_thread(
                        leader.facilitate_discussion, discussion_prompt
                    )
                else:
                    leader_report = await asyncio.to_thread(leader.analyze, discussion_prompt)
                    leader_content = (
                        leader_report.analysis
                        if isinstance(leader_report, AgentReport)
                        else str(leader_report)
                    )

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
                
                # 各Agent回应（自然语言 discuss_reply，避免 JSON 套娃）
                round2_lines: List[str] = []
                for report in round1_reports:
                    role = report['agent_role']
                    agent = team.get(role)
                    if not agent:
                        continue
                    
                    response_prompt = f"""你是 {report['agent_name']}。队长讨论引导如下：

{_clip_text(leader_content, 2000)}

请基于你的专业角度回应；若程序标出了分歧焦点，请明确表态是否认同、依据何在。"""
                    
                    try:
                        response_content = await asyncio.to_thread(
                            agent.discuss_reply, response_prompt
                        )

                        response_event = {
                            'round': 2,
                            'agent_name': report['icon'] + ' ' + report['agent_name'],
                            'agent_role': role,
                            'content': response_content,
                            'type': 'response'
                        }
                        discussion_messages.append(response_event)
                        round2_lines.append(
                            f"- {response_event['agent_name']}: {_clip_text(response_content, 400)}"
                        )
                        yield f"event: discussion\ndata: {json.dumps(response_event)}\n\n"
                        
                        await asyncio.sleep(0.3)
                        
                    except Exception as e:
                        error_payload = {
                            'agent': report['agent_name'],
                            'error': str(e)
                        }
                        yield f"event: error\ndata: {json.dumps(error_payload)}\n\n"

                # 队长收束：共识 / 未决分歧 / 待验证点（仍为非 JSON）
                if round2_lines and hasattr(leader, "facilitate_discussion"):
                    synthesis_prompt = f"""股票 {stock_name}({stock_code}) 第二轮讨论发言摘录：
队长开场：
{_clip_text(leader_content, 1200)}

各成员回应：
{chr(10).join(round2_lines)}

请用纯中文、编号列表输出（非 JSON）：
1) 共识要点（2～4 条）
2) 仍存分歧（1～3 条）
3) 决策前待验证点（1～2 条）
每条不超过 60 字。"""
                    try:
                        closing_content = await asyncio.to_thread(
                            leader.facilitate_discussion, synthesis_prompt
                        )
                        closing_event = {
                            'round': 2,
                            'agent_name': '👔 队长',
                            'agent_role': 'leader',
                            'content': closing_content,
                            'type': 'synthesis'
                        }
                        discussion_messages.append(closing_event)
                        yield f"event: discussion\ndata: {json.dumps(closing_event)}\n\n"
                    except Exception:
                        pass
                        
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': f'Leader讨论失败: {str(e)}'})}\n\n"
        
        await asyncio.sleep(0.5)
        
        # ===== 第三轮：达成共识 =====
        yield f"event: round_start\ndata: {json.dumps({'round': 3, 'type': 'consensus', 'title': '🤝 第三轮：达成共识'})}\n\n"
        
        ib = analysis_data.get("intel_brief")
        brief_json = ""
        if ib:
            brief_json = json.dumps(ib, ensure_ascii=False, indent=2)
            if len(brief_json) > 12000:
                brief_json = brief_json[:12000] + "\n…(IntelBrief 已截断)"

        final_prompt = f"""你是投资决策队长，请基于以下信息输出最终 JSON 决策，不要输出额外解释。

股票信息：
- 股票代码: {stock_code}
- 股票名称: {stock_name}

情报共识摘要（IntelBrief，全队共享，须与各专业分析交叉验证）：
{brief_json if brief_json else "- 本轮无结构化情报摘要"}

第一轮独立分析：
{chr(10).join([f"- {r['agent_name']}({r['agent_role']}): 评分 {float(r.get('score') or 0):.1f}，摘要：{r['summary']}，分析：{r['analysis']}" for r in round1_reports])}

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
  "position_ratio": 建议仓位百分比,
  "chart_key_levels": [
    {{"kind": "support", "price": 数字, "label": "如前低/MA20 等简短说明"}},
    {{"kind": "resistance", "price": 数字, "label": "如前高/缺口上沿等"}}
  ]
}}
chart_key_levels 为可选，最多 6 条，价格须与技术分析员支撑/压力或基本面估值可追溯；无明确价位时填 []。"""

        final_decision = None
        if leader:
            try:
                final_report = await asyncio.to_thread(leader.analyze, final_prompt)
                if isinstance(final_report, AgentReport):
                    fb_lv = _chart_key_levels_from_technical(
                        _as_dict((analysis_data.get("full_data") or {}).get("technical"))
                    )
                    final_decision = _build_final_decision(
                        stock_code=stock_code,
                        stock_name=stock_name,
                        rule_decision=rule_decision,
                        round1_reports=round1_reports,
                        leader_report=final_report,
                        current_price=analysis_data.get("current_price"),
                        data_uses_mock=uses_mock,
                        data_gaps=analysis_data.get("data_gaps"),
                        fallback_chart_key_levels=fb_lv,
                    )
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': f'Leader最终决策失败: {str(e)}'})}\n\n"

        if final_decision is None:
            raw_scores = [float(r.get("score") or 0) for r in round1_reports]
            fallback_score = sum(raw_scores) / len(raw_scores) if raw_scores else 0.0
            fallback_action = _normalize_final_action(None, fallback_score)
            fb_chart_levels = _chart_key_levels_from_technical(
                _as_dict((analysis_data.get("full_data") or {}).get("technical"))
            )
            final_decision = {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'current_price': analysis_data.get("current_price"),
                'data_uses_mock': uses_mock,
                'data_gaps': analysis_data.get("data_gaps", []),
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
                'chart_key_levels': fb_chart_levels,
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
                    'weighted_score': round(
                        (float(r.get("score") or 0)) * LLM_ROLE_WEIGHTS.get(r['agent_role'], 0), 2
                    ),
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
            generate_sse_events(
                stock_code,
                stock_name,
                force_refresh=request.force_refresh,
                user_request=request.user_request or "",
            ),
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
