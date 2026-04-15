"""
配置模块初始化
"""
import os

from .config_loader import (
    ConfigLoader,
    ProviderConfig,
    AgentConfig,
    DiscussionConfig,
    get_config_loader,
    get_llm_config,
)

# 向后兼容的常量（来自旧版 config.py）
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
DATABASE_PATH = os.path.join(DATA_DIR, 'stock_analysis.db')
REPORTS_DIR = os.path.join(DATA_DIR, 'reports')

# 日志配置
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
LOG_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file_prefix': 'agent_team',
    'file_suffix': '.log',
    'max_file_size': 10 * 1024 * 1024,  # 10MB
    'backup_count': 5,
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        '': {
            'handlers': ['default'],
            'level': 'INFO',
            'propagate': True
        }
    }
}

# Agent权重配置
AGENT_WEIGHTS = {
    'technical': 0.35,
    'intelligence': 0.30,
    'risk': 0.20,
    'fundamental': 0.15,
}

# 评分阈值配置
SCORE_THRESHOLDS = {
    'strong_buy': 8.0,
    'buy': 7.0,
    'watch': 5.0,
    'avoid': 3.0,
}

# 仓位管理配置
POSITION_LIMITS = {
    'max_single_position': 0.20,
    'max_sector_position': 0.40,
    'max_total_position': 0.80,
    'min_reserve_position': 0.20,
}

# 止损止盈配置
STOP_LOSS_CONFIG = {
    'default_stop_loss_rate': 0.06,
    'max_stop_loss_rate': 0.10,
    'min_stop_loss_rate': 0.03,
}

TAKE_PROFIT_CONFIG = {
    'target_1_rate': 0.05,
    'target_2_rate': 0.08,
    'target_3_rate': 0.12,
    'min_profit_loss_ratio': 1.5,
}

# 持股周期配置
HOLDING_CONFIG = {
    'min_holding_days': 3,
    'max_holding_days': 10,
    'target_holding_days': 5,
}

# 技术分析参数
TECHNICAL_PARAMS = {
    'ma_periods': [5, 10, 20, 60],
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

__all__ = [
    'ConfigLoader',
    'ProviderConfig',
    'AgentConfig', 
    'DiscussionConfig',
    'get_config_loader',
    'get_llm_config',
    # 向后兼容
    'DATA_DIR',
    'DATABASE_PATH',
    'REPORTS_DIR',
    'LOGS_DIR',
    'LOG_CONFIG',
    'AGENT_WEIGHTS',
    'SCORE_THRESHOLDS',
    'POSITION_LIMITS',
    'STOP_LOSS_CONFIG',
    'TAKE_PROFIT_CONFIG',
    'HOLDING_CONFIG',
    'TECHNICAL_PARAMS',
]
