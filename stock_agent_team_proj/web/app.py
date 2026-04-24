"""
Web应用主文件
中短线波段 Agent Team 系统 Web界面
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from config.project_paths import PROJECT_ROOT, ensure_project_root_on_path
from config.load_env import load_project_env

ensure_project_root_on_path()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# 启动时加载 .env，确保 Web 进程可读取本地 API Key。
load_project_env()

from storage.database import Database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    app.state.db = Database()
    yield
    # 关闭时清理资源
    pass


# 创建FastAPI应用
app = FastAPI(
    title="股票Agent分析系统",
    description="中短线波段交易分析Agent团队系统Web界面",
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

# 注册API路由
from web.api import analyze, history, config, kline, watchlist, intel, performance, charts, scheduler

app.include_router(analyze.router, prefix="/api", tags=["股票分析"])
app.include_router(history.router, prefix="/api", tags=["历史记录"])
app.include_router(config.router, prefix="/api", tags=["配置管理"])
app.include_router(kline.router, prefix="/api", tags=["K线数据"])
app.include_router(watchlist.router, prefix="/api", tags=["观察池管理"])
app.include_router(intel.router, prefix="/api", tags=["情报追踪"])
app.include_router(performance.router, prefix="/api", tags=["历史表现"])
app.include_router(charts.router, prefix="/api", tags=["图表数据"])
app.include_router(scheduler.router, prefix="/api", tags=["定时任务"])


@app.get("/", response_class=HTMLResponse)
async def root():
    """首页"""
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return {"message": "Stock Agent Team Web Interface"}


@app.get("/health")
async def health_check():
    """增强版健康检查 - 包含依赖状态"""
    from config.config_loader import get_llm_config
    from storage.database import db
    import os
    from pathlib import Path
    from datetime import datetime
    
    status = {
        "status": "healthy",
        "service": "stock-agent-team-web",
        "timestamp": datetime.now().isoformat(),
        "version": "1.2.0",
        "dependencies": {}
    }
    
    # 检查数据库
    try:
        db_status = db.get_health_status() if hasattr(db, 'get_health_status') else "connected"
        status["dependencies"]["database"] = {"status": "healthy", "details": db_status}
    except Exception as e:
        status["dependencies"]["database"] = {"status": "degraded", "error": str(e)}
        status["status"] = "degraded"
    
    # 检查LLM配置
    try:
        config = get_llm_config()
        validation = config.validate()
        llm_status = "healthy" if validation.get("valid", False) else "warning"
        missing = config.get_missing_api_keys()
        status["dependencies"]["llm"] = {
            "status": llm_status,
            "default_provider": config.default_provider,
            "missing_keys": len(missing)
        }
        if missing:
            status["status"] = "degraded"
    except Exception as e:
        status["dependencies"]["llm"] = {"status": "error", "error": str(e)}
        status["status"] = "degraded"
    
    # 检查数据目录和缓存
    try:
        data_dir = Path("data")
        status["dependencies"]["data"] = {
            "status": "healthy",
            "reports": len(list(data_dir.glob("reports/*.md"))) if data_dir.exists() else 0,
            "intel_cache": len(list((data_dir / "intel").glob("*.json"))) if (data_dir / "intel").exists() else 0
        }
    except Exception:
        status["dependencies"]["data"] = {"status": "warning"}
    
    # 添加trace信息
    status["observability"] = {
        "trace_id": f"health-{int(datetime.now().timestamp())}",
        "log_level": "INFO"
    }
    
    return status


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.app:app", host="0.0.0.0", port=8000, reload=True)
