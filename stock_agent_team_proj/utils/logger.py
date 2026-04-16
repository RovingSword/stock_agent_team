"""
日志工具
"""
import logging
import os
from datetime import datetime

from config import LOG_CONFIG, LOGS_DIR


def get_logger(name: str) -> logging.Logger:
    """获取日志记录器"""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(getattr(logging, LOG_CONFIG['level']))
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(LOG_CONFIG['format'])
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # 文件处理器
        log_file = os.path.join(
            LOGS_DIR, 
            f"{LOG_CONFIG['file_prefix']}_{datetime.now().strftime('%Y%m%d')}.log"
        )
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(LOG_CONFIG['format'])
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger
