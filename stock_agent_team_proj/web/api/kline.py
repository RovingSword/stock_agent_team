"""
K线数据接口
GET /api/kline/{stock_code} - 返回 ECharts 所需格式的日K线 + 均线 + 支撑阻力数据
"""
import os
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from config.project_paths import ensure_project_root_on_path

ensure_project_root_on_path()

from utils.data_fetcher import data_fetcher

router = APIRouter()


def _safe_float(val, default=None):
    """安全转换为 float，NaN / None 转为 default"""
    if val is None:
        return default
    try:
        f = float(val)
        return default if (np.isnan(f) or np.isinf(f)) else round(f, 3)
    except (TypeError, ValueError):
        return default


@router.get("/kline/{stock_code}")
async def get_kline(
    stock_code: str,
    days: int = Query(default=60, ge=10, le=250),
):
    """
    返回日K线数据，格式适配 ECharts candlestick。

    响应结构::

        {
          "dates": ["2025-01-02", ...],
          "ohlc":  [[open, close, low, high], ...],
          "volumes": [123456, ...],
          "ma5":  [null, null, ..., 12.3],
          "ma10": [...],
          "ma20": [...],
          "support_levels":  [价格, ...],
          "resistance_levels": [价格, ...],
        }
    """
    code = stock_code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="股票代码不能为空")

    df: Optional[pd.DataFrame] = data_fetcher.get_daily_kline(code, days=days)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"无法获取 {code} 的K线数据")

    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["ma5"] = df["close"].rolling(window=5).mean()
    df["ma10"] = df["close"].rolling(window=10).mean()
    df["ma20"] = df["close"].rolling(window=20).mean()

    dates = df["date"].astype(str).tolist()

    ohlc = []
    for _, row in df.iterrows():
        ohlc.append([
            _safe_float(row["open"], 0),
            _safe_float(row["close"], 0),
            _safe_float(row["low"], 0),
            _safe_float(row["high"], 0),
        ])

    volumes = [_safe_float(row["volume"], 0) for _, row in df.iterrows()]
    ma5 = [_safe_float(v) for v in df["ma5"]]
    ma10 = [_safe_float(v) for v in df["ma10"]]
    ma20 = [_safe_float(v) for v in df["ma20"]]

    indicators = data_fetcher.get_technical_indicators(code)
    support_levels = []
    resistance_levels = []
    if indicators:
        support_levels = [_safe_float(v) for v in indicators.get("support_levels", []) if _safe_float(v) is not None]
        resistance_levels = [_safe_float(v) for v in indicators.get("resistance_levels", []) if _safe_float(v) is not None]

    return {
        "dates": dates,
        "ohlc": ohlc,
        "volumes": volumes,
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "support_levels": support_levels,
        "resistance_levels": resistance_levels,
    }
