"""
系统配置文件
"""
import os
from datetime import time
from typing import Dict, List

# ============================================================
# 基础路径配置
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DATABASE_PATH = os.path.join(DATA_DIR, 'database.db')
REPORTS_DIR = os.path.join(DATA_DIR, 'reports')
LOGS_DIR = os.path.join(DATA_DIR, 'logs')

# 确保目录存在
for dir_path in [DATA_DIR, REPORTS_DIR, LOGS_DIR]:
    os.makedirs(dir_path, exist_ok=True)


# ============================================================
# Agent权重配置
# ============================================================
AGENT_WEIGHTS = {
    'technical': 0.35,        # 技术分析员权重
    'intelligence': 0.30,     # 情报员权重
    'risk': 0.20,             # 风控官权重
    'fundamental': 0.15,      # 基本面分析师权重
}

# 权重调整范围
WEIGHT_RANGES = {
    'technical': (0.20, 0.50),
    'intelligence': (0.15, 0.45),
    'risk': (0.15, 0.35),
    'fundamental': (0.10, 0.30),
}


# ============================================================
# 评分阈值配置
# ============================================================
SCORE_THRESHOLDS = {
    'strong_buy': 8.0,        # 强烈买入
    'buy': 7.0,               # 建议买入
    'watch': 5.0,             # 观望
    'avoid': 3.0,             # 回避
}


# ============================================================
# 仓位管理配置
# ============================================================
POSITION_LIMITS = {
    'max_single_position': 0.20,    # 单只股票最大仓位
    'max_sector_position': 0.40,    # 单板块最大仓位
    'max_total_position': 0.80,     # 总仓位上限
    'min_reserve_position': 0.20,   # 最小保留仓位
}


# ============================================================
# 止损止盈配置
# ============================================================
STOP_LOSS_CONFIG = {
    'default_stop_loss_rate': 0.06,     # 默认止损比例 6%
    'max_stop_loss_rate': 0.10,         # 最大止损比例 10%
    'min_stop_loss_rate': 0.03,         # 最小止损比例 3%
}

TAKE_PROFIT_CONFIG = {
    'target_1_rate': 0.05,              # 第一止盈目标 5%
    'target_2_rate': 0.08,              # 第二止盈目标 8%
    'target_3_rate': 0.12,              # 第三止盈目标 12%
    'min_profit_loss_ratio': 1.5,       # 最小盈亏比
}


# ============================================================
# 持股周期配置
# ============================================================
HOLDING_CONFIG = {
    'min_holding_days': 3,              # 最少持股天数
    'max_holding_days': 10,             # 最多持股天数
    'target_holding_days': 5,           # 目标持股天数
}


# ============================================================
# Agent角色配置
# ============================================================
AGENT_CONFIG = {
    'technical': {
        'name': '技术分析员',
        'role': 'technical_analyst',
        'weight': 0.35,
        'description': '负责技术面分析，包括K线形态、均线系统、MACD、RSI、KDJ等技术指标',
    },
    'intelligence': {
        'name': '情报员',
        'role': 'intelligence_officer',
        'weight': 0.30,
        'description': '负责情报面分析，包括资金流向、龙虎榜、北向资金、热点题材、消息催化剂',
    },
    'risk': {
        'name': '风控官',
        'role': 'risk_controller',
        'weight': 0.20,
        'description': '负责风险控制，包括大盘风险、个股风险、交易风险评估，拥有一票否决权',
    },
    'fundamental': {
        'name': '基本面分析师',
        'role': 'fundamental_analyst',
        'weight': 0.15,
        'description': '负责基本面分析，包括业绩、估值、行业地位、风险排查',
    },
    'leader': {
        'name': '决策中枢',
        'role': 'leader',
        'description': '负责汇总各方分析，做出最终交易决策',
    },
    'review': {
        'name': '复盘分析师',
        'role': 'review_analyst',
        'description': '负责交易复盘，分析盈利亏损原因，优化策略权重',
    },
}


