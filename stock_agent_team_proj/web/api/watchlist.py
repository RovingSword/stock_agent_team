"""
观察池管理 API
提供观察池的增删改查、状态管理和分析功能
"""

import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from watchlist import WatchlistManager, StockCandidate

router = APIRouter()

# 获取WatchlistManager单例
def get_watchlist_manager() -> WatchlistManager:
    if not hasattr(get_watchlist_manager, '_instance'):
        get_watchlist_manager._instance = WatchlistManager()
    return get_watchlist_manager._instance


# ========== 请求模型 ==========

class AddStockRequest(BaseModel):
    """添加股票请求"""
    stock_code: str = Field(..., description="股票代码", example="300750")
    stock_name: str = Field(..., description="股票名称", example="宁德时代")
    source: str = Field("manual", description="来源: dragon_rank/hot_sector/research/manual")
    score: float = Field(0.0, description="初始评分")
    reason: str = Field("", description="添加原因")


class RemoveStockRequest(BaseModel):
    """移除股票请求"""
    stock_code: str = Field(..., description="股票代码")
    reason: str = Field("", description="移除原因")


class UpdateStatusRequest(BaseModel):
    """更新状态请求"""
    stock_code: str = Field(..., description="股票代码")
    status: str = Field(..., description="新状态: pending/watching/archived/removed")


class AnalyzeRequest(BaseModel):
    """分析请求"""
    stock_code: Optional[str] = Field(None, description="股票代码，不提供则分析所有")
    mode: str = Field("rule", description="分析模式: rule/llm")
    with_intel: bool = Field(True, description="是否注入网络情报（仅llm模式生效）")
    force_refresh: bool = Field(False, description="是否强制刷新情报缓存（跳过缓存重新搜索）")


# ========== 响应模型 ==========

class StockCandidateResponse(BaseModel):
    """股票候选响应"""
    code: str
    name: str
    status: str
    score: float
    composite_score: float
    is_buy_recommended: bool
    source: str
    add_reason: str
    add_date: str
    last_analysis_date: Optional[str]
    analysis_result: Optional[Dict[str, Any]]
    
    @classmethod
    def from_candidate(cls, candidate: StockCandidate) -> "StockCandidateResponse":
        return cls(
            code=candidate.code,
            name=candidate.name,
            status=candidate.status,
            score=candidate.source_score or 0.0,
            composite_score=candidate.composite_score or 0.0,
            is_buy_recommended=candidate.is_buy_recommended or False,
            source=candidate.source or "manual",
            add_reason=candidate.add_reason or "",
            add_date=candidate.add_date or "",
            last_analysis_date=candidate.last_analysis_date,
            analysis_result=candidate.analysis_result,
        )


# ========== API端点 ==========

@router.get("/watchlist/status")
async def get_watchlist_status():
    """获取观察池状态"""
    try:
        manager = get_watchlist_manager()
        stats = manager.get_statistics()
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"获取状态失败: {str(e)}"
        }


@router.get("/watchlist/list")
async def get_watchlist_list(status: Optional[str] = None):
    """获取候选股列表"""
    try:
        manager = get_watchlist_manager()
        if status:
            candidates = manager.get_all_candidates(status=status)
        else:
            candidates = manager.get_all_candidates()
        
        return {
            "success": True,
            "data": {
                "candidates": [StockCandidateResponse.from_candidate(c).model_dump() for c in candidates],
                "total": len(candidates)
            }
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"获取列表失败: {str(e)}"
        }


@router.post("/watchlist/add")
async def add_stock(request: AddStockRequest):
    """添加股票到观察池"""
    try:
        manager = get_watchlist_manager()
        
        # 创建候选股票对象
        candidate = StockCandidate(
            code=request.stock_code,
            name=request.stock_name,
            add_date=datetime.now().strftime("%Y-%m-%d"),
            add_reason=request.reason,
            source=request.source,
            source_score=request.score,
            status="pending"
        )
        
        success = manager.add_candidate(candidate)
        
        if success:
            return {
                "success": True,
                "message": f"成功添加 {request.stock_name}({request.stock_code}) 到观察池"
            }
        else:
            # 检查是否已存在
            existing = manager.get_candidate(request.stock_code)
            if existing:
                return {
                    "success": False,
                    "message": f"{request.stock_name}({request.stock_code}) 已在观察池中"
                }
            return {
                "success": False,
                "message": "添加失败，观察池可能已满"
            }
            
    except Exception as e:
        return {
            "success": False,
            "message": f"添加失败: {str(e)}"
        }


@router.post("/watchlist/remove")
async def remove_stock(request: RemoveStockRequest):
    """从观察池移除股票"""
    try:
        manager = get_watchlist_manager()
        success = manager.remove_candidate(request.stock_code, request.reason)
        
        if success:
            return {
                "success": True,
                "message": f"已从观察池移除 {request.stock_code}"
            }
        else:
            return {
                "success": False,
                "message": f"{request.stock_code} 不在观察池中或移除失败"
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"移除失败: {str(e)}"
        }


@router.post("/watchlist/status")
async def update_stock_status(request: UpdateStatusRequest):
    """更新股票状态"""
    try:
        manager = get_watchlist_manager()
        success = manager.change_status(request.stock_code, request.status)
        
        if success:
            return {
                "success": True,
                "message": f"已将 {request.stock_code} 状态更新为 {request.status}"
            }
        else:
            return {
                "success": False,
                "message": f"更新状态失败: {request.stock_code}"
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"更新状态失败: {str(e)}"
        }


