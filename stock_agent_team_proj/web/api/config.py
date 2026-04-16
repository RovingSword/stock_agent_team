"""
配置管理接口
GET /api/config - 获取权重配置
"""
import os
import sys
from typing import Dict

from fastapi import APIRouter
from pydantic import BaseModel

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from storage.database import Database
import config as app_config

router = APIRouter()


class WeightsConfig(BaseModel):
    """权重配置"""
    technical: float
    intelligence: float
    risk: float
    fundamental: float


class ConfigResponse(BaseModel):
    """配置响应"""
    success: bool
    message: str
    weights: WeightsConfig
    weight_ranges: Dict[str, tuple]
    score_thresholds: Dict[str, float]
    position_limits: Dict[str, float]


def get_db() -> Database:
    """获取数据库实例"""
    if not hasattr(get_db, '_instance'):
        get_db._instance = Database()
    return get_db._instance


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    """
    获取当前配置信息
    
    返回:
    - weights: 当前Agent权重配置
    - weight_ranges: 权重调整范围
    - score_thresholds: 评分阈值
    - position_limits: 仓位限制
    """
    try:
        db = get_db()
        
        # 获取当前权重
        current_weights = db.get_current_weights()
        
        return ConfigResponse(
            success=True,
            message="获取成功",
            weights=WeightsConfig(**current_weights),
            weight_ranges=app_config.WEIGHT_RANGES,
            score_thresholds=app_config.SCORE_THRESHOLDS,
            position_limits=app_config.POSITION_LIMITS
        )
        
    except Exception as e:
        # 返回默认配置
        return ConfigResponse(
            success=False,
            message=f"获取配置失败，使用默认配置: {str(e)}",
            weights=WeightsConfig(
                technical=0.35,
                intelligence=0.30,
                risk=0.20,
                fundamental=0.15
            ),
            weight_ranges=app_config.WEIGHT_RANGES,
            score_thresholds=app_config.SCORE_THRESHOLDS,
            position_limits=app_config.POSITION_LIMITS
        )


@router.get("/config/weights", response_model=ConfigResponse)
async def get_weights():
    """获取权重配置（别名）"""
    return await get_config()


@router.get("/config/thresholds", response_model=ConfigResponse)
async def get_thresholds():
    """获取评分阈值配置"""
    return ConfigResponse(
        success=True,
        message="获取成功",
        weights=WeightsConfig(
            technical=0.35,
            intelligence=0.30,
            risk=0.20,
            fundamental=0.15
        ),
        weight_ranges=app_config.WEIGHT_RANGES,
        score_thresholds=app_config.SCORE_THRESHOLDS,
        position_limits=app_config.POSITION_LIMITS
    )
