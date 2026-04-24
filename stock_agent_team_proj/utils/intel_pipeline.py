"""
情报管线：SSE/CLI 对齐 —— 原始缓存 → WebIntelligenceGatherer.build_report → 结构化报告；
并生成规则型 IntelBrief（可磁盘缓存，键随 gather_time + tracked_at 失效）。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from agents.web_intelligence.gatherer import WebIntelligenceGatherer
from utils.logger import get_logger

logger = get_logger("intel_pipeline")

INTEL_SEARCH_KEYS = ("news", "research", "sentiment", "industry", "macro")
INTEL_BRIEF_CACHE_DIR = os.path.join("data", "intel", "briefs")

# IntelBrief（字典结构，便于 JSON 与 LLM 注入）
# - schema_version: str
# - stock_code, stock_name
# - source: "rule_based_v1"
# - core_thesis: str
# - overall_sentiment: str  # 与报告一致
# - bull_case / bear_case: List[{"claim": str, "evidence_refs": [{"ref_id", "title_snippet"}]}]
# - key_numbers: List[{"label", "value", "unit", "source_hint"}]
# - catalysts: List[str]
# - risk_flags: List[str]
# - open_questions: List[str]
# - role_hints: Dict[role, List[str]]  role in technical|fundamental|risk|intelligence|leader
# - institutional_one_liners: List[str]


def raw_intel_to_search_payload(raw_intel: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """从 intel 缓存/搜索结构提取 build_report 可用的 {type: [items]}。"""
    payload: Dict[str, List[Dict[str, Any]]] = {}
    for key in INTEL_SEARCH_KEYS:
        items = raw_intel.get(key)
        if isinstance(items, list) and items:
            payload[key] = items
    return payload


def cache_intel_has_search_lists(raw_intel: Dict[str, Any]) -> bool:
    return bool(raw_intel_to_search_payload(raw_intel))


def build_intel_report_dict(
    stock_code: str,
    stock_name: str,
    raw_intel: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    对原始情报列表执行与 CLI 一致的 build_report（时效/可信度/综合字段）。
    若无可用列表则返回 None。
    """
    payload = raw_intel_to_search_payload(raw_intel)
    if not payload:
        return None
    gatherer = WebIntelligenceGatherer()
    report = gatherer.build_report(stock_code, stock_name, payload)
    return report.to_dict()


def _brief_cache_filename(stock_code: str, gather_time: str, tracked_at: str) -> str:
    key = f"{stock_code}|{gather_time}|{tracked_at}"
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    return f"{stock_code}_{h}.json"


