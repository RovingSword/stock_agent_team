# 股票 Agent Team 生产环境部署指南

## 目录
- [环境要求](#环境要求)
- [快速部署（Docker）](#快速部署docker)
- [手动部署](#手动部署)
- [配置说明](#配置说明)
- [定时任务配置](#定时任务配置)
- [日志管理](#日志管理)
- [监控与告警](#监控与告警)
- [常见问题](#常见问题)

---

## 环境要求

### 服务器配置

| 项目 | 最低配置 | 推荐配置 |
|------|----------|----------|
| CPU | 2核 | 4核+ |
| 内存 | 4GB | 8GB+ |
| 硬盘 | 20GB | 50GB+ SSD |
| 系统 | Ubuntu 20.04+ / CentOS 7+ | Ubuntu 22.04 LTS |

### 软件环境

- **Python**: 3.8+ (推荐 3.9 或 3.10)
- **Docker**: 20.10+ (如使用 Docker 部署)
- **Docker Compose**: 2.0+ (如使用 Docker 部署)

---

## 快速部署（Docker）

### 1. 准备环境

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | bash

# 安装 Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# 启动 Docker 服务
systemctl start docker
systemctl enable docker
```

### 2. 一键启动

```bash
cd stock_agent_team/deploy

# 构建并启动容器
docker-compose up -d

# 查看容器状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 3. 验证部署

```bash
# 进入容器测试运行
docker-compose exec stock-agent python main.py

# 检查日志
docker-compose logs --tail=50
```

### 4. 停止服务

```bash
# 优雅停止
./stop.sh

# 或者直接使用 docker-compose
docker-compose down
```

---

## 手动部署

### 1. 安装 Python 环境

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.10 python3.10-venv python3-pip

# CentOS/RHEL
sudo yum install -y python310 python310-pip python310-devel
```

### 2. 创建用户和目录

```bash
# 创建专用用户（推荐）
sudo useradd -m -s /bin/bash stockagent
sudo mkdir -p /opt/stock_agent_team
sudo chown -R stockagent:stockagent /opt/stock_agent_team

# 创建数据目录
sudo mkdir -p /var/log/stock_agent_team
sudo chown stockagent:stockagent /var/log/stock_agent_team
```

### 3. 上传项目文件

```bash
# 使用 scp 上传（或 git clone）
scp -r stock_agent_team stockagent@your-server:/opt/stock_agent_team/

# 或者使用 git
sudo git clone <repo_url> /opt/stock_agent_team
sudo chown -R stockagent:stockagent /opt/stock_agent_team
```

### 4. 创建虚拟环境并安装依赖

```bash
cd /opt/stock_agent_team

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. 初始化数据库

```bash
cd /opt/stock_agent_team

# 创建必要目录
mkdir -p data/reports data/logs

# 首次运行会自动创建数据库
python main.py
```

### 6. 配置环境变量（可选）

创建 `.env` 文件：

```bash
cat > /opt/stock_agent_team/.env << EOF
# 日志目录
LOG_DIR=/var/log/stock_agent_team

# 数据目录
DATA_DIR=/opt/stock_agent_team/data

# Python 环境
PYTHONPATH=/opt/stock_agent_team

# 时区设置
TZ=Asia/Shanghai
EOF
```

---

## 配置说明

### 配置文件位置

所有配置集中在 `config.py` 中，主要配置项：

#### 日志配置

```python
LOG_CONFIG = {
    'level': 'INFO',                    # 日志级别: DEBUG/INFO/WARNING/ERROR
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file_prefix': 'agent_team',        # 日志文件前缀
    'max_file_size': 10 * 1024 * 1024,  # 单个日志文件最大 10MB
    'backup_count': 5,                   # 保留的旧日志文件数量
}
```

#### 复盘配置

```python
REVIEW_CONFIG = {
    'daily_review_time': time(17, 0),   # 每日复盘时间（收盘后）
    'weekly_review_day': 4,             # 周度复盘（0=周一, 4=周五）
    'monthly_review_day': -1,           # 月度复盘（-1=月末最后交易日）
}
```

#### 交易参数

```python
# 评分阈值
SCORE_THRESHOLDS = {
    'strong_buy': 8.0,   # 强烈买入
    'buy': 7.0,          # 建议买入
    'watch': 5.0,        # 观望
    'avoid': 3.0,        # 回避
}

# 仓位限制
POSITION_LIMITS = {
    'max_single_position': 0.20,    # 单只股票最大 20%
    'max_total_position': 0.80,     # 总仓位上限 80%
}
```

---

## 定时任务配置

### 方案一：APScheduler（推荐）

创建调度脚本 `scheduler.py`：

```python
#!/usr/bin/env python3
"""
股票 Agent Team 定时任务调度器
"""
import sys
import time
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# 添加项目路径
sys.path.insert(0, '/opt/stock_agent_team')

from main import StockAgentTeam
from config import REVIEW_CONFIG
from utils.logger import get_logger

logger = get_logger('scheduler')

# 股票池（可配置）
WATCH_STOCKS = [
    ('300750', '宁德时代'),
    ('600519', '贵州茅台'),
    # 添加更多股票...
]

def daily_review():
    """每日复盘任务"""
    logger.info("开始执行每日复盘...")
    try:
        team = StockAgentTeam()
        result = team.review('daily')
        logger.info(f"每日复盘完成: {result.get('summary', 'N/A')}")
    except Exception as e:
        logger.error(f"每日复盘失败: {e}")

def weekly_review():
    """周度复盘任务"""
    logger.info("开始执行周度复盘...")
    try:
        team = StockAgentTeam()
        result = team.review('weekly')
        logger.info(f"周度复盘完成: {result.get('summary', 'N/A')}")
    except Exception as e:
        logger.error(f"周度复盘失败: {e}")

def analyze_stocks():
    """股票分析任务"""
    logger.info("开始执行股票分析...")
    try:
        team = StockAgentTeam()
        for code, name in WATCH_STOCKS:
            result = team.analyze(code, name)
            logger.info(f"{name}({code}) 分析完成，决策: {result.final_action}")
    except Exception as e:
        logger.error(f"股票分析失败: {e}")

def main():
    tz = pytz.timezone('Asia/Shanghai')
    scheduler = BlockingScheduler(timezone=tz)
    
    # 每日收盘后复盘 (16:00)
    scheduler.add_job(
        daily_review,
        CronTrigger(hour=16, minute=0, timezone=tz),
        id='daily_review',
        name='每日复盘'
    )
    
    # 周五收盘后周度复盘 (16:30)
    scheduler.add_job(
        weekly_review,
        CronTrigger(day_of_week='fri', hour=16, minute=30, timezone=tz),
        id='weekly_review',
        name='周度复盘'
    )
    
    # 交易日上午 9:35 分析（可选）
    scheduler.add_job(
        analyze_stocks,
        CronTrigger(hour=9, minute=35, timezone=tz),
        id='morning_analysis',
        name='早盘分析'
    )
    
    # 交易日下午 14:30 分析（可选）
    scheduler.add_job(
        analyze_stocks,
        CronTrigger(hour=14, minute=30, timezone=tz),
        id='afternoon_analysis',
        name='午盘分析'
    )
    
    logger.info("调度器启动成功")
    print("按 Ctrl+C 停止调度器")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("调度器已停止")
        sys.exit(0)

if __name__ == "__main__":
    main()
```

运行调度器：
```bash
# 后台运行
nohup python scheduler.py > scheduler.log 2>&1 &

# 查看进程
ps aux | grep scheduler

# 停止
pkill -f scheduler.py
```

### 方案二：Crontab

```bash
# 编辑 crontab
crontab -e

# 添加以下任务
# 每天 16:00 执行每日复盘
0 16 * * 1-5 cd /opt/stock_agent_team && /opt/stock_agent_team/venv/bin/python main.py --review daily >> /var/log/stock_agent_team/cron_review.log 2>&1

# 周五 16:30 执行周度复盘
30 16 * * 5 cd /opt/stock_agent_team && /opt/stock_agent_team/venv/bin/python main.py --review weekly >> /var/log/stock_agent_team/cron_review.log 2>&1

# 每天 9:35 执行早盘分析
35 9 * * 1-5 cd /opt/stock_agent_team && /opt/stock_agent_team/venv/bin/python main.py --analyze >> /var/log/stock_agent_team/cron_analysis.log 2>&1

# 每天 14:30 执行午盘分析
30 14 * * 1-5 cd /opt/stock_agent_team && /opt/stock_agent_team/venv/bin/python main.py --analyze >> /var/log/stock_agent_team/cron_analysis.log 2>&1

# 查看 crontab
crontab -l

# 查看 cron 日志
grep CRON /var/log/syslog
```

### 启动管理脚本

使用 systemd 管理（推荐）：

```bash
# 创建 systemd 服务文件
sudo cat > /etc/systemd/system/stock-agent.service << EOF
[Unit]
Description=Stock Agent Team Scheduler
After=network.target

[Service]
Type=simple
User=stockagent
WorkingDirectory=/opt/stock_agent_team
Environment="PYTHONPATH=/opt/stock_agent_team"
Environment="TZ=Asia/Shanghai"
ExecStart=/opt/stock_agent_team/venv/bin/python scheduler.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/stock_agent_team/service.log
StandardError=append:/var/log/stock_agent_team/service.log

[Install]
WantedBy=multi-user.target
EOF

# 启用并启动服务
sudo systemctl daemon-reload
sudo systemctl enable stock-agent
sudo systemctl start stock-agent

# 管理命令
sudo systemctl status stock-agent
sudo systemctl restart stock-agent
sudo systemctl stop stock-agent
```

---

## 日志管理

### 日志目录结构

```
/opt/stock_agent_team/data/logs/
├── agent_team_20240101.log      # 主日志
├── agent_team_20240102.log
└── ...

# 或在 Docker 环境下
/var/log/stock_agent_team/
├── agent_team.log               # 符号链接到最新日志
├── agent_team_20240101.log
└── agent_team_20240102.log
```

### 日志轮转配置

创建 `/etc/logrotate.d/stock_agent`：

```
/opt/stock_agent_team/data/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 stockagent stockagent
    sharedscripts
    postrotate
        # 通知应用重新打开日志文件
        kill -USR1 $(cat /var/run/stock_agent.pid 2>/dev/null) 2>/dev/null || true
    endscript
}
```

### 日志分析常用命令

```bash
# 实时查看日志
tail -f data/logs/agent_team_$(date +%Y%m%d).log

# 查看错误日志
grep ERROR data/logs/*.log

# 统计每日运行次数
grep "分析完成" data/logs/*.log | wc -l

# 查看今日所有日志
grep "$(date +%Y-%m-%d)" data/logs/*.log
```

---

## 监控与告警

### 基础监控脚本

创建 `monitor.py`：

```python
#!/usr/bin/env python3
"""
健康检查与告警脚本
"""
import os
import sys
import time
import psutil
from datetime import datetime
import sqlite3

sys.path.insert(0, '/opt/stock_agent_team')

from config import DATABASE_PATH, LOGS_DIR
from utils.logger import get_logger

logger = get_logger('monitor')

def check_process():
    """检查进程是否存活"""
    current_pid = os.getpid()
    try:
        proc = psutil.Process(current_pid)
        return True
    except:
        return False

def check_database():
    """检查数据库连接"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.execute("SELECT 1").fetchone()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"数据库检查失败: {e}")
        return False

def check_disk_space():
    """检查磁盘空间"""
    usage = psutil.disk_usage('/')
    return usage.percent < 90

def check_memory():
    """检查内存使用"""
    mem = psutil.virtual_memory()
    return mem.percent < 85

def check_log_file():
    """检查日志文件是否正常写入"""
    today = datetime.now().strftime('%Y%m%d')
    log_file = os.path.join(LOGS_DIR, f'agent_team_{today}.log')
    
    if not os.path.exists(log_file):
        return False
    
    # 检查最近5分钟是否有写入
    mtime = os.path.getmtime(log_file)
    return (time.time() - mtime) < 300

def health_check():
    """执行健康检查"""
    checks = {
        '进程状态': check_process(),
        '数据库': check_database(),
        '磁盘空间': check_disk_space(),
        '内存使用': check_memory(),
        '日志写入': check_log_file(),
    }
    
    all_ok = all(checks.values())
    
    report = f"[健康检查] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    for name, status in checks.items():
        report += f"  {name}: {'✓' if status else '✗'}\n"
    
    if all_ok:
        report += "状态: 健康\n"
    else:
        report += "状态: 异常 - 需要关注!\n"
    
    print(report)
    logger.info(report)
    
    return all_ok

if __name__ == "__main__":
    health_check()
```

### Crontab 监控任务

```bash
# 每5分钟检查一次
*/5 * * * * cd /opt/stock_agent_team && python monitor.py >> /var/log/stock_agent_team/health.log 2>&1
```

### 告警方式建议

1. **邮件告警**：配置 SMTP 发送告警邮件
2. **钉钉/企业微信**：使用 Webhook 推送告警
3. **短信告警**：使用云服务商短信 API
4. **监控平台**：接入 Prometheus + Grafana

---

## 常见问题

### Q1: 启动时报错 "ModuleNotFoundError"

```bash
# 确保已安装所有依赖
pip install -r requirements.txt

# 检查 PYTHONPATH
export PYTHONPATH=/opt/stock_agent_team:$PYTHONPATH
```

### Q2: Docker 容器内存不足

编辑 `docker-compose.yml`，调整资源限制：

```yaml
services:
  stock-agent:
    mem_limit: 2g
    mem_reservation: 1g
```

### Q3: 数据获取失败

系统内置多数据源自动切换，如持续失败：
1. 检查网络连接
2. 确认数据源可用性
3. 系统会自动降级使用缓存数据

### Q4: 数据库锁定

```bash
# 检查是否有进程占用
lsof data/database.db

# 如需修复数据库
sqlite3 data/database.db "PRAGMA integrity_check;"
```

### Q5: 日志文件过大

```bash
# 手动轮转日志
logrotate -f /etc/logrotate.d/stock_agent

# 或压缩旧日志
gzip data/logs/agent_team_$(date -d '1 week ago' +%Y%m%d).log
```

---

## 快速命令参考

```bash
# ===== Docker 部署 =====
cd deploy
docker-compose up -d              # 启动
docker-compose logs -f            # 查看日志
docker-compose exec stock-agent python main.py  # 测试运行
docker-compose down               # 停止

# ===== 手动部署 =====
cd /opt/stock_agent_team
source venv/bin/activate

# 运行主程序
python main.py

# 运行调度器
python scheduler.py

# 健康检查
python monitor.py

# ===== Systemd 管理 =====
sudo systemctl start stock-agent
sudo systemctl stop stock-agent
sudo systemctl restart stock-agent
sudo systemctl status stock-agent
```

---

## 安全建议

1. **不要**在生产环境使用 root 运行
2. 定期**备份数据库**：
   ```bash
   cp data/database.db data/database_$(date +%Y%m%d).db
   ```
3. 限制数据目录权限：
   ```bash
   chmod 700 data/
   chmod 600 data/database.db
   ```
4. 使用防火墙限制不必要的端口访问
5. 定期更新系统和依赖包

---

## 技术支持

如遇问题，请检查：
1. 日志文件 `data/logs/` 目录
2. 系统资源使用情况
3. 网络连通性
4. 数据源可用性
