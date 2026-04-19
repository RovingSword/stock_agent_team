"""
网络情报搜索器
支持多种搜索引擎API，实现自动情报搜集
"""
import json
import time
from typing import Dict, Any, List, Optional
import requests

from utils.logger import get_logger
from config.intel_config import (
    BING_API_KEY, BING_ENDPOINT,
    GOOGLE_API_KEY, GOOGLE_CX,
    SERPER_API_KEY,
    SEARCH_TIMEOUT, MAX_RESULTS_PER_TYPE,
    has_search_capability, get_active_search_provider
)

logger = get_logger('intel_searcher')


class IntelSearcher:
    """网络情报搜索器"""
    
    def __init__(self):
        self.timeout = SEARCH_TIMEOUT
        self.max_results = MAX_RESULTS_PER_TYPE
        self.provider = get_active_search_provider()
    
    def is_available(self) -> bool:
        """检查搜索能力是否可用"""
        return has_search_capability()
    
    def search(self, query: str, max_results: int = None) -> List[Dict[str, Any]]:
        """
        执行搜索
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数
            
        Returns:
            搜索结果列表，每个结果包含 title, snippet, url, time
        """
        if not self.is_available():
            logger.warning("未配置搜索API，无法自动搜索")
            return []
        
        max_results = max_results or self.max_results
        
        if self.provider == "bing":
            return self._search_bing(query, max_results)
        elif self.provider == "google":
            return self._search_google(query, max_results)
        elif self.provider == "serper":
            return self._search_serper(query, max_results)
        else:
            return []
    
    def _search_bing(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Bing搜索"""
        try:
            headers = {"Ocp-Apim-Subscription-Key": BING_API_KEY}
            params = {
                "q": query,
                "count": max_results,
                "mkt": "zh-CN",
                "responseFilter": "Webpages"
            }
            
            response = requests.get(
                BING_ENDPOINT,
                headers=headers,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            web_pages = data.get("webPages", {}).get("value", [])
            for item in web_pages[:max_results]:
                results.append({
                    "title": item.get("name", ""),
                    "snippet": item.get("snippet", ""),
                    "url": item.get("url", ""),
                    "time": None  # Bing不提供时间
                })
            
            logger.info(f"Bing搜索成功: {query} -> {len(results)}条结果")
            return results
            
        except Exception as e:
            logger.error(f"Bing搜索失败: {e}")
            return []
    
    def _search_google(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Google Custom Search"""
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": GOOGLE_API_KEY,
                "cx": GOOGLE_CX,
                "q": query,
                "num": max_results,
                "hl": "zh-CN"
            }
            
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            items = data.get("items", [])
            for item in items[:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "url": item.get("link", ""),
                    "time": None
                })
            
            logger.info(f"Google搜索成功: {query} -> {len(results)}条结果")
            return results
            
        except Exception as e:
            logger.error(f"Google搜索失败: {e}")
            return []
    
    def _search_serper(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Serper搜索 (Google结果)"""
        try:
            url = "https://google.serper.dev/search"
            headers = {
                "X-API-KEY": SERPER_API_KEY,
                "Content-Type": "application/json"
            }
            payload = {
                "q": query,
                "hl": "zh-cn",
                "gl": "cn"
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            # Serper返回organic结果
            organic = data.get("organic", [])
            for item in organic[:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "url": item.get("link", ""),
                    "time": item.get("date")
                })
            
            logger.info(f"Serper搜索成功: {query} -> {len(results)}条结果")
            return results
            
        except Exception as e:
            logger.error(f"Serper搜索失败: {e}")
            return []
    
    def search_multiple(self, queries: List[str], max_results_per_query: int = None) -> List[Dict[str, Any]]:
        """批量搜索多个查询"""
        all_results = []
        for query in queries:
            results = self.search(query, max_results_per_query)
            all_results.extend(results)
            time.sleep(0.5)  # 避免请求过快
        return all_results


# 全局实例
intel_searcher = IntelSearcher()


def format_intel_for_injection(search_results: Dict[str, List[Dict]]) -> Dict[str, Any]:
    """
    将搜索结果格式化为可注入的情报格式
    
    Args:
        search_results: {type: [results]} 格式的搜索结果
        
    Returns:
        格式化后的情报数据
    """
    formatted = {}
    
    for intel_type, results in search_results.items():
        formatted[intel_type] = [
            {
                "title": r.get("title", ""),
                "summary": r.get("snippet", ""),
                "url": r.get("url", ""),
                "time": r.get("time"),
                "sentiment": "neutral",  # 默认中性，后续可接入情感分析
                "relevance": 0.5
            }
            for r in results
        ]
    
    return formatted
