"""
日志工具
"""
import logging
import os
import re
from datetime import datetime
from typing import Any

from config import LOG_CONFIG, LOGS_DIR

_RE_API_KEY = re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}\b", re.IGNORECASE)
_RE_BEARER = re.compile(r"(?i)Bearer\s+[A-Za-z0-9\-\._~\+/=]+", re.IGNORECASE)


def _redact_log_text(text: Any) -> str:
    if not isinstance(text, str):
        return str(text) if text is not None else ""
    s = _RE_API_KEY.sub("sk-***REDACTED***", text)
    s = _RE_BEARER.sub("Bearer ***REDACTED***", s)
    return s


class _RedactSecretsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        record.msg = _redact_log_text(record.msg)  # type: ignore[assignment]
        if record.args:
            if isinstance(record.args, dict):
                return True
            record.args = tuple(  # type: ignore[assignment]
                _redact_log_text(a) if isinstance(a, str) else a
                for a in record.args
            )
        return True


def get_logger(name: str) -> logging.Logger:
    """获取日志记录器"""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(getattr(logging, LOG_CONFIG['level']))
        redact = _RedactSecretsFilter()
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.addFilter(redact)
        console_formatter = logging.Formatter(LOG_CONFIG['format'])
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # 文件处理器
        os.makedirs(LOGS_DIR, exist_ok=True)
        log_file = os.path.join(
            LOGS_DIR, 
            f"{LOG_CONFIG['file_prefix']}_{datetime.now().strftime('%Y%m%d')}.log"
        )
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.addFilter(_RedactSecretsFilter())
        file_formatter = logging.Formatter(LOG_CONFIG['format'])
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger
