"""
网络情报 LLM 简要解读：固定 JSON 输出、磁盘缓存、与 gather_time/tracked_at 联动失效。

与「情报员」产品语义一致，仅基于所给 Brief/标题摘要，不替代投资建议。
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional

from config.project_paths import ensure_project_root_on_path

ensure_project_root_on_path()

from utils.logger import get_logger

logger = get_logger("intel_llm_interpret")

INTERPRET_CACHE_DIR = os.path.join("data", "intel", "llm_interpret")

# 与 LLM 约定单一 JSON 对象字段（与 Mock 可识别关键词配合）
INTERPRET_USER_TAG = "【网络情报简要解读任务】"

INTERPRET_SYSTEM = """【角色】你是投研团队「市场情报员」，仅就本次提供的「规则型情报摘要 + 条目标题/摘要」做简要解读。

【铁律】
1. 只根据输入中已出现的信息归纳，禁止编造公司名、数字、日期、未提供的传闻。
2. 禁止给出明确买入/卖出/目标价等投资建议；可描述舆情与信息结构上的偏多/偏空/分歧。
3. 严格只输出一个 JSON 对象，无 Markdown 代码块、无其他文字。

【输出 JSON 字段】
- summary_text: string，3～6 句中文连贯叙述
- bullets: string 数组，3～5 条短句要点
- stance: 只能是以下之一：「偏谨慎偏多」「偏谨慎偏空」「观望」「信息不足」（信息单薄时用）
- confidence: 0 到 1 之间小数，表示对「解读仅覆盖当前输入」的把握（非对股价的判断）
- disclaimer: 固定短句，说明本解读基于当前抓取、非投资建议

