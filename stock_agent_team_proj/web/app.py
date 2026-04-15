"""
Web应用主文件
中短线波段 Agent Team 系统 Web界面
"""
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
from web.api import analyze, history, config

app.include_router(analyze.router, prefix="/api", tags=["股票分析"])
app.include_router(history.router, prefix="/api", tags=["历史记录"])
app.include_router(config.router, prefix="/api", tags=["配置管理"])


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
    """健康检查"""
    return {"status": "healthy", "service": "stock-agent-team-web"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("stock_agent_team.web.app:app", host="0.0.0.0", port=8000, reload=True)
