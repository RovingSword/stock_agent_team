"""
股票分析接口
POST /api/analyze - 执行股票分析
"""
import os
import sys
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from main import StockAgentTeam

router = APIRouter()


class AnalyzeRequest(BaseModel):
    """股票分析请求"""
    stock_code: str = Field(..., description="股票代码", example="300750")
    stock_name: Optional[str] = Field(None, description="股票名称，不提供则自动获取")
    user_request: str = Field("", description="用户请求描述")


class AgentScore(BaseModel):
    """Agent评分"""
    agent_type: str
    agent_name: str
    score: float
    weight: float
    weighted_score: float
    comment: str
    key_points: list
    risk_points: list


class AnalyzeResponse(BaseModel):
    """股票分析响应"""
    success: bool
    message: str
    data: Optional[dict] = None


def get_team() -> StockAgentTeam:
    """获取StockAgentTeam实例"""
    if not hasattr(get_team, '_instance'):
        get_team._instance = StockAgentTeam()
    return get_team._instance


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_stock(request: AnalyzeRequest):
    """
    股票分析接口
    
    输入股票代码，返回分析报告（评分、建议、各Agent意见）
    """
    try:
        # 参数验证
        if not request.stock_code:
            raise HTTPException(status_code=400, detail="股票代码不能为空")
        
        stock_code = request.stock_code.strip()
        stock_name = request.stock_name.strip() if request.stock_name else stock_code
        
        # 执行分析
        team = get_team()
        decision = team.analyze(
            stock_code=stock_code,
            stock_name=stock_name,
            user_request=request.user_request
        )
        
        # 提取Agent评分
        agent_scores = []
        score_breakdown = decision.score_breakdown or {}
        
        # 技术分析员
        if 'technical' in score_breakdown:
            tech = score_breakdown['technical']
            agent_scores.append(AgentScore(
                agent_type='technical',
                agent_name='技术分析员',
                score=tech.get('score', 0),
                weight=tech.get('weight', 0.35),
                weighted_score=tech.get('weighted_score', 0),
                comment=tech.get('comment', ''),
                key_points=tech.get('key_points', []),
                risk_points=tech.get('risk_points', [])
            ))
        
        # 情报员
        if 'intelligence' in score_breakdown:
            intel = score_breakdown['intelligence']
            agent_scores.append(AgentScore(
                agent_type='intelligence',
                agent_name='情报员',
                score=intel.get('score', 0),
                weight=intel.get('weight', 0.30),
                weighted_score=intel.get('weighted_score', 0),
                comment=intel.get('comment', ''),
                key_points=intel.get('key_points', []),
                risk_points=intel.get('risk_points', [])
            ))
        
        # 风控官
        if 'risk' in score_breakdown:
            risk = score_breakdown['risk']
            agent_scores.append(AgentScore(
                agent_type='risk',
                agent_name='风控官',
                score=risk.get('score', 0),
                weight=risk.get('weight', 0.20),
                weighted_score=risk.get('weighted_score', 0),
                comment=risk.get('comment', ''),
                key_points=risk.get('key_points', []),
                risk_points=risk.get('risk_points', [])
            ))
        
        # 基本面分析师
        if 'fundamental' in score_breakdown:
            fund = score_breakdown['fundamental']
            agent_scores.append(AgentScore(
                agent_type='fundamental',
                agent_name='基本面分析师',
                score=fund.get('score', 0),
                weight=fund.get('weight', 0.15),
                weighted_score=fund.get('weighted_score', 0),
                comment=fund.get('comment', ''),
                key_points=fund.get('key_points', []),
                risk_points=fund.get('risk_points', [])
            ))
        
        # 构建返回数据
        result_data = {
            'task_id': decision.header.message_id,
            'stock_code': decision.stock_code,
            'stock_name': decision.stock_name,
            'final_action': decision.final_action,
            'confidence': decision.confidence,
            'composite_score': decision.composite_score,
            'execution': {
                'entry_zone': decision.execution.get('entry_zone', []),
                'stop_loss': decision.execution.get('stop_loss', 0),
                'take_profit_1': decision.execution.get('take_profit_1', 0),
                'take_profit_2': decision.execution.get('take_profit_2', 0),
                'position_size': decision.execution.get('position_size', 0),
            },
            'rationale': {
                'buy_reasons': decision.rationale.get('buy_reasons', []),
                'risk_warnings': decision.rationale.get('risk_warnings', []),
            },
            'agent_scores': [s.model_dump() for s in agent_scores],
            'timestamp': decision.header.timestamp,
        }
        
        return AnalyzeResponse(
            success=True,
            message="分析完成",
            data=result_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        return AnalyzeResponse(
            success=False,
            message=f"分析失败: {str(e)}",
            data=None
        )
