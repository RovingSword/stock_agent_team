#!/bin/bash
# 启动Web服务器脚本

cd "$(dirname "$0")/.." || exit 1

echo "=========================================="
echo "股票Agent分析系统 - Web服务启动"
echo "=========================================="

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    exit 1
fi

# 检查依赖
echo "📦 检查依赖..."
python3 -c "import fastapi" 2>/dev/null || {
    echo "⚠️  FastAPI 未安装，正在安装..."
    pip install fastapi uvicorn -q
}

# 启动服务
echo ""
echo "🚀 启动Web服务..."
echo "📍 访问地址: http://localhost:8000"
echo "📍 API文档: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止服务"
echo "=========================================="

# 使用uvicorn启动
python3 -m uvicorn web.app:app --host 0.0.0.0 --port 8000 --reload