schema_version 固定为 \"llm_interpret_v1\"
"""


def _brief_signature(brief: Dict[str, Any]) -> str:
    """用于缓存键的 Brief 子集，排除机器可读的大字段。"""
    keys = (
        "schema_version",
        "core_thesis",
        "overall_sentiment",
        "catalysts",
        "risk_flags",
        "open_questions",
    )
    sub = {k: brief.get(k) for k in keys}
    bull = brief.get("bull_case") or []
    bear = brief.get("bear_case") or []
    if isinstance(bull, list):
        sub["bull_claims"] = [
            (b.get("claim") if isinstance(b, dict) else str(b))[:200] for b in bull[:4]
        ]
    if isinstance(bear, list):
        sub["bear_claims"] = [
            (b.get("claim") if isinstance(b, dict) else str(b))[:200] for b in bear[:4]
        ]
    return json.dumps(sub, ensure_ascii=False, sort_keys=True)


def _cache_filename(
    stock_code: str, gather_time: str, tracked_at: str, sig_hash: str, force_key: int
) -> str:
    raw = f"{stock_code}|{gather_time}|{tracked_at}|{sig_hash}|{force_key}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"{stock_code}_{h}.json"


def _sample_titles(intel_report: Dict[str, Any], per_type: int = 2) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for key in ("news", "research", "sentiment", "industry", "macro"):
        items = intel_report.get(key)
        if not isinstance(items, list):
            continue
        titles: List[str] = []
        for it in items[:per_type]:
            if isinstance(it, dict) and it.get("title"):
                titles.append(str(it["title"])[:120])
        if titles:
            out[key] = titles
    return out


def _build_user_content(
    stock_code: str,
    stock_name: str,
    intel_brief: Dict[str, Any],
    intel_report: Optional[Dict[str, Any]],
) -> str:
    report = intel_report or {}
    sample = _sample_titles(report, 2)
    payload = {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "rule_intel_brief": {
            "core_thesis": intel_brief.get("core_thesis"),
            "overall_sentiment": intel_brief.get("overall_sentiment"),
            "catalysts": (intel_brief.get("catalysts") or [])[:8],
            "risk_flags": (intel_brief.get("risk_flags") or [])[:8],
            "open_questions": (intel_brief.get("open_questions") or [])[:5],
        },
        "item_titles_by_type": sample,
    }
    return (
        f"{INTERPRET_USER_TAG}\n"
        f"请基于下列 JSON 完成解读，勿引入外部知识：\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


def _resolve_llm_runtime_kwargs() -> Dict[str, Any]:
    import os

    from config.config_loader import get_llm_config

    loader = get_llm_config()
    provider_name = loader.default_provider
    provider = loader.get_provider()
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
        "temperature": min(0.5, float(provider.temperature or 0.7)),
        "max_tokens": min(900, int(provider.max_tokens or 2000)),
    }


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    if not text or not str(text).strip():
        return None
    t = str(text).strip()
    a, b = t.find("{"), t.rfind("}")
    if a == -1 or b <= a:
        return None
    try:
        return json.loads(t[a : b + 1])
    except json.JSONDecodeError:
        return None


def _normalize_interpretation(raw: Dict[str, Any], intel_brief: Dict[str, Any]) -> Dict[str, Any]:
    stance_choices = ("偏谨慎偏多", "偏谨慎偏空", "观望", "信息不足")
    stance = raw.get("stance")
    if stance not in stance_choices:
        o = intel_brief.get("overall_sentiment") or "neutral"
        if o in ("positive", "乐观", "偏多"):
            stance = "偏谨慎偏多"
        elif o in ("negative", "悲观", "偏空"):
            stance = "偏谨慎偏空"
        elif o in ("insufficient", "信息不足"):
            stance = "信息不足"
        else:
            stance = "观望"
    conf = raw.get("confidence")
    try:
        c = float(conf)
        c = max(0.0, min(1.0, c))
    except (TypeError, ValueError):
        c = 0.45
    bullets = raw.get("bullets")
    if not isinstance(bullets, list):
        bullets = []
    bullets = [str(b).strip() for b in bullets if b][:5]
    st = raw.get("summary_text")
    if not isinstance(st, str) or not st.strip():
        st = (intel_brief.get("core_thesis") or "").strip() or "当前输入下可归纳的信息有限，请以规则摘要与原文链接为准。"
    disc = raw.get("disclaimer")
    if not isinstance(disc, str) or not disc.strip():
        disc = "本解读仅基于当前抓取与规则摘要，不构成投资建议。"
    return {
        "schema_version": "llm_interpret_v1",
        "summary_text": st.strip(),
        "bullets": bullets,
        "stance": stance,
        "confidence": c,
        "disclaimer": disc.strip(),
        "source": raw.get("source") or "llm_v1",
    }


def _rule_fallback(brief: Dict[str, Any]) -> Dict[str, Any]:
    cats = (brief.get("catalysts") or [])[:3]
    risks = (brief.get("risk_flags") or [])[:2]
    bullets = [str(x) for x in cats + risks if x][:5]
    if len(bullets) < 3 and brief.get("core_thesis"):
        bullets = [str(brief.get("core_thesis"))[:160]] + bullets
    return {
        "schema_version": "llm_interpret_v1",
        "summary_text": (brief.get("core_thesis") or "暂无规则摘要，无法深度解读。").strip(),
        "bullets": bullets[:5] if bullets else ["请尝试刷新后重新拉取情报。"],
        "stance": "信息不足" if not brief.get("core_thesis") else "观望",
        "confidence": 0.25,
        "disclaimer": "本段为规则摘要的机械整理，非模型生成；不构成投资建议。",
        "source": "rule_fallback",
    }


def get_or_create_llm_interpretation(
    intel_brief: Dict[str, Any],
    intel_report: Optional[Dict[str, Any]],
    stock_code: str,
    stock_name: str,
    tracked_at: str = "",
    gather_time: str = "",
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    返回标准 interpretation dict；若 LLM 不可用或失败，回退为规则整理。
    """
    gather_time = gather_time or (intel_report or {}).get("gather_time") or ""
    sig = _brief_signature(intel_brief)
    sig_hash = hashlib.sha256(sig.encode("utf-8")).hexdigest()[:20]
    force_key = 1 if force_refresh else 0
    os.makedirs(INTERPRET_CACHE_DIR, exist_ok=True)
    fname = _cache_filename(stock_code, gather_time, tracked_at, sig_hash, force_key)
    path = os.path.join(INTERPRET_CACHE_DIR, fname)

    if not force_refresh and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if isinstance(cached, dict) and cached.get("summary_text"):
                return cached
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("读取 LLM 解读缓存失败: %s", e)

    user_content = _build_user_content(stock_code, stock_name, intel_brief, intel_report)
    out: Optional[Dict[str, Any]] = None
    try:
        from llm import get_provider
        from llm.base_provider import ChatMessage

        cfg = _resolve_llm_runtime_kwargs()
        prov = get_provider(
            cfg["provider"],
            api_key=cfg["api_key"] or None,
            base_url=cfg["base_url"],
            model=cfg["model"],
        )
        messages = [
            ChatMessage(role="system", content=INTERPRET_SYSTEM),
            ChatMessage(role="user", content=user_content),
        ]
        resp = prov.chat_with_history(
            messages=messages,
            temperature=cfg["temperature"],
            max_tokens=cfg["max_tokens"],
        )
        text = (resp.content or "").strip()
        raw = _extract_json_object(text)
        if raw:
            out = _normalize_interpretation(raw, intel_brief)
            out["source"] = "llm_v1"
    except Exception as e:
        logger.warning("LLM 解读调用失败: %s", e)

    if not out or not out.get("summary_text"):
        out = _rule_fallback(intel_brief)

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.warning("写入 LLM 解读缓存失败: %s", e)

    return out


__all__ = [
    "get_or_create_llm_interpretation",
    "INTERPRET_CACHE_DIR",
    "INTERPRET_USER_TAG",
]
