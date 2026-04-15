#!/bin/bash
# =============================================================================
# Stock Agent Team - 停止脚本
# 优雅停止 Docker 容器
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
echo -e "${BLUE}  股票 Agent Team 停止脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 切换到部署目录
cd "$DEPLOY_DIR"

# 检查是否有运行的容器
if ! docker-compose ps &> /dev/null; then
    echo -e "${YELLOW}没有发现运行中的容器${NC}"
    exit 0
fi

# 显示当前容器状态
echo -e "${YELLOW}当前容器状态:${NC}"
docker-compose ps
echo ""

# 询问确认（可选，通过参数跳过）
FORCE_STOP=false
if [[ "$1" == "-f" ]] || [[ "$1" == "--force" ]]; then
    FORCE_STOP=true
fi

if [ "$FORCE_STOP" = false ]; then
    read -p "确认停止所有容器? [y/N] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}取消停止操作${NC}"
        exit 0
    fi
fi

# 停止容器
echo -e "${YELLOW}正在停止容器...${NC}"
docker-compose down --remove-orphans

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✓ 停止成功！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 清理选项
echo -e "${YELLOW}是否清理未使用的镜像和卷?${NC}"
read -p "这将删除未使用的 Docker 资源 [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}清理未使用资源...${NC}"
    docker image prune -f
    docker volume prune -f 2>/dev/null || true
    echo -e "${GREEN}✓ 清理完成${NC}"
fi

echo ""
echo -e "下次启动: ${YELLOW}./start.sh${NC}"
echo ""
