"""
网络情报配置
配置搜索API密钥，支持多种搜索引擎（密钥请放在项目根目录 .env，勿提交仓库）
"""

import os

from .load_env import load_project_env

load_project_env()

# ========== 搜索引擎配置 ==========
# 启用任一搜索引擎即可实现自动情报搜集
# 密钥来源：环境变量 / .env（见 .env.example）

# Bing Search API (推荐)
# 获取方式: https://azure.microsoft.com/services/cognitive-services/bing-web-search-api/
BING_API_KEY = os.environ.get("BING_API_KEY", "").strip()
BING_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"

# Google Custom Search API
# 获取方式: https://developers.google.com/custom-search/v1/introduction
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "").strip()
GOOGLE_CX = os.environ.get("GOOGLE_CX", "").strip()

# Serper API (Google搜索的替代方案，免费额度较大)
# 获取方式: https://serper.dev/
SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "").strip()

# ========== 搜索行为配置 ==========
SEARCH_TIMEOUT = 15  # 搜索超时秒数
MAX_RESULTS_PER_TYPE = 5  # 每类情报最多获取条数

# ========== 检查是否配置了搜索能力 ==========


def has_search_capability() -> bool:
    """检查是否配置了至少一个搜索API"""
    return bool(BING_API_KEY or GOOGLE_API_KEY or SERPER_API_KEY)


def get_active_search_provider() -> str:
    """获取当前启用的搜索提供商"""
    if BING_API_KEY:
        return "bing"
    if GOOGLE_API_KEY:
        return "google"
    if SERPER_API_KEY:
        return "serper"
    return "none"