def _extract_key_numbers(items: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    """从研报类条目中粗提数字（启发式，非 NLP）。"""
    out: List[Dict[str, Any]] = []
    pat_target = re.compile(r"目标价[：:\s]*([\d.]+)\s*(?:元|港币|港元|美元)?", re.I)
    pat_price = re.compile(r"([\d]{1,3}(?:,\d{3})*(?:\.\d+)?|\d+\.\d+)\s*元")

    for item in items:
        if len(out) >= limit:
            break
        text = f"{item.get('title', '')} {item.get('summary', '')} {item.get('snippet', '')}"
        m = pat_target.search(text)
        if m:
            out.append(
                {
                    "label": "目标价(文本提取)",
                    "value": m.group(1).replace(",", ""),
                    "unit": "元或原文币种",
                    "source_hint": (item.get("title") or "")[:80],
                }
            )
            continue
        m2 = pat_price.search(text)
        if m2 and "目标" in text:
            out.append(
                {
                    "label": "价格提及",
                    "value": m2.group(1).replace(",", ""),
                    "unit": "元",
                    "source_hint": (item.get("title") or "")[:80],
                }
            )
    return out[:limit]


def build_rule_based_intel_brief(
    intel_report: Dict[str, Any],
    stock_code: str,
    stock_name: str,
    user_request: str = "",
) -> Dict[str, Any]:
    """基于结构化情报报告生成规则型 Brief（无 LLM，可追溯至报告字段）。"""
    ref_i = 0

    def next_ref() -> str:
        nonlocal ref_i
        ref_i += 1
        return f"R{ref_i}"

    overall = intel_report.get("overall_sentiment") or "neutral"
    hot_topics = intel_report.get("hot_topics") or []
    key_pos = intel_report.get("key_positive") or []
    key_neg = intel_report.get("key_negative") or []
    inst_views = intel_report.get("institutional_views") or []

    bull_case: List[Dict[str, Any]] = []
    for kp in key_pos[:6]:
        if not isinstance(kp, str):
            continue
        rid = next_ref()
        bull_case.append(
            {
                "claim": kp,
                "evidence_refs": [{"ref_id": rid, "title_snippet": kp[:72]}],
            }
        )

    bear_case: List[Dict[str, Any]] = []
    for kn in key_neg[:6]:
        if not isinstance(kn, str):
            continue
        rid = next_ref()
        bear_case.append(
            {
                "claim": kn,
                "evidence_refs": [{"ref_id": rid, "title_snippet": kn[:72]}],
            }
        )

    research_items = intel_report.get("research") or []
    if not isinstance(research_items, list):
        research_items = []
    key_numbers = _extract_key_numbers([x for x in research_items if isinstance(x, dict)])

    for iv in inst_views[:3]:
        if isinstance(iv, dict) and iv.get("summary"):
            key_numbers.append(
                {
                    "label": "机构摘要",
                    "value": (iv.get("summary") or "")[:120],
                    "unit": "文本",
                    "source_hint": (iv.get("title") or "")[:80],
                }
            )

    catalysts = list(hot_topics[:4])
    for x in key_pos[:2]:
        if isinstance(x, str) and x not in catalysts:
            catalysts.append(x[:60])

    risk_flags = [x for x in key_neg if isinstance(x, str)][:5]
    cred = intel_report.get("credibility_summary") or {}
    if isinstance(cred, dict):
        low_n = int(cred.get("low_credibility") or 0)
        high_n = int(cred.get("high_credibility") or 0)
        if low_n > high_n and low_n >= 2:
            risk_flags.append("低可信度来源条数偏高，需交叉验证")

    open_questions: List[str] = []
    if overall == "neutral" and key_pos and key_neg:
        open_questions.append("多空舆情并存，需结合量价与基本面判断主导矛盾")
    if user_request:
        open_questions.append(f"对照用户诉求复核：{user_request[:120]}")

    inst_lines = []
    for iv in inst_views[:4]:
        if isinstance(iv, dict):
            inst_lines.append(f"{iv.get('title', '')}: {(iv.get('summary') or '')[:100]}")

    thesis_parts = [f"{stock_name}({stock_code}) 情报面整体偏{overall}"]
    if hot_topics:
        thesis_parts.append("热点：" + " / ".join(hot_topics[:3]))
    core_thesis = "；".join(thesis_parts)

    role_hints = {
        "technical": [
            f"舆情与题材：{', '.join(hot_topics[:2])}" if hot_topics else "缺少热点题材条目，侧重量价结构本身",
            "事件驱动若密集，注意波动放大与假突破",
        ],
        "fundamental": [
            "将研报目标价/盈利预测与当前估值、财报数据交叉验证",
            *(inst_lines[:1] if inst_lines else ["机构观点有限，避免单条消息过度外推"]),
        ],
        "risk": [
            *(risk_flags[:3] if risk_flags else ["舆情风险未显著暴露，仍须核对规则引擎红线"]),
            "关注监管公告、减持、诉讼类硬风险是否被舆情掩盖",
        ],
        "intelligence": [
            "核对资金流向、北向与舆情方向是否一致",
            f"整体情绪 {overall}，重点跟踪 catalysts 是否已被定价",
        ],
        "leader": [
            "对齐四路 Agent 与 Brief 中的多空证据，明确主导逻辑",
            "分歧大时优先 watch，并要求各侧给出可溯源依据",
        ],
    }

    return {
        "schema_version": "intel_brief_v1",
        "stock_code": stock_code,
        "stock_name": stock_name,
        "source": "rule_based_v1",
        "core_thesis": core_thesis,
        "overall_sentiment": overall,
        "bull_case": bull_case,
        "bear_case": bear_case,
        "key_numbers": key_numbers,
        "catalysts": catalysts[:8],
        "risk_flags": risk_flags[:8],
        "open_questions": open_questions[:5],
        "role_hints": role_hints,
        "institutional_one_liners": inst_lines,
        "credibility_summary": cred,
        "freshness_summary": intel_report.get("freshness_summary") or {},
    }


def get_or_build_cached_intel_brief(
    intel_report: Dict[str, Any],
    stock_code: str,
    stock_name: str,
    tracked_at: str = "",
    user_request: str = "",
) -> Dict[str, Any]:
    """
    Brief 磁盘缓存：键 = stock_code + gather_time + tracked_at（内容变则自动失效）。
    """
    gather_time = intel_report.get("gather_time") or ""
    fname = _brief_cache_filename(stock_code, gather_time, tracked_at or "")
    os.makedirs(INTEL_BRIEF_CACHE_DIR, exist_ok=True)
    path = os.path.join(INTEL_BRIEF_CACHE_DIR, fname)

    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached.get("schema_version") and cached.get("core_thesis"):
                return cached
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("读取 Brief 缓存失败，将重建: %s", e)

    brief = build_rule_based_intel_brief(intel_report, stock_code, stock_name, user_request=user_request)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(brief, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.warning("写入 Brief 缓存失败: %s", e)

    return brief


def slice_brief_for_agent_role(brief: Dict[str, Any], agent_role: str) -> Dict[str, Any]:
    """供各 Agent 注入：公共摘要 + 该角色 hints + 精简 catalysts/risk。"""
    hints = (brief.get("role_hints") or {}).get(agent_role) or []
    return {
        "core_thesis": brief.get("core_thesis"),
        "overall_sentiment": brief.get("overall_sentiment"),
        "catalysts": (brief.get("catalysts") or [])[:5],
        "risk_flags": (brief.get("risk_flags") or [])[:5],
        "key_numbers": (brief.get("key_numbers") or [])[:4],
        "open_questions": (brief.get("open_questions") or [])[:3],
        "role_hints": hints,
    }


def prepare_intel_package_for_analysis(
    stock_code: str,
    stock_name: str,
    raw_intel: Dict[str, Any],
    tracked_at: str = "",
    user_request: str = "",
) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    一站式：原始缓存 → 结构化报告 dict + Brief。
    返回 (intel_report_dict, intel_brief)；无列表数据时返回 None。
    """
    report_dict = build_intel_report_dict(stock_code, stock_name, raw_intel)
    if not report_dict:
        return None
    brief = get_or_build_cached_intel_brief(
        report_dict,
        stock_code,
        stock_name,
        tracked_at=tracked_at,
        user_request=user_request,
    )
    return report_dict, brief


def format_brief_for_prompt(brief_slice: Dict[str, Any]) -> str:
    """转为可读中文块，用于 system/user 拼接。"""
    lines = [
        "【情报摘要 Brief】（由结构化情报报告规则提炼，证据见 ref；请与原始数据交叉验证）",
        f"- 核心叙事：{brief_slice.get('core_thesis')}",
        f"- 整体情绪：{brief_slice.get('overall_sentiment')}",
    ]
    cats = brief_slice.get("catalysts") or []
    if cats:
        lines.append("- 催化剂/热点：" + "；".join(str(c) for c in cats))
    risks = brief_slice.get("risk_flags") or []
    if risks:
        lines.append("- 风险标记：" + "；".join(str(r) for r in risks))
    kn = brief_slice.get("key_numbers") or []
    if kn:
        nums = []
        for item in kn:
            if isinstance(item, dict):
                nums.append(
                    f"{item.get('label')}={item.get('value')}{item.get('unit') or ''}"
                    f"（{item.get('source_hint', '')[:40]}）"
                )
        if nums:
            lines.append("- 关键数字：" + "；".join(nums))
    oq = brief_slice.get("open_questions") or []
    if oq:
        lines.append("- 待澄清：" + "；".join(str(x) for x in oq))
    rh = brief_slice.get("role_hints") or []
    if rh:
        lines.append("- 本角色关注：" + "；".join(str(h) for h in rh))
    return "\n".join(lines)
