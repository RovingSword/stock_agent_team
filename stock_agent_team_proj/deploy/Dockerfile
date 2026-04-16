# =============================================================================
# Stock Agent Team - Dockerfile
# 中短线波段 Agent Team 系统 Docker 镜像
# =============================================================================

# 使用官方 Python 运行时作为基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    TZ=Asia/Shanghai \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# 第一阶段：安装 Python 依赖
# =============================================================================
# 先复制 requirements.txt 以利用 Docker 缓存层
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# =============================================================================
# 第二阶段：复制应用代码
# =============================================================================
# 复制项目文件
COPY . .

# 创建数据目录
RUN mkdir -p /app/data/reports /app/data/logs

# =============================================================================
# 暴露端口（如果有 Web 服务）
EXPOSE 5000

# =============================================================================
# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import sqlite3; sqlite3.connect('/app/data/database.db')" || exit 1

# =============================================================================
# 默认启动命令
CMD ["python", "main.py"]
