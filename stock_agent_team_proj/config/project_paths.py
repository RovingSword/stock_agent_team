"""
项目根路径与 import 引导（单点维护，避免各处重复 sys.path 片段）。
在 uvicorn、pytest、脚本入口中均应先调用 ensure_project_root_on_path()（或由 config 包代劳）。
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def ensure_project_root_on_path() -> Path:
    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    return PROJECT_ROOT
