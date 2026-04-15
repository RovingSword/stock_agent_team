# Stock Agent Team 本地部署指南

本文档详细说明如何在本地环境（MacBook 和 Windows 11 + RTX3060）部署 Stock Agent Team 中短线波段交易分析系统。

---

## 目录

1. [项目概述](#项目概述)
2. [第一部分：MacBook 部署](#第一部分macbook-部署)
3. [第二部分：Windows 11 + RTX3060 部署](#第二部分windows-11--rtx3060-部署)
4. [第三部分：通用配置](#第三部分通用配置)
5. [第四部分：网络问题排查](#第四部分网络问题排查)

---

## 项目概述

### 项目结构

```
stock_agent_team/
├── agents/              # Agent 核心模块
│   ├── leader.py        # 团队领导
│   ├── technical_analyst.py    # 技术分析师
│   ├── intelligence_officer.py # 情报员
│   ├── risk_controller.py       # 风控官
│   └── fundamental_analyst.py   # 基本面分析师
├── storage/             # 数据存储
│   └── database.py      # SQLite 数据库操作
├── utils/               # 工具模块
│   ├── logger.py        # 日志模块
│   └── data_fetcher.py  # 数据获取
├── config.py            # 系统配置
├── main.py              # 程序入口
└── requirements.txt     # 依赖清单
```

### 核心依赖

| 依赖包 | 版本要求 | 说明 |
|--------|----------|------|
| pandas | >=1.5.0 | 数据分析核心 |
| numpy | >=1.21.0 | 数值计算 |
| akshare | >=1.10.0 | 股票数据源（东方财富等） |
| efinance | >=0.8.0 | 股票数据源（同花顺等） |
| APScheduler | >=3.10.0 | 定时任务调度 |
| requests | >=2.28.0 | HTTP 请求 |

### 运行方式

```bash
# 进入项目目录
cd stock_agent_team

# 运行主程序
python main.py
```

---

## 第一部分：MacBook 部署

### 1.1 Python 环境安装

#### 推荐方案：Homebrew + pyenv

**Step 1：安装 Homebrew（如已安装请跳过）**

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

**Step 2：安装 pyenv**

```bash
# 使用 Homebrew 安装
brew install pyenv

# 添加到 shell 配置（根据你使用的 shell 选择）
# zsh（如 macOS 默认）
echo 'eval "$(pyenv init -)"' >> ~/.zshrc
source ~/.zshrc

# 或 bash
echo 'eval "$(pyenv init -)"' >> ~/.bash_profile
source ~/.bash_profile
```

**Step 3：安装 Python**

```bash
# 列出可用版本
pyenv install --list | grep "3\."

# 安装 Python 3.10+（推荐 3.10 或 3.11）
pyenv install 3.10.12

# 设置全局版本
pyenv global 3.10.12

# 验证安装
python --version
```

#### 备选方案：Miniconda

```bash
# 下载 Miniconda
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh

# 或 Intel 版本
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh

# 安装
bash Miniconda3-latest-MacOSX-*.sh

# 创建虚拟环境
conda create -n stock_agent python=3.10
conda activate stock_agent
```

### 1.2 虚拟环境创建

**使用 pyenv-virtualenv**

```bash
# 安装 pyenv-virtualenv 插件
brew install pyenv-virtualenv

# 添加到 shell 配置
echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.zshrc
source ~/.zshrc

# 创建虚拟环境
cd stock_agent_team
pyenv virtualenv 3.10.12 stock_agent-env

# 设置项目本地 Python 版本
pyenv local stock_agent-env
```

**验证虚拟环境**

```bash
# 确认当前使用的 Python
which python
python --version
```

### 1.3 依赖安装

```bash
# 确保在项目目录下，且虚拟环境已激活
cd stock_agent_team
pyenv activate stock_agent-env  # 或 conda activate stock_agent

# 升级 pip
pip install --upgrade pip

# 安装依赖
pip install -r requirements.txt
```

**常见编译问题处理**

如果 `numba` 或 `cython` 安装失败：

```bash
# 安装 Xcode 命令行工具（编译依赖）
xcode-select --install

# 使用预编译版本
pip install numba --only-binary=:all:
```

### 1.4 数据库初始化

SQLite 数据库会在首次运行时自动创建。运行一次主程序即可：

```bash
python main.py
```

**数据库位置**

```
stock_agent_team/data/database.db
```

**手动初始化（如需要）**

```python
# 在 Python 中执行
from storage.database import db
# 数据库会自动创建
```

### 1.5 运行测试

```bash
# 快速测试 - 检查所有模块是否正常导入
python -c "
from agents.leader import Leader
from storage.database import db
from utils.logger import get_logger
print('✅ 所有模块导入成功')
"

# 完整运行测试
python main.py
```

**预期输出**

```
============================================================
中短线波段 Agent Team 系统
============================================================

【示例分析】宁德时代(300750)
------------------------------------------------------------
决策结果:
  股票: 宁德时代(300750)
  动作: [具体决策]
  ...
============================================================
系统运行完成
============================================================
```

### 1.6 常见问题（macOS）

#### 问题 1：权限被拒绝

```bash
# 修复项目目录权限
chmod -R 755 stock_agent_team/
```

#### 问题 2：zsh: command not found: pyenv

**解决方法**：确保 shell 配置正确加载

```bash
# 检查配置
cat ~/.zshrc | grep pyenv

# 手动加载（如上面命令无输出）
echo 'export PATH="/usr/local/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init -)"' >> ~/.zshrc
source ~/.zshrc
```

#### 问题 3：SSL 证书错误

```bash
# macOS 需要安装 SSL 证书
/Applications/Python\ 3.10/Install\ Certificates.command
```

#### 问题 4：数据目录写入权限

```bash
# 赋予 data 目录写权限
chmod -R 755 stock_agent_team/data/
```

---

## 第二部分：Windows 11 + RTX3060 部署

### 2.1 Python 环境安装

#### 推荐方案：Miniconda

**Step 1：下载 Miniconda**

访问 https://docs.conda.io/en/latest/miniconda.html，下载 Windows 64-bit installer (exe)。

**Step 2：安装 Miniconda**

1. 运行下载的 `.exe` 安装程序
2. 选择 "Just Me" 安装
3. 建议勾选 "Add Miniconda3 to my PATH environment variable"（可选）
4. 完成安装

**Step 3：打开 Anaconda Prompt**

在开始菜单中搜索 `Anaconda Prompt`，右键选择 "以管理员身份运行"。

### 2.2 虚拟环境创建

```powershell
# 创建虚拟环境
conda create -n stock_agent python=3.10

# 激活虚拟环境
conda activate stock_agent

# 确认激活成功
python --version
```

### 2.3 依赖安装

```powershell
# 确保在项目目录下
# 例如：如果项目在 D:\Projects\stock_agent_team
cd /d D:\Projects\stock_agent_team

# 升级 pip
pip install --upgrade pip

# 安装依赖
pip install -r requirements.txt
```

**Windows 下可能的编译问题**

1. **Visual Studio Build Tools**

   如果安装 `numba` 时报错，需要安装 C++ 编译工具：

   ```
   下载 Visual Studio Build Tools: https://visualstudio.microsoft.com/downloads/
   选择 "C++ 生成工具" 工作负载
   ```

2. **安装预编译版本**

   ```powershell
   # 避免编译，使用预编译二进制
   pip install numba --only-binary=:all:
   ```

### 2.4 CUDA/PyTorch GPU 环境配置（可选）

> ⚠️ **注意**：当前版本不强制要求 GPU，以下配置仅为未来扩展准备。

**Step 1：检查 RTX 3060 驱动**

```powershell
# 打开 NVIDIA 控制面板 -> 系统信息 -> 查看驱动版本
# 驱动版本需 >= 472.12
```

**Step 2：安装 CUDA Toolkit**

1. 下载 CUDA Toolkit 11.8：https://developer.nvidia.com/cuda-downloads
2. 选择 Windows -> x86_64 -> 11 -> exe(local)
3. 安装时选择 "Custom" -> 勾选所有组件

**Step 3：安装 PyTorch with CUDA**

```powershell
pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu118
```

**Step 4：验证 GPU 可用性**

```powershell
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0)}')"
```

### 2.5 数据库初始化

SQLite 数据库会在首次运行时自动创建：

```powershell
python main.py
```

**数据库位置**

```
D:\Projects\stock_agent_team\data\database.db
```

### 2.6 运行测试

**快速测试**

```powershell
python -c "from agents.leader import Leader; from storage.database import db; print('OK')"
```

**完整运行**

```powershell
python main.py
```

### 2.7 常见问题（Windows）

#### 问题 1：路径包含中文

**问题**：Python 对中文路径支持较差。

**解决方法**：

1. 将项目移动到纯英文路径，例如：
   ```
   D:\Projects\stock_agent_team\
   ```
2. 用户目录包含中文时，设置环境变量：
   ```powershell
   set PYTHONIOENCODING=utf-8
   ```

#### 问题 2：编码问题

Windows 默认使用 GBK 编码，可能导致 akshare/efinance 数据读取异常。

**解决方法**：在代码开头添加编码声明

```powershell
# 临时设置
set PYTHONIOENCODING=utf-8

# 永久设置：系统环境变量 -> 新建
# 变量名：PYTHONIOENCODING
# 变量值：utf-8
```

#### 问题 3：长路径支持

Windows 默认路径长度限制为 260 字符，可能导致问题。

**解决方法**：启用长路径

1. 按 `Win + R`，输入 `gpedit.msc`
2. 导航到：`计算机配置` -> `管理模板` -> `系统` -> `文件系统`
3. 启用 `启用 Win32 长路径`

#### 问题 4：防火墙拦截

**解决方法**：允许 Python 通过防火墙

```powershell
# 以管理员身份运行 PowerShell
netsh advfirewall firewall add rule name="Python" dir=in action=allow program="C:\Users\<用户名>\miniconda3\python.exe" enable=yes
```

#### 问题 5：PowerShell 执行策略

```powershell
# 以管理员身份运行
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### 问题 6：akshare 数据获取失败

Windows 下可能因代理或 SSL 问题导致失败：

```powershell
# 设置信任主机
pip install trustme

# 或更新证书
conda install certifi
```

---

## 第三部分：通用配置

### 3.1 定时任务设置

#### macOS: launchd 或 crontab

**方案 1：launchd（推荐）**

创建 `~/Library/LaunchAgents/com.stockagent.daily.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.stockagent.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/你的用户名/miniconda3/envs/stock_agent/bin/python</string>
        <string>/Users/你的用户名/Projects/stock_agent_team/main.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>25</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>/Users/你的用户名/Projects/stock_agent_team</string>
    <key>StandardOutPath</key>
    <string>/Users/你的用户名/Projects/stock_agent_team/data/logs/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/你的用户名/Projects/stock_agent_team/data/logs/launchd.error.log</string>
</dict>
</plist>
```

加载定时任务：

```bash
# 加载任务
launchctl load ~/Library/LaunchAgents/com.stockagent.daily.plist

# 卸载任务
launchctl unload ~/Library/LaunchAgents/com.stockagent.daily.plist

# 查看任务状态
launchctl list | grep stockagent
```

**方案 2：crontab**

```bash
# 编辑 crontab
crontab -e

# 添加任务（每天 9:25 执行）
25 9 * * 1-5 /Users/用户名/miniconda3/envs/stock_agent/bin/python /Users/用户名/Projects/stock_agent_team/main.py >> /Users/用户名/Projects/stock_agent_team/data/logs/cron.log 2>&1

# 每天收盘后 15:30 执行复盘
30 15 * * 1-5 /Users/用户名/miniconda3/envs/stock_agent/bin/python -c "from main import StockAgentTeam; StockAgentTeam().review('daily')" >> /Users/用户名/Projects/stock_agent_team/data/logs/cron.log 2>&1
```

#### Windows: 任务计划程序

**Step 1：打开任务计划程序**

按 `Win + R`，输入 `taskschd.msc`

**Step 2：创建基本任务**

1. 点击 "创建基本任务"
2. 名称：`StockAgent Daily`
3. 触发器：每天 9:25
4. 操作：启动程序
5. 程序/脚本：`C:\Users\你的用户名\miniconda3\envs\stock_agent\python.exe`
6. 添加参数：`D:\Projects\stock_agent_team\main.py`
7. 起始位置：`D:\Projects\stock_agent_team`

**Step 3：高级设置**

1. 右键任务 -> 属性
2. 勾选 "使用最高权限运行"
3. 配置针对 Windows 10/11 的兼容性设置

**PowerShell 脚本示例** (`run_analysis.ps1`)

```powershell
# D:\Projects\stock_agent_team\run_analysis.ps1
$ErrorActionPreference = "Stop"
$projectPath = "D:\Projects\stock_agent_team"
$logPath = "$projectPath\data\logs\scheduler.log"

try {
    Set-Location $projectPath
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "=== [$timestamp] 开始执行 ===" | Out-File -FilePath $logPath -Append
    
    $env:PYTHONIOENCODING = "utf-8"
    & "$projectPath\..\miniconda3\envs\stock_agent\python.exe" "$projectPath\main.py" 2>&1 | Out-File -FilePath $logPath -Append
    
    "=== [$timestamp] 执行完成 ===" | Out-File -FilePath $logPath -Append
} catch {
    "=== [ERROR] $_ ===" | Out-File -FilePath $logPath -Append
}
```

### 3.2 日志查看

**日志位置**

```
stock_agent_team/data/logs/
├── app.log           # 应用日志
├── error.log         # 错误日志
├── launchd.log       # macOS launchd 日志
└── scheduler.log     # 定时任务日志
```

**查看日志命令**

| 系统 | 命令 |
|------|------|
| macOS | `tail -f data/logs/app.log` |
| Windows | `Get-Content data/logs/app.log -Wait -Tail 50` |

**日志配置修改**

编辑 `stock_agent_team/utils/logger.py` 或在 `config.py` 中添加：

```python
# config.py
LOG_CONFIG = {
    'level': 'INFO',           # DEBUG, INFO, WARNING, ERROR
    'max_bytes': 10485760,     # 单个日志文件最大 10MB
    'backup_count': 5,         # 保留备份数量
}
```

### 3.3 数据备份

**备份脚本**

```bash
#!/bin/bash
# backup.sh - macOS/Linux 备份脚本

PROJECT_DIR="/Users/用户名/Projects/stock_agent_team"
BACKUP_DIR="/Users/用户名/Backups/stock_agent"
DATE=$(date +%Y%m%d_%H%M%S)

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 备份数据库
cp "$PROJECT_DIR/data/database.db" "$BACKUP_DIR/database_$DATE.db"

# 备份配置
cp "$PROJECT_DIR/config.py" "$BACKUP_DIR/config_$DATE.py"

# 压缩备份
cd "$BACKUP_DIR"
tar -czf "backup_$DATE.tar.gz" "database_$DATE.db" "config_$DATE.py"

# 删除原始文件（保留压缩包）
rm "database_$DATE.db" "config_$DATE.py"

# 删除 7 天前的备份
find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +7 -delete

echo "备份完成: backup_$DATE.tar.gz"
```

**Windows 备份脚本** (`backup.ps1`)

```powershell
# D:\Projects\stock_agent_team\backup.ps1

$projectDir = "D:\Projects\stock_agent_team"
$backupDir = "D:\Backups\stock_agent"
$date = Get-Date -Format "yyyyMMdd_HHmmss"

# 创建备份目录
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir
}

# 备份数据库
Copy-Item "$projectDir\data\database.db" "$backupDir\database_$date.db"

# 压缩
$zipFile = "$backupDir\backup_$date.zip"
Compress-Archive -Path "$backupDir\database_$date.db" -DestinationPath $zipFile -Force

# 删除临时文件
Remove-Item "$backupDir\database_$date.db"

# 删除 7 天前的备份
Get-ChildItem $backupDir -Filter "backup_*.zip" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } | Remove-Item

Write-Host "备份完成: $zipFile"
```

**定时备份（macOS crontab）**

```bash
# 每天凌晨 2 点备份
0 2 * * * /Users/用户名/Projects/stock_agent_team/backup.sh
```

**定时备份（Windows 任务计划程序）**

创建每日 2:00 的计划任务，运行 `powershell -File D:\Projects\stock_agent_team\backup.ps1`

---

## 第四部分：网络问题排查

### 4.1 akshare/efinance 连接问题

#### 问题诊断

```python
# 测试网络连接
import requests

# 测试东方财富
try:
    r = requests.get("https://push2.eastmoney.com/api/qt/stock/get", timeout=10)
    print(f"东方财富: {r.status_code}")
except Exception as e:
    print(f"东方财富连接失败: {e}")

# 测试 akshare
import akshare as ak
try:
    df = ak.stock_zh_a_spot_em()
    print(f"akshare: 连接成功，获取 {len(df)} 条数据")
except Exception as e:
    print(f"akshare 连接失败: {e}")
```

#### 常见错误

| 错误信息 | 可能原因 | 解决方案 |
|----------|----------|----------|
| `ConnectionError` | 网络不通 | 检查网络/代理设置 |
| `ReadTimeout` | 请求超时 | 增加 timeout 参数 |
| `HTTP 403` | 被拒绝访问 | 检查 User-Agent |
| `JSONDecodeError` | 返回格式异常 | 可能是数据源更新 |

### 4.2 代理设置

#### 系统代理

**macOS**

```bash
# 查看代理设置
 networksetup -getwebproxy "Wi-Fi"

# 设置代理（临时）
export http_proxy="http://127.0.0.1:7890"
export https_proxy="http://127.0.0.1:7890"

# 永久设置
echo 'export http_proxy="http://127.0.0.1:7890"' >> ~/.zshrc
echo 'export https_proxy="http://127.0.0.1:7890"' >> ~/.zshrc
source ~/.zshrc
```

**Windows**

```powershell
# PowerShell 临时设置
$env:http_proxy = "http://127.0.0.1:7890"
$env:https_proxy = "http://127.0.0.1:7890"

# 永久设置
[System.Environment]::SetEnvironmentVariable("http_proxy", "http://127.0.0.1:7890", "User")
[System.Environment]::SetEnvironmentVariable("https_proxy", "http://127.0.0.1:7890", "User")
```

#### Python 代码内设置

```python
import os
import requests

# 设置代理
os.environ['http_proxy'] = 'http://127.0.0.1:7890'
os.environ['https_proxy'] = 'http://127.0.0.1:7890'

# 自定义 session
session = requests.Session()
session.proxies = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7890'
}
```

### 4.3 防火墙配置

#### macOS 防火墙

```bash
# 查看防火墙状态
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate

# 允许 Python 通过防火墙
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --addapp="/Users/用户名/miniconda3/envs/stock_agent/bin/python"

# 或使用命令行添加
sudo launchctl unload /System/Library/LaunchDaemons/com.apple.alf.useragent.plist
sudo launchctl load /System/Library/LaunchDaemons/com.apple.alf.useragent.plist
```

#### Windows 防火墙

```powershell
# 允许 Python 通过防火墙（管理员）
New-NetFirewallRule -DisplayName "Python Stock Agent" -Direction Inbound -Protocol TCP -LocalPort Any -Action Allow -Program "C:\Users\用户名\miniconda3\envs\stock_agent\python.exe"

# 或使用高级防火墙设置
netsh advfirewall firewall add rule name="Python Stock Agent" dir=in action=allow program="C:\Users\用户名\miniconda3\envs\stock_agent\python.exe" enable=yes
```

### 4.4 DNS 污染问题

```bash
# macOS - 使用 Google DNS
networksetup -setdnsservers "Wi-Fi" 8.8.8.8 8.8.4.4

# Windows - 使用 Google DNS
# 控制面板 -> 网络和共享中心 -> 适配器设置 -> IPv4
# DNS 服务器: 8.8.8.8, 8.8.4.4
```

### 4.5 证书问题

```bash
# macOS - 更新证书
/Applications/Python\ 3.10/Install\ Certificates.command

# 或使用 certifi
pip install --upgrade certifi
python -c "import ssl; print(ssl.get_default_verify_paths())"
```

---

## 附录

### A. 快速部署清单

#### macOS

- [ ] 安装 Xcode Command Line Tools
- [ ] 安装 Homebrew
- [ ] 安装 pyenv 和 Python 3.10+
- [ ] 创建虚拟环境
- [ ] 安装依赖 `pip install -r requirements.txt`
- [ ] 运行测试 `python main.py`
- [ ] 配置定时任务（可选）

#### Windows 11

- [ ] 安装 Miniconda
- [ ] 创建虚拟环境 `conda create -n stock_agent python=3.10`
- [ ] 激活环境 `conda activate stock_agent`
- [ ] 安装依赖 `pip install -r requirements.txt`
- [ ] 运行测试 `python main.py`
- [ ] 配置定时任务（可选）

### B. 常用命令速查

| 操作 | macOS | Windows |
|------|-------|---------|
| 进入目录 | `cd ~/Projects/stock_agent_team` | `cd /d D:\Projects\stock_agent_team` |
| 激活环境 | `pyenv activate stock_agent-env` | `conda activate stock_agent` |
| 运行程序 | `python main.py` | `python main.py` |
| 查看日志 | `tail -f data/logs/app.log` | `Get-Content data/logs/app.log -Wait` |
| 备份数据 | `./backup.sh` | `.\backup.ps1` |

### C. 联系方式与支持

如遇到问题，请检查：

1. 是否严格按本文档步骤操作
2. 错误信息是否已在网上搜索
3. 项目的 GitHub Issues 是否有类似问题

---

**文档版本**: 1.0  
**最后更新**: 2024年  
**适用版本**: stock_agent_team (latest)
