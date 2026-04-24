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

from utils.data_fetcher import data_fetcher, compute_rule_based_support_resistance

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
          "macd_dif", "macd_dea", "macd_hist": MACD 序列,
          "rsi12": RSI(12) 序列,
          "vol_ma5", "vol_ma10": 成交量均线,
          "data_uses_mock": 是否使用模拟/兜底数据,
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

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd_dif"] = ema12 - ema26
    df["macd_dea"] = df["macd_dif"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = (df["macd_dif"] - df["macd_dea"]) * 2.0

    def _calc_rsi(series: pd.Series, period: int = 12) -> pd.Series:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, np.inf)
        return 100 - (100 / (1 + rs))

    df["rsi12"] = _calc_rsi(df["close"], 12)
    df["vol_ma5"] = df["volume"].rolling(window=5).mean()
    df["vol_ma10"] = df["volume"].rolling(window=10).mean()

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
    macd_dif = [_safe_float(v) for v in df["macd_dif"]]
    macd_dea = [_safe_float(v) for v in df["macd_dea"]]
    macd_hist = [_safe_float(v) for v in df["macd_hist"]]
    rsi12 = [_safe_float(v) for v in df["rsi12"]]
    vol_ma5 = [_safe_float(v) for v in df["vol_ma5"]]
    vol_ma10 = [_safe_float(v) for v in df["vol_ma10"]]

    highs_s = df["high"].tolist()
    lows_s = df["low"].tolist()
    closes_s = df["close"].tolist()
    support_raw, resistance_raw = compute_rule_based_support_resistance(highs_s, lows_s, closes_s)
    support_levels = [_safe_float(v) for v in support_raw if _safe_float(v) is not None]
    resistance_levels = [_safe_float(v) for v in resistance_raw if _safe_float(v) is not None]

    return {
        "dates": dates,
        "ohlc": ohlc,
        "volumes": volumes,
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "macd_dif": macd_dif,
        "macd_dea": macd_dea,
        "macd_hist": macd_hist,
        "rsi12": rsi12,
        "vol_ma5": vol_ma5,
        "vol_ma10": vol_ma10,
        "support_levels": support_levels,
        "resistance_levels": resistance_levels,
        "data_uses_mock": data_fetcher.is_mock_data(code),
    }
