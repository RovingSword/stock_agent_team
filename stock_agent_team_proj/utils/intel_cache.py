"""
统一情报缓存管理
为情报追踪、LLM分析等模块提供统一的情报获取、缓存和过期机制

核心规则：
- 3天内：直接使用缓存，不重新搜索
- 3~7天：使用缓存但标记为 stale（建议刷新）
- 7天以上：强制重新搜索
- force_refresh=True：跳过缓存，强制搜索
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

from config.intel_config import has_search_capability, get_active_search_provider
from utils.intel_searcher import intel_searcher
from utils.logger import get_logger

logger = get_logger('intel_cache')

# 缓存目录
INTEL_CACHE_DIR = os.path.join('data', 'intel')

# 有效期配置（天数）
FRESH_DAYS = 3       # 3天内视为新鲜
STALE_DAYS = 7       # 7天内可用但过时，超过7天强制刷新


def get_intel_cache_path(stock_code: str) -> str:
    """获取情报缓存文件路径"""
    return os.path.join(INTEL_CACHE_DIR, f'{stock_code}.json')


def load_intel_cache(stock_code: str) -> Optional[Dict[str, Any]]:
    """加载情报缓存，返回 None 表示无缓存或缓存无效

    Returns:
        缓存数据字典，包含 _cache_meta 元信息
    """
    cache_file = get_intel_cache_path(stock_code)

    if not os.path.exists(cache_file):
        return None

    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 解析缓存时间
        tracked_at = data.get('tracked_at', '')
        cache_time = None
        if tracked_at:
            try:
                cache_time = datetime.fromisoformat(tracked_at)
            except (ValueError, TypeError):
                pass

        # 计算缓存年龄
        age_days = None
        if cache_time:
            age_days = (datetime.now() - cache_time).days

        # 检查是否有实质内容
        has_content = (
            bool(data.get('news')) or
            bool(data.get('research')) or
            bool(data.get('sentiment')) or
            bool(data.get('announcements'))
        )

        if not has_content:
            logger.info(f"缓存无实质内容: {stock_code}")
            return None

        # 添加缓存元信息（不保存到文件，仅运行时使用）
        data['_cache_meta'] = {
            'age_days': age_days,
            'is_fresh': age_days is not None and age_days <= FRESH_DAYS,
            'is_stale': age_days is not None and FRESH_DAYS < age_days <= STALE_DAYS,
            'is_expired': age_days is not None and age_days > STALE_DAYS,
            'cache_time': tracked_at,
        }

        return data

    except Exception as e:
        logger.warning(f"读取缓存失败: {stock_code} - {e}")
        return None


def save_intel_cache(stock_code: str, intel_data: Dict[str, Any]) -> None:
    """保存情报到缓存文件"""
    # 移除运行时元信息
    save_data = {k: v for k, v in intel_data.items() if k != '_cache_meta'}

    # 确保目录存在
    os.makedirs(INTEL_CACHE_DIR, exist_ok=True)

    cache_file = get_intel_cache_path(stock_code)
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)

    logger.info(f"情报已缓存: {stock_code} -> {cache_file}")


def search_intel(stock_code: str, stock_name: str) -> Dict[str, Any]:
    """通过搜索引擎收集情报（不使用缓存）

    Returns:
        搜索结果数据，已保存到缓存
    """
    intel_data = {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "tracked_at": datetime.now().isoformat(),
        "days": 7,
        "news": [],
        "announcements": [],
        "research": [],
        "sentiment": [],
        "social_sentiment": "neutral",
        "hot_rank": None,
    }

    search_stats = {
        "search_provider": "none",
        "searched": False,
    }

    if has_search_capability():
        search_provider = get_active_search_provider()
        search_stats["search_provider"] = search_provider
        search_stats["searched"] = True

        search_tasks = [
            {"type": "news", "query": f"{stock_name} {stock_code} 最新消息", "max_results": 5},
            {"type": "research", "query": f"{stock_name} 研报 目标价 评级", "max_results": 3},
            {"type": "sentiment", "query": f"{stock_name} 股吧 讨论", "max_results": 3},
        ]

        for task in search_tasks:
            try:
                results = intel_searcher.search(task["query"], task["max_results"])
                if results:
                    intel_data[task["type"]] = [
                        {
                            "title": r.get("title", ""),
                            "summary": r.get("snippet", ""),
                            "url": r.get("url", ""),
                            "time": r.get("time"),
                            "sentiment": "neutral"
                        }
                        for r in results
                    ]
                    search_stats[f"{task['type']}_count"] = len(results)
                else:
                    search_stats[f"{task['type']}_count"] = 0
            except Exception as e:
                search_stats[f"{task['type']}_error"] = str(e)
                search_stats[f"{task['type']}_count"] = 0

    intel_data["search_stats"] = search_stats

    # 保存到缓存
    save_intel_cache(stock_code, intel_data)

    return intel_data


def get_intel(stock_code: str, stock_name: str = None,
              force_refresh: bool = False) -> Dict[str, Any]:
    """统一情报获取接口（带缓存机制）

    这是所有模块获取情报的唯一入口。

    缓存策略：
    - force_refresh=True: 强制重新搜索
    - 缓存 ≤ 3天: 直接返回缓存
    - 3天 < 缓存 ≤ 7天: 返回缓存但标记为 stale
    - 缓存 > 7天: 强制重新搜索
    - 无缓存: 执行搜索

    Args:
        stock_code: 股票代码
        stock_name: 股票名称（无缓存时用于搜索）
        force_refresh: 是否强制刷新（跳过缓存）

    Returns:
        情报数据字典，包含 _cache_meta 元信息
    """
    stock_name = stock_name or stock_code

    # 1. 如果不强制刷新，尝试读取缓存
    if not force_refresh:
        cached = load_intel_cache(stock_code)

        if cached:
            meta = cached.get('_cache_meta', {})

            # 缓存过期（>7天），强制重新搜索
            if meta.get('is_expired'):
                logger.info(f"缓存已过期({meta.get('age_days')}天)，重新搜索: {stock_code}")
                # fall through to search
            elif meta.get('is_stale'):
                # 缓存可用但过时（3~7天），返回缓存并标记
                logger.info(f"缓存可用但过时({meta.get('age_days')}天)，建议刷新: {stock_code}")
                return cached
            else:
                # 缓存新鲜（≤3天），直接返回
                logger.info(f"使用新鲜缓存({meta.get('age_days')}天): {stock_code}")
                return cached

    # 2. 执行搜索
    logger.info(f"执行情报搜索: {stock_name}({stock_code})")
    intel_data = search_intel(stock_code, stock_name)

    # 添加缓存元信息
    intel_data['_cache_meta'] = {
        'age_days': 0,
        'is_fresh': True,
        'is_stale': False,
        'is_expired': False,
        'cache_time': intel_data.get('tracked_at', ''),
    }

    return intel_data


def get_intel_for_analysis(stock_code: str, stock_name: str = None,
                           force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    """获取格式化后的情报数据（用于LLM分析注入）

    返回 format_intel_for_injection 格式的数据，
    可直接传入 StockAgentTeam.analyze(web_intelligence=...)

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        force_refresh: 是否强制刷新

    Returns:
        格式化后的情报数据，或 None（搜索不可用时）
    """
    intel_data = get_intel(stock_code, stock_name, force_refresh)

    # 移除缓存元信息（使用副本避免修改原始数据）
    meta = intel_data.get('_cache_meta', None)
    intel_copy = {k: v for k, v in intel_data.items() if k != '_cache_meta'}

    # 检查是否有搜索结果
    search_stats = intel_copy.get('search_stats', {})
    if not search_stats.get('searched', False) and not intel_data.get('news') and not intel_data.get('research'):
        return None

    # 转换为注入格式
    formatted = {}
    for intel_type in ['news', 'research', 'sentiment', 'industry', 'macro']:
        items = intel_data.get(intel_type, [])
        if items:
            formatted[intel_type] = items

    # 如果格式化后为空，返回 None
    if not formatted:
        return None

    return formatted