# ============================================================
# 复盘配置
# ============================================================
REVIEW_CONFIG = {
    # 触发条件
    'consecutive_loss_count': 3,        # 连续亏损笔数触发紧急复盘
    'single_loss_threshold': -0.10,     # 单笔亏损阈值触发异常复盘
    'total_drawdown_threshold': -0.15,  # 累计回撤阈值触发风控复盘
    
    # 定时复盘
    'daily_review_time': time(17, 0),   # 每日复盘时间
    'weekly_review_day': 4,              # 周度复盘星期 (0=周一, 4=周五)
    'monthly_review_day': -1,            # 月度复盘日 (-1表示最后一个交易日)
    
    # 权重调整
    'weight_adjustment_factor': 0.8,     # 权重调整系数
    'min_sample_size': 5,                # 最小样本数
}


# ============================================================
# 消息协议配置
# ============================================================
MESSAGE_TYPES = {
    'task_dispatch': '任务分发',
    'analysis_report': '分析报告',
    'risk_assessment': '风控评估',
    'trade_decision': '交易决策',
    'error_report': '错误报告',
    'review_request': '复盘请求',
    'review_report': '复盘报告',
}


# ============================================================
# 日志配置
# ============================================================
LOG_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file_prefix': 'agent_team',
    'max_file_size': 10 * 1024 * 1024,  # 10MB
    'backup_count': 5,
}


# ============================================================
# 数据源配置 (需要对接实际数据源)
# ============================================================
DATA_SOURCES = {
    'stock_quote': {
        'provider': 'akshare',          # 股票行情数据源
        'cache_enabled': True,
        'cache_ttl': 300,               # 缓存时间(秒)
    },
    'financial_data': {
        'provider': 'tushare',          # 财务数据源
        'cache_enabled': True,
        'cache_ttl': 3600,
    },
    'news_data': {
        'provider': 'sina',             # 新闻数据源
        'cache_enabled': True,
        'cache_ttl': 600,
    },
}


# ============================================================
# 系统状态
# ============================================================
SYSTEM_STATUS = {
    'is_trading': False,                # 是否交易中
    'is_paused': False,                 # 是否暂停
    'pause_reason': None,               # 暂停原因
    'last_analysis_time': None,         # 最后分析时间
    'total_trades': 0,                  # 总交易数
    'total_return': 0.0,                # 总收益率
}


# ============================================================
# 技术分析参数
# ============================================================
TECHNICAL_PARAMS = {
    'ma_periods': [5, 10, 20, 60],      # 均线周期
    'macd_params': {
        'fast': 12,
        'slow': 26,
        'signal': 9,
    },
    'rsi_period': 14,
    'kdj_params': {
        'n': 9,
        'm1': 3,
        'm2': 3,
    },
    'bollinger_params': {
        'n': 20,
        'k': 2,
    },
}


# ============================================================
# 输出模板配置
# ============================================================
REPORT_TEMPLATES = {
    'technical': {
        'sections': ['趋势判断', '位置判断', '入场信号', '交易计划', '风险提示'],
    },
    'intelligence': {
        'sections': ['题材分析', '资金流向', '消息催化剂', '市场情绪', '短线爆发力'],
    },
    'fundamental': {
        'sections': ['风险排查', '业绩概况', '估值情况', '行业地位'],
    },
    'risk': {
        'sections': ['大盘风险', '个股风险', '交易风险', '风控决策'],
    },
    'decision': {
        'sections': ['综合评分', '决策结论', '交易执行', '核心逻辑', '后续跟踪'],
    },
    'review_single': {
        'sections': ['交易概况', '各角色评分回顾', '交易过程回顾', '归因分析', '复盘结论'],
    },
    'review_weekly': {
        'sections': ['交易概况', '交易明细', '各角色表现', '盈利分析', '亏损分析', '市场环境', '下周建议'],
    },
    'review_monthly': {
        'sections': ['核心数据', '各角色表现', '策略验证', '权重调整', '策略更新', '下月规划'],
    },
}
