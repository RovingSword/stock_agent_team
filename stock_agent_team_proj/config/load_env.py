"""
加载项目根目录 .env，供 config / Web / CLI 在导入密钥前统一调用。
"""
from __future__ import annotations

import os
from pathlib import Path

from .project_paths import PROJECT_ROOT

try:
    from dotenv import load_dotenv as _dotenv_load
except ModuleNotFoundError:
    _dotenv_load = None


def load_project_env(env_path: Path | None = None) -> bool:
    """加载项目根目录下的 .env；缺少 python-dotenv 时退回简易解析。"""
    env_path = Path(env_path) if env_path is not None else PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return False

    if _dotenv_load is not None:
        return bool(_dotenv_load(dotenv_path=env_path))

    loaded = False
    with env_path.open("r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            if not key:
                continue

            os.environ.setdefault(key, value)
            loaded = True

    return loaded
