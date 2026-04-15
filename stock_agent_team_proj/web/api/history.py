"""
历史记录查询接口
GET /api/history - 获取历史分析记录
"""
from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from stock_agent_team.storage.database import Database

router = APIRouter()


def get_db() -> Database:
    """获取数据库实例"""
    if not hasattr(get_db, '_instance'):
        get_db._instance = Database()
    return get_db._instance


class HistoryItem(BaseModel):
    """历史记录项"""
    trade_id: str
    stock_code: str
    stock_name: str
    buy_date: str
    buy_price: float
    buy_position: float
    buy_score: float
    status: str
    return_rate: Optional[float] = None
    holding_days: Optional[int] = None


class HistoryResponse(BaseModel):
    """历史记录响应"""
    success: bool
    message: str
    data: List[dict] = None
    total: int = 0


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    limit: int = Query(10, ge=1, le=100, description="返回记录数"),
    offset: int = Query(0, ge=0, description="偏移量"),
    stock_code: Optional[str] = Query(None, description="按股票代码筛选"),
    status: Optional[str] = Query(None, description="按状态筛选: holding/closed/cancelled"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD")
):
    """
    获取历史分析记录
    
    - limit: 返回记录数，默认10条
    - offset: 偏移量，用于分页
    - stock_code: 按股票代码筛选
    - status: 按状态筛选 (holding/closed/cancelled)
    - start_date: 开始日期
    - end_date: 结束日期
    """
    try:
        db = get_db()
        records = []
        
        # 根据是否有筛选条件获取记录
        if stock_code or status or start_date or end_date:
            # 使用period查询
            start = start_date or (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            end = end_date or datetime.now().strftime('%Y-%m-%d')
            trades = db.get_trades_by_period(start, end)
            
            # 应用额外筛选
            if stock_code:
                trades = [t for t in trades if t['stock_code'] == stock_code]
            if status:
                trades = [t for t in trades if t['status'] == status]
        else:
            # 获取所有交易，按日期排序
            start = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            end = datetime.now().strftime('%Y-%m-%d')
            trades = db.get_trades_by_period(start, end)
        
        # 获取各Agent评分
        for trade in trades[offset:offset+limit]:
            trade_id = trade['trade_id']
            scores = db.get_agent_scores(trade_id)
            
            record = {
                'trade_id': trade_id,
                'stock_code': trade['stock_code'],
                'stock_name': trade['stock_name'],
                'buy_date': trade['buy_date'],
                'buy_price': trade['buy_price'],
                'buy_position': trade['buy_position'],
                'buy_score': trade.get('buy_score', 0),
                'status': trade['status'],
                'return_rate': trade.get('return_rate'),
                'holding_days': trade.get('holding_days'),
                'max_profit': trade.get('max_profit'),
                'max_loss': trade.get('max_loss'),
                'agent_scores': scores,
            }
            records.append(record)
        
        return HistoryResponse(
            success=True,
            message="获取成功",
            data=records,
            total=len(trades)
        )
        
    except Exception as e:
        return HistoryResponse(
            success=False,
            message=f"获取历史记录失败: {str(e)}",
            data=[],
            total=0
        )


@router.get("/history/{trade_id}", response_model=HistoryResponse)
async def get_history_detail(trade_id: str):
    """获取单条历史记录详情"""
    try:
        db = get_db()
        trade = db.get_trade(trade_id)
        
        if not trade:
            raise HTTPException(status_code=404, detail="记录不存在")
        
        scores = db.get_agent_scores(trade_id)
        
        return HistoryResponse(
            success=True,
            message="获取成功",
            data=[{
                'trade_id': trade['trade_id'],
                'stock_code': trade['stock_code'],
                'stock_name': trade['stock_name'],
                'buy_date': trade['buy_date'],
                'buy_price': trade['buy_price'],
                'buy_position': trade['buy_position'],
                'buy_score': trade.get('buy_score', 0),
                'status': trade['status'],
                'return_rate': trade.get('return_rate'),
                'holding_days': trade.get('holding_days'),
                'max_profit': trade.get('max_profit'),
                'max_loss': trade.get('max_loss'),
                'sell_date': trade.get('sell_date'),
                'sell_price': trade.get('sell_price'),
                'sell_reason': trade.get('sell_reason'),
                'sell_score': trade.get('sell_score'),
                'agent_scores': scores,
            }]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        return HistoryResponse(
            success=False,
            message=f"获取详情失败: {str(e)}",
            data=[]
        )
