"""
基于观察池已记录信号与价格快照，生成简要的信号后验摘要（非完整回测引擎）。
供策略迭代与 API 展示使用。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .performance_tracker import PerformanceTracker


def build_signal_outcome_summary(
    tracker: PerformanceTracker,
    *,
    limit_closed: int = 30,
) -> Dict[str, Any]:
    """
    汇总已平仓的买入类信号与未平仓/观察类信号的近期表现，便于与当时 AI 建议对照。

    Returns:
        closed_buy: 已平仓的 buy 类信号摘要列表（按时间倒序截断 limit_closed）
        open_buy: 未平仓的 buy 类信号
        last_update: 价格/信号数据更新时间
    """
    signals: List[Dict[str, Any]] = list(tracker.signal_history.signals)
    # 新在前
    signals_sorted = sorted(
        signals,
        key=lambda s: (s.get("signal_date") or "", s.get("code") or ""),
        reverse=True,
    )

    buy_closed: List[Dict[str, Any]] = []
    buy_open: List[Dict[str, Any]] = []

    for s in signals_sorted:
        if s.get("signal_type") != "buy":
            continue
        code = s.get("code", "")
        entry = s.get("entry_price")
        row: Dict[str, Any] = {
            "code": code,
            "name": s.get("name", ""),
            "signal_date": s.get("signal_date"),
            "entry_price": entry,
            "exit_date": s.get("exit_date"),
            "exit_price": s.get("exit_price"),
            "exit_reason": s.get("exit_reason"),
            "actual_return": s.get("actual_return"),
            "holding_days": s.get("holding_days"),
        }
        if s.get("exit_date"):
            buy_closed.append(row)
        else:
            last_px = tracker.get_current_price(code)
            floating = None
            if last_px and entry:
                try:
                    floating = round((float(last_px) - float(entry)) / float(entry) * 100, 2)
                except (TypeError, ValueError, ZeroDivisionError):
                    floating = None
            row["mark_price"] = last_px
            row["floating_return_pct"] = floating
            buy_open.append(row)

    closed_out = buy_closed[:limit_closed]

    closed_returns = [x["actual_return"] for x in closed_out if x.get("actual_return") is not None]
    win_count = sum(1 for r in closed_returns if r and r > 0)
    n = len(closed_returns)
    win_rate = round(win_count / n, 4) if n else None
    avg_ret = (
        round(sum(closed_returns) / n, 4) if n else None
    )

    return {
        "summary": {
            "closed_buy_count": len(buy_closed),
            "open_buy_count": len(buy_open),
            "win_rate_closed": win_rate,
            "avg_return_closed_pct": avg_ret,
        },
        "closed_buy": closed_out,
        "open_buy": buy_open[:50],
        "last_update": getattr(tracker.price_history, "update_time", None)
        or getattr(tracker.signal_history, "update_time", None),
    }
