"""配置模块"""
import os
import sys

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# 从settings导入所有配置
from .settings import *
from .intel_config import (
    has_search_capability,
    get_active_search_provider,
    BING_API_KEY,
    GOOGLE_API_KEY,
    SERPER_API_KEY
)

__all__ = [
    # 基础配置
    'BASE_DIR', 'DATA_DIR', 'DATABASE_PATH', 'REPORTS_DIR', 'LOGS_DIR',
    'AGENT_WEIGHTS', 'WEIGHT_RANGES', 'SCORE_THRESHOLDS',
    # 情报配置
    'has_search_capability', 'get_active_search_provider',
    'BING_API_KEY', 'GOOGLE_API_KEY', 'SERPER_API_KEY'
]
