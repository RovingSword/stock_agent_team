"""
历史表现 API
提供表现统计、周报、月报和持仓记录功能
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from watchlist import PerformanceTracker, PerformanceReporter

router = APIRouter()

# 获取组件实例
def get_performance_tracker() -> PerformanceTracker:
    if not hasattr(get_performance_tracker, '_instance'):
        get_performance_tracker._instance = PerformanceTracker()
    return get_performance_tracker._instance


def get_performance_reporter() -> PerformanceReporter:
    if not hasattr(get_performance_reporter, '_instance'):
        get_performance_reporter._instance = PerformanceReporter()
    return get_performance_reporter._instance


# ========== 请求模型 ==========

class ClosePositionRequest(BaseModel):
    """平仓请求"""
    stock_code: str = Field(..., description="股票代码")
    reason: str = Field("", description="平仓原因")
    exit_price: Optional[float] = Field(None, description="出场价格")
    exit_date: Optional[str] = Field(None, description="出场日期")


class AddPositionRequest(BaseModel):
    """添加持仓请求"""
    stock_code: str = Field(..., description="股票代码")
    stock_name: str = Field(..., description="股票名称")
    entry_price: float = Field(..., description="入场价格")
    shares: int = Field(..., description="股数")
    entry_date: Optional[str] = Field(None, description="入场日期")


# ========== API端点 ==========

@router.get("/performance/stats")
async def get_performance_stats():
    """获取表现统计"""
    try:
        tracker = get_performance_tracker()
        stats = tracker.get_summary_stats()
        
        # 格式化数据
        formatted_stats = {
            "total_signals": stats.get("total_signals", 0),
            "winning_signals": stats.get("winning_signals", 0),
            "total_profit_rate": round(stats.get("total_profit_rate", 0), 4),
            "win_rate": round(stats.get("win_rate", 0), 4),
            "avg_holding_days": round(stats.get("avg_holding_days", 0), 1),
            "max_consecutive_wins": stats.get("max_consecutive_wins", 0),
            "max_consecutive_losses": stats.get("max_consecutive_losses", 0),
            "largest_profit": round(stats.get("largest_profit", 0), 4),
            "largest_loss": round(stats.get("largest_loss", 0), 4),
        }
        
        return {
            "success": True,
            "data": formatted_stats
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"获取统计失败: {str(e)}"
        }


@router.get("/performance/weekly")
async def get_weekly_report():
    """获取周度报告"""
    try:
        reporter = get_performance_reporter()
        
        # 生成周报
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        report = reporter.generate_weekly_report(start_date, end_date)
        
        return {
            "success": True,
            "data": report
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"生成周报失败: {str(e)}"
        }


@router.get("/performance/monthly")
async def get_monthly_report():
    """获取月度报告"""
    try:
        reporter = get_performance_reporter()
        
        # 生成月报
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        report = reporter.generate_monthly_report(start_date, end_date)
        
        return {
            "success": True,
            "data": report
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"生成月报失败: {str(e)}"
        }


@router.get("/performance/positions")
async def get_positions():
    """获取持仓记录"""
    try:
        tracker = get_performance_tracker()
        positions = tracker.get_open_positions()
        
        formatted_positions = []
        for pos in positions:
            formatted_positions.append({
                "stock_code": pos.stock_code,
                "stock_name": pos.stock_name,
                "entry_price": pos.entry_price,
                "shares": pos.shares,
                "entry_date": pos.entry_date,
                "current_value": pos.current_value or (pos.entry_price * pos.shares),
                "profit_loss": pos.profit_loss or 0.0,
                "profit_rate": pos.profit_rate or 0.0,
                "holding_days": (datetime.now() - datetime.fromisoformat(pos.entry_date)).days if pos.entry_date else 0
            })
        
        return {
            "success": True,
            "data": {
                "positions": formatted_positions,
                "count": len(formatted_positions)
            }
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"获取持仓失败: {str(e)}"
        }


@router.get("/performance/history")
async def get_signal_history(
    stock_code: Optional[str] = None,
    limit: int = 20
):
    """获取信号历史"""
    try:
        tracker = get_performance_tracker()
        history = tracker.get_signal_history(stock_code, limit)
        
        formatted_history = []
        for signal in history:
            formatted_history.append({
                "signal_id": signal.signal_id,
                "stock_code": signal.stock_code,
                "stock_name": signal.stock_name,
                "signal_type": signal.signal_type,
                "entry_price": signal.entry_price,
                "exit_price": signal.exit_price,
                "profit_rate": round(signal.profit_rate, 4) if signal.profit_rate else 0.0,
                "signal_date": signal.signal_date,
                "close_date": signal.close_date,
                "holding_days": signal.holding_days,
                "status": signal.status,
                "close_reason": signal.close_reason
            })
        
        return {
            "success": True,
            "data": {
                "signals": formatted_history,
                "count": len(formatted_history)
            }
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"获取历史失败: {str(e)}"
        }


@router.post("/performance/close")
async def close_position(request: ClosePositionRequest):
    """平仓"""
    try:
        tracker = get_performance_tracker()
        
        success = tracker.close_position(
            code=request.stock_code,
            exit_price=request.exit_price,
            exit_date=request.exit_date,
            reason=request.reason
        )
        
        if success:
            return {
                "success": True,
                "message": f"{request.stock_code} 已平仓"
            }
        else:
            return {
                "success": False,
                "message": f"{request.stock_code} 平仓失败或不在持仓中"
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"平仓失败: {str(e)}"
        }


@router.post("/performance/add-position")
async def add_position(request: AddPositionRequest):
    """添加持仓"""
    try:
        tracker = get_performance_tracker()
        
        success = tracker.add_position(
            code=request.stock_code,
            name=request.stock_name,
            entry_price=request.entry_price,
            shares=request.shares,
            entry_date=request.entry_date
        )
        
        if success:
            return {
                "success": True,
                "message": f"已添加 {request.stock_name}({request.stock_code}) 持仓"
            }
        else:
            return {
                "success": False,
                "message": "添加持仓失败"
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"添加持仓失败: {str(e)}"
        }


@router.get("/performance/chart-data")
async def get_performance_chart_data():
    """获取表现图表数据"""
    try:
        tracker = get_performance_tracker()
        reporter = get_performance_reporter()
        
        # 获取历史信号
        history = tracker.get_signal_history(limit=100)
        
        # 生成累计收益曲线
        cumulative_data = []
        cumulative_profit = 0.0
        
        for signal in sorted(history, key=lambda x: x.signal_date):
            if signal.profit_rate is not None:
                cumulative_profit += signal.profit_rate
                cumulative_data.append({
                    "date": signal.close_date or signal.signal_date,
                    "cumulative_profit": round(cumulative_profit, 4),
                    "single_profit": round(signal.profit_rate, 4)
                })
        
        # 获取胜率统计
        stats = tracker.get_summary_stats()
        
        return {
            "success": True,
            "data": {
                "cumulative_curve": cumulative_data,
                "summary": {
                    "win_rate": round(stats.get("win_rate", 0), 4),
                    "total_profit_rate": round(stats.get("total_profit_rate", 0), 4),
                    "total_signals": stats.get("total_signals", 0)
                }
            }
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"获取图表数据失败: {str(e)}"
        }
