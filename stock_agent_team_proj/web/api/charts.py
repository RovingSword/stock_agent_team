"""
图表数据 API
提供K线图、观察池汇总图和表现统计图的数据
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from config.project_paths import ensure_project_root_on_path

ensure_project_root_on_path()

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from watchlist import WatchlistManager, PerformanceTracker
from utils.data_fetcher import data_fetcher

router = APIRouter()

# ========== 辅助函数 ==========

def format_kline_data(kline_list: List) -> Dict[str, Any]:
    """格式化K线数据为ECharts格式"""
    dates = []
    opens = []
    highs = []
    lows = []
    closes = []
    volumes = []
    
    for k in kline_list:
        dates.append(k.get('date', ''))
        opens.append(k.get('open', 0))
        highs.append(k.get('high', 0))
        lows.append(k.get('low', 0))
        closes.append(k.get('close', 0))
        volumes.append(k.get('volume', 0))
    
    return {
        "dates": dates,
        "opens": opens,
        "highs": highs,
        "lows": lows,
        "closes": closes,
        "volumes": volumes
    }


# ========== API端点 ==========

@router.get("/charts/kline/{code}")
async def get_kline_chart(code: str, days: int = 60):
    """获取K线图数据"""
    try:
        # 获取K线数据
        kline_data = data_fetcher.get_daily_kline(code, days=days)
        
        if not kline_data or len(kline_data) == 0:
            return {
                "success": False,
                "message": f"无法获取 {code} 的K线数据"
            }
        
        # 格式化数据
        formatted = format_kline_data(kline_data)
        
        # 计算均线
        ma5 = calculate_ma(formatted["closes"], 5)
        ma10 = calculate_ma(formatted["closes"], 10)
        ma20 = calculate_ma(formatted["closes"], 20)
        
        # 识别支撑位和阻力位
        support, resistance = identify_support_resistance(formatted["highs"], formatted["lows"])
        
        return {
            "success": True,
            "data": {
                "code": code,
                "dates": formatted["dates"],
                "kline": {
                    "opens": formatted["opens"],
                    "highs": formatted["highs"],
                    "lows": formatted["lows"],
                    "closes": formatted["closes"],
                    "volumes": formatted["volumes"]
                },
                "ma": {
                    "ma5": ma5,
                    "ma10": ma10,
                    "ma20": ma20
                },
                "levels": {
                    "support": support,
                    "resistance": resistance
                }
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"获取K线数据失败: {str(e)}"
        }


def calculate_ma(closes: List[float], period: int) -> List[float]:
    """计算移动平均线"""
    ma = []
    for i in range(len(closes)):
        if i < period - 1:
            ma.append(None)
        else:
            avg = sum(closes[i - period + 1:i + 1]) / period
            ma.append(round(avg, 2))
    return ma


def identify_support_resistance(highs: List[float], lows: List[float]) -> tuple:
    """识别支撑位和阻力位"""
    if len(highs) < 20:
        return [], []
    
    # 取最近20天的数据
    recent_highs = sorted(highs[-20:])[-5:]
    recent_lows = sorted(lows[-20:])[:5]
    
    resistance = [round(h, 2) for h in recent_highs[-2:]]
    support = [round(l, 2) for l in recent_lows[:2]]
    
    return support, resistance


@router.get("/charts/watchlist")
async def get_watchlist_chart():
    """获取观察池汇总图数据"""
    try:
        manager = WatchlistManager()
        stats = manager.get_statistics()
        
        # 获取候选股列表
        candidates = manager.get_all_candidates()
        
        # 按状态分组统计
        status_counts = stats.get("by_status", {})
        
        # 评分分布
        score_ranges = {
            "0-60": 0,
            "60-70": 0,
            "70-80": 0,
            "80-90": 0,
            "90-100": 0
        }
        
        for c in candidates:
            score = c.composite_score or c.score or 0
            if score < 60:
                score_ranges["0-60"] += 1
            elif score < 70:
                score_ranges["60-70"] += 1
            elif score < 80:
                score_ranges["70-80"] += 1
            elif score < 90:
                score_ranges["80-90"] += 1
            else:
                score_ranges["90-100"] += 1
        
        # 来源分布
        source_counts = {}
        for c in candidates:
            source = c.source or "unknown"
            source_counts[source] = source_counts.get(source, 0) + 1
        
        return {
            "success": True,
            "data": {
                "total_count": len(candidates),
                "status_distribution": status_counts,
                "score_distribution": score_ranges,
                "source_distribution": source_counts,
                "buy_recommended": len(manager.get_buy_recommended()),
                "last_update": stats.get("last_update", "")
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"获取汇总图数据失败: {str(e)}"
        }


@router.get("/charts/performance")
async def get_performance_chart():
    """获取表现统计图数据"""
    try:
        tracker = PerformanceTracker()
        
        # 获取历史信号
        history = tracker.get_signal_history(limit=100)
        
        # 格式化信号数据
        signals = []
        cumulative_profit = 0.0
        cumulative_data = []
        
        for signal in sorted(history, key=lambda x: x.close_date or x.signal_date):
            profit_rate = signal.profit_rate or 0
            cumulative_profit += profit_rate
            
            signals.append({
                "code": signal.stock_code,
                "name": signal.stock_name,
                "entry_price": signal.entry_price,
                "exit_price": signal.exit_price,
                "profit_rate": round(profit_rate, 4),
                "cumulative_profit": round(cumulative_profit, 4),
                "signal_date": signal.signal_date,
                "close_date": signal.close_date,
                "holding_days": signal.holding_days,
                "is_profit": profit_rate > 0
            })
            
            cumulative_data.append({
                "date": signal.close_date or signal.signal_date,
                "value": round(cumulative_profit, 4)
            })
        
        # 获取统计
        stats = tracker.get_summary_stats()
        
        # 生成胜率饼图数据
        win_count = stats.get("winning_signals", 0)
        lose_count = stats.get("total_signals", 0) - win_count
        
        return {
            "success": True,
            "data": {
                "signals": signals,
                "cumulative_curve": cumulative_data,
                "summary": {
                    "total_signals": stats.get("total_signals", 0),
                    "win_rate": round(stats.get("win_rate", 0) * 100, 1),
                    "total_profit_rate": round(stats.get("total_profit_rate", 0) * 100, 2),
                    "win_count": win_count,
                    "lose_count": lose_count
                },
                "pie_data": [
                    {"name": "盈利", "value": win_count},
                    {"name": "亏损", "value": lose_count}
                ]
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"获取表现图数据失败: {str(e)}"
        }


@router.get("/charts/candlestick/{code}")
async def get_candlestick_data(code: str, days: int = 60):
    """获取蜡烛图数据（简化版）"""
    try:
        kline_data = data_fetcher.get_daily_kline(code, days=days)
        
        if not kline_data:
            return {
                "success": False,
                "message": f"无法获取 {code} 的K线数据"
            }
        
        # 生成ECharts蜡烛图数据格式
        candle_data = []
        dates = []
        
        for k in kline_data:
            dates.append(k.get('date', ''))
            # [open, close, low, high] - 正确顺序
            candle_data.append([
                k.get('open', 0),
                k.get('close', 0),
                k.get('low', 0),
                k.get('high', 0)
            ])
        
        # 生成成交量数据
        volume_data = [[i, k.get('volume', 0), 1 if k.get('close', 0) >= k.get('open', 0) else -1] 
                      for i, k in enumerate(kline_data)]
        
        return {
            "success": True,
            "data": {
                "code": code,
                "dates": dates,
                "candle_data": candle_data,
                "volume_data": volume_data
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"获取蜡烛图数据失败: {str(e)}"
        }
