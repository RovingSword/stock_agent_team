"""
情报追踪 API
提供股票情报追踪、板块热点追踪和情报简报功能
"""

import os
import sys
from datetime import datetime
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from watchlist import DataCollector, StockScreener, WatchlistManager
from utils.intel_cache import get_intel

router = APIRouter()

# 获取组件实例
def get_data_collector() -> DataCollector:
    if not hasattr(get_data_collector, '_instance'):
        get_data_collector._instance = DataCollector()
    return get_data_collector._instance


def get_stock_screener() -> StockScreener:
    if not hasattr(get_stock_screener, '_instance'):
        get_stock_screener._instance = StockScreener()
    return get_stock_screener._instance


def get_watchlist_manager() -> WatchlistManager:
    if not hasattr(get_watchlist_manager, '_instance'):
        get_watchlist_manager._instance = WatchlistManager()
    return get_watchlist_manager._instance


# ========== 请求模型 ==========

class TrackStockRequest(BaseModel):
    """追踪股票请求"""
    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    days: int = Field(7, description="追踪天数")
    force_refresh: bool = Field(False, description="是否强制刷新（跳过缓存）")


class TrackSectorRequest(BaseModel):
    """追踪板块请求"""
    sector_name: str = Field(..., description="板块名称")
    days: int = Field(7, description="追踪天数")


# ========== API端点 ==========

@router.post("/intel/track")
async def track_stock(request: TrackStockRequest):
    """追踪单只股票情报（带缓存机制）

    缓存策略：
    - 3天内：直接使用缓存
    - 3~7天：使用缓存但标记为 stale
    - 7天以上：强制重新搜索
    - force_refresh=True：跳过缓存
    """
    try:
        stock_name = request.stock_name or request.stock_code
        collector = get_data_collector()
        
        # ========== 使用统一缓存接口获取情报 ==========
        intel_data = get_intel(
            stock_code=request.stock_code,
            stock_name=stock_name,
            force_refresh=request.force_refresh
        )

        # 提取缓存元信息
        cache_meta = intel_data.pop('_cache_meta', {})

        # 尝试收集龙虎榜数据（补充信息）
        try:
            dragon_data = collector.collect_dragon_rank()
            for item in dragon_data:
                if request.stock_code in str(item):
                    intel_data["dragon_rank"] = item
        except Exception:
            pass
        
        # 计算汇总
        total_news = len(intel_data.get("news", []))
        total_research = len(intel_data.get("research", []))
        total_sentiment = len(intel_data.get("sentiment", []))

        # 构建返回消息（含缓存状态）
        if cache_meta.get('is_fresh'):
            cache_status = f"(使用{cache_meta.get('age_days', 0)}天前缓存)"
        elif cache_meta.get('is_stale'):
            cache_status = f"(缓存已{cache_meta.get('age_days', '?')}天，建议刷新)"
        else:
            cache_status = "(全新搜索)"

        return {
            "success": True,
            "message": f"已追踪 {stock_name}({request.stock_code}) 情报: {total_news}条新闻, {total_research}条研报, {total_sentiment}条舆情 {cache_status}",
            "data": intel_data,
            "cache_meta": cache_meta
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"追踪失败: {str(e)}"
        }


@router.post("/intel/track-sector")
async def track_sector(request: TrackSectorRequest):
    """追踪板块热点"""
    try:
        collector = get_data_collector()
        screener = get_stock_screener()
        
        # 收集板块数据
        sector_data = {
            "sector_name": request.sector_name,
            "tracked_at": datetime.now().isoformat(),
            "days": request.days,
            "hot_stocks": [],
            "trend": "unknown",
            "strength": 0.0
        }
        
        # 尝试获取热门板块股票
        try:
            hot_sectors = collector.collect_hot_sectors()
            for sector in hot_sectors:
                if request.sector_name in sector.get("name", ""):
                    sector_data["trend"] = sector.get("trend", "unknown")
                    sector_data["strength"] = sector.get("hot_score", 0.0)
                    sector_data["hot_stocks"] = sector.get("stocks", [])
        except Exception:
            pass
        
        return {
            "success": True,
            "message": f"已追踪板块 {request.sector_name}",
            "data": sector_data
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"追踪板块失败: {str(e)}"
        }


@router.get("/intel/brief/{code}")
async def get_intel_brief(code: str, force_refresh: bool = False):
    """获取股票情报简报（带缓存机制）"""
    try:
        # 获取股票名称
        manager = get_watchlist_manager()
        candidate = manager.get_candidate(code)
        stock_name = candidate.name if candidate else code
        
        # 使用统一缓存接口
        intel_data = get_intel(
            stock_code=code,
            stock_name=stock_name,
            force_refresh=force_refresh
        )
            
        # 提取缓存元信息
        cache_meta = intel_data.pop('_cache_meta', {})
            
        # 兼容旧接口：stale 字段
        intel_data["stale"] = cache_meta.get('is_stale', False) or cache_meta.get('is_expired', False)
            
        return {
            "success": True,
            "data": intel_data,
            "cache_meta": cache_meta
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"获取简报失败: {str(e)}"
        }


@router.get("/intel/hot-sectors")
async def get_hot_sectors():
    """获取热门板块"""
    try:
        collector = get_data_collector()
        hot_sectors = collector.collect_hot_sectors()
        
        return {
            "success": True,
            "data": {
                "sectors": hot_sectors[:20],  # 返回前20个
                "count": len(hot_sectors)
            }
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"获取热门板块失败: {str(e)}"
        }


@router.get("/intel/dragon-rank")
async def get_dragon_rank():
    """获取龙虎榜数据"""
    try:
        collector = get_data_collector()
        dragon_data = collector.collect_dragon_rank()
        
        return {
            "success": True,
            "data": {
                "records": dragon_data,
                "count": len(dragon_data)
            }
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"获取龙虎榜失败: {str(e)}"
        }


@router.post("/intel/collect")
async def collect_intel_data():
    """收集所有情报数据"""
    try:
        collector = get_data_collector()
        
        results = {
            "collected_at": datetime.now().isoformat(),
            "dragon_rank": {"count": 0},
            "hot_sectors": {"count": 0},
            "research": {"count": 0}
        }
        
        # 收集龙虎榜
        try:
            dragon_data = collector.collect_dragon_rank()
            results["dragon_rank"]["count"] = len(dragon_data)
            results["dragon_rank"]["data"] = dragon_data[:10]
        except Exception as e:
            results["dragon_rank"]["error"] = str(e)
        
        # 收集热门板块
        try:
            hot_sectors = collector.collect_hot_sectors()
            results["hot_sectors"]["count"] = len(hot_sectors)
            results["hot_sectors"]["data"] = hot_sectors[:10]
        except Exception as e:
            results["hot_sectors"]["error"] = str(e)
        
        # 收集机构调研
        try:
            research = collector.collect_research()
            results["research"]["count"] = len(research)
            results["research"]["data"] = research[:10]
        except Exception as e:
            results["research"]["error"] = str(e)
        
        return {
            "success": True,
            "message": "情报数据收集完成",
            "data": results
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"收集失败: {str(e)}"
        }
