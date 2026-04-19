"""
观察池定时任务配置

配置说明：
1. 每日16:30：采集龙虎榜、热门板块、机构调研数据
2. 每周六10:00：更新观察池+分析候选股票
3. 分析完成后推送结果到主对话

使用方式：
  # 列出所有任务
  python main.py schedule list
  
  # 启动调度器
  python main.py schedule start
  
  # 手动执行特定任务
  python main.py auto --task daily_collect    # 采集数据
  python main.py auto --task weekly_update    # 完整流程
  
  # 执行完整流程（采集+筛选+分析）
  python main.py auto
"""

# 默认任务配置
DEFAULT_TASKS = [
    {
        "task_id": "daily_collect",
        "task_name": "每日数据采集",
        "task_type": "collect",
        "schedule_time": "16:30",
        "description": "每日收盘后采集龙虎榜、热门板块、机构调研数据",
    },
    {
        "task_id": "weekly_update",
        "task_name": "每周观察池更新",
        "task_type": "full",
        "schedule_time": "10:00",
        "weekday": 6,  # 周六
        "description": "每周六执行完整流程：采集数据、筛选候选股、分析并推送结果",
    },
]

# 推送配置
PUSH_CONFIG = {
    "enabled": True,
    "push_on_buy_recommended": True,  # 有推荐买入时推送
    "push_on_weekly_update": True,     # 每周更新后推送
    "min_recommendations": 1,          # 最少推荐数量才推送
}

# 分析配置
ANALYSIS_CONFIG = {
    "max_candidates_per_run": 5,    # 每次最多分析数量
    "min_score_threshold": 60.0,    # 最低评分阈值
    "auto_archive_days": 30,       # 超过N天未分析自动归档
}
