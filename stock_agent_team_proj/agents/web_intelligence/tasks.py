"""
网络情报任务执行器
定义主Agent执行搜索的具体任务格式
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional


@dataclass
class SearchTask:
    """单个搜索任务"""
    task_type: str      # news, research, sentiment, industry, macro
    query: str          # 搜索关键词
    description: str    # 任务描述
    max_results: int = 5


@dataclass  
class SearchResult:
    """搜索结果"""
    task_type: str
    items: List[Dict[str, Any]]  # [{title, summary, url, time}]


# 任务模板 - 供主Agent参考
TASK_TEMPLATES = {
    'news': {
        'keywords': ['最新消息', '新闻', '公告', '动态'],
        'sources_hint': '新浪财经、东方财富、同花顺'
    },
    'research': {
        'keywords': ['研报', '评级', '目标价', '券商观点'],
        'sources_hint': '东方财富研报、慧博投研'
    },
    'sentiment': {
        'keywords': ['股吧', '讨论', '雪球', '观点'],
        'sources_hint': '雪球、东方财富股吧、微博'
    },
    'industry': {
        'keywords': ['行业政策', '产业链', '竞争格局'],
        'sources_hint': '行业媒体、政府公告'
    },
    'macro': {
        'keywords': ['A股', '大盘', '趋势', '政策'],
        'sources_hint': '财经媒体'
    }
}


def format_task_for_agent(task: SearchTask) -> str:
    """格式化任务描述，供主Agent执行
    
    Args:
        task: 搜索任务
        
    Returns:
        格式化的任务描述
    """
    template = TASK_TEMPLATES.get(task.task_type, {})
    sources = template.get('sources_hint', '互联网')
    
    return f"""
【{task.description}】
搜索关键词: {task.query}
建议来源: {sources}
最多获取: {task.max_results} 条结果

请搜索并整理相关信息，返回格式:
- 标题
- 摘要/核心观点
- 来源链接(如有)
- 发布时间(如有)
""".strip()


def create_search_results(
    task_type: str,
    raw_results: List[Dict[str, Any]]
) -> SearchResult:
    """创建搜索结果对象
    
    Args:
        task_type: 任务类型
        raw_results: 原始搜索结果
        
    Returns:
        SearchResult
    """
    return SearchResult(
        task_type=task_type,
        items=raw_results
    )
