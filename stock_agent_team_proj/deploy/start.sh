#!/bin/bash
# =============================================================================
# Stock Agent Team - 启动脚本
# 一键启动 Docker 容器
# =============================================================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$SCRIPT_DIR"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  股票 Agent Team 启动脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查 Docker 是否安装
echo -e "${YELLOW}[1/5] 检查 Docker 环境...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker 未安装，请先安装 Docker${NC}"
    echo "  参考: https://docs.docker.com/engine/install/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}✗ Docker Compose 未安装${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker 环境检查通过${NC}"
echo ""

# 检查 Docker 服务状态
echo -e "${YELLOW}[2/5] 检查 Docker 服务状态...${NC}"
if ! docker info &> /dev/null; then
    echo -e "${RED}✗ Docker 服务未运行，请启动 Docker${NC}"
    echo "  Ubuntu: sudo systemctl start docker"
    echo "  CentOS: sudo systemctl start docker"
    exit 1
fi
echo -e "${GREEN}✓ Docker 服务运行正常${NC}"
echo ""

# 切换到部署目录
cd "$DEPLOY_DIR"

# 创建必要的目录
echo -e "${YELLOW}[3/5] 创建必要目录...${NC}"
mkdir -p ../data/reports
mkdir -p ../data/logs
echo -e "${GREEN}✓ 目录创建完成${NC}"
echo ""

# 停止旧容器（如存在）
echo -e "${YELLOW}[4/5] 停止旧容器...${NC}"
docker-compose down --remove-orphans 2>/dev/null || true
echo -e "${GREEN}✓ 旧容器已清理${NC}"
echo ""

# 构建并启动容器
echo -e "${YELLOW}[5/5] 构建并启动容器...${NC}"
echo ""
docker-compose up -d --build

# 等待容器启动
echo ""
echo -e "${YELLOW}等待容器启动...${NC}"
sleep 5

# 检查容器状态
if docker-compose ps | grep -q "Up"; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  ✓ 启动成功！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "容器状态:"
    docker-compose ps
    echo ""
    echo -e "查看日志命令: ${YELLOW}docker-compose logs -f${NC}"
    echo -e "进入容器:     ${YELLOW}docker-compose exec stock-agent bash${NC}"
    echo -e "停止服务:     ${YELLOW}./stop.sh${NC}"
    echo ""
else
    echo ""
    echo -e "${RED}✗ 启动可能存在问题，请检查日志${NC}"
    echo ""
    echo -e "查看日志: ${YELLOW}docker-compose logs${NC}"
    echo ""
    exit 1
fi
