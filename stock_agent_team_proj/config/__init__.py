"""配置模块"""
import os

from .project_paths import PROJECT_ROOT, ensure_project_root_on_path

# 单点将项目根加入 path（供 import agents / utils 等顶级包）
ensure_project_root_on_path()
BASE_DIR = str(PROJECT_ROOT)

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