@router.post("/watchlist/analyze")
async def analyze_watchlist(request: AnalyzeRequest):
    """分析观察池中的股票

    mode=rule: 快速规则筛选
    mode=llm: LLM Agent深度分析（支持网络情报注入）
    """
    try:
        manager = get_watchlist_manager()
        
        if request.stock_code:
            # 分析单只股票
            candidate = manager.get_candidate(request.stock_code)
            if not candidate:
                return {
                    "success": False,
                    "message": f"{request.stock_code} 不在观察池中"
                }
            candidates = [candidate]
        else:
            # 分析所有待分析的股票
            candidates = manager.get_pending_candidates()
        
        if not candidates:
            return {
                "success": False,
                "message": "没有待分析的股票"
            }
        
        results = []

        if request.mode == "llm":
            # ========== LLM Agent 深度分析（含情报注入，带缓存） ==========
            from main import StockAgentTeam

            team = StockAgentTeam()

            for candidate in candidates:
                manager.change_status(candidate.code, 'analyzing')

                # 通过统一缓存接口收集网络情报
                web_intel = None
                intel_cache_meta = None
                if request.with_intel:
                    try:
                        # 获取情报数据（带缓存机制）
                        from utils.intel_cache import get_intel
                        raw_intel = get_intel(
                            stock_code=candidate.code,
                            stock_name=candidate.name,
                            force_refresh=request.force_refresh
                        )
                        intel_cache_meta = raw_intel.pop('_cache_meta', None)

                        # 检查是否有实质内容，转换为分析注入格式
                        search_stats = raw_intel.get('search_stats', {})
                        has_content = any(raw_intel.get(k) for k in ['news', 'research', 'sentiment', 'industry', 'macro'])

                        if has_content or search_stats.get('searched', False):
                            # 转换为 {type: [results]} 格式
                            formatted = {}
                            for intel_type in ['news', 'research', 'sentiment', 'industry', 'macro']:
                                items = raw_intel.get(intel_type, [])
                                if items:
                                    formatted[intel_type] = items
                            if formatted:
                                web_intel = formatted
                    except Exception as e:
                        # 情报收集失败不阻断分析
                        pass

                # 执行LLM分析
                decision = team.analyze(
                    candidate.code,
                    candidate.name,
                    "中短线波段分析",
                    web_intel
                )

                # 构建情报来源信息
                intel_source = "none"
                if web_intel is not None and intel_cache_meta:
                    if intel_cache_meta.get('is_fresh'):
                        intel_source = f"cached({intel_cache_meta.get('age_days', 0)}d)"
                    elif intel_cache_meta.get('is_stale'):
                        intel_source = f"stale({intel_cache_meta.get('age_days', '?')}d)"
                    else:
                        intel_source = "fresh_search"

                # 更新分析结果
                manager.update_analysis_result(
                    code=candidate.code,
                    analysis_result={
                        "mode": "llm",
                        "analyzed_at": datetime.now().isoformat(),
                        "action": decision.final_action,
                        "confidence": decision.confidence,
                        "rationale": decision.rationale,
                        "with_intel": web_intel is not None,
                        "intel_source": intel_source,
                    },
                    composite_score=decision.composite_score,
                    is_buy_recommended=decision.is_buy,
                )

                results.append({
                    "code": candidate.code,
                    "name": candidate.name,
                    "action": decision.final_action,
                    "composite_score": round(decision.composite_score, 2),
                    "confidence": decision.confidence,
                    "is_buy": decision.is_buy,
                    "with_intel": web_intel is not None,
                    "intel_source": intel_source,
                })
        else:
            # ========== 规则模式快速筛选 ==========
            for candidate in candidates:
                manager.update_analysis_result(
                    code=candidate.code,
                    analysis_result={
                        "mode": "rule",
                        "analyzed_at": datetime.now().isoformat(),
                        "summary": f"{candidate.name} 规则筛选完成"
                    },
                    composite_score=candidate.source_score or 75.0,
                    is_buy_recommended=True
                )
                results.append({
                    "code": candidate.code,
                    "name": candidate.name,
                    "status": "analyzed"
                })

        return {
            "success": True,
            "message": f"成功分析 {len(results)} 只股票 (模式: {request.mode})",
            "data": {
                "analyzed": results,
                "total": len(results),
                "mode": request.mode
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"分析失败: {str(e)}"
        }


@router.get("/watchlist/search")
async def search_stocks(keyword: str):
    """搜索股票"""
    try:
        manager = get_watchlist_manager()
        results = manager.search(keyword)
        
        return {
            "success": True,
            "data": {
                "results": [StockCandidateResponse.from_candidate(c).model_dump() for c in results],
                "count": len(results)
            }
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"搜索失败: {str(e)}"
        }


@router.get("/watchlist/recommended")
async def get_recommended_stocks():
    """获取推荐买入的股票"""
    try:
        manager = get_watchlist_manager()
        candidates = manager.get_buy_recommended()
        
        return {
            "success": True,
            "data": {
                "candidates": [StockCandidateResponse.from_candidate(c).model_dump() for c in candidates],
                "count": len(candidates)
            }
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"获取推荐失败: {str(e)}"
        }
