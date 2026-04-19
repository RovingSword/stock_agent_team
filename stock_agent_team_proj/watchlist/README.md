# 股票观察池系统

自动化的股票观察池管理系统，支持从龙虎榜、热门板块、机构调研等数据源自动采集、筛选候选股票，并定时执行分析。

## 系统架构

```
stock_agent_team/
├── watchlist/                    # 观察池模块
│   ├── __init__.py              # 模块导出
│   ├── config.py                 # 配置文件
│   ├── models.py                 # 数据模型
│   ├── data_collector.py         # 数据采集器
│   ├── stock_screener.py         # 股票筛选器
│   ├── watchlist_manager.py      # 观察池管理器
│   ├── performance_tracker.py    # 表现跟踪器
│   ├── performance_reporter.py   # 表现报告生成器
│   ├── auto_scheduler.py         # 自动调度器
│   ├── task_config.py            # 任务配置
│   └── test_watchlist.py        # 测试脚本
├── data/                         # 数据存储目录
│   ├── watchlist.json           # 观察池数据
│   ├── dragon_tiger.json        # 龙虎榜缓存
│   ├── sector.json              # 板块缓存
│   ├── research.json            # 调研缓存
│   ├── price_history.json       # 价格历史
│   ├── signal_history.json       # 信号历史
│   ├── performance_stats.json    # 统计数据
│   └── scheduled_tasks.json      # 定时任务配置
└── main.py                       # 主程序
```

## 核心功能

### 1. 数据采集 (DataCollector)
从多个数据源自动采集数据：
- **龙虎榜**：机构净买入、涨停板、异常波动等
- **热门板块**：涨幅居前板块、龙头股票
- **机构调研**：机构关注度高、调研密集的股票

### 2. 股票筛选 (StockScreener)
多维度评分筛选：
- 评分权重：龙虎榜(40%) + 板块热度(30%) + 机构调研(30%)
- 过滤条件：非ST股、流通市值>20亿、近5日涨幅<30%
- 自动排除已在观察池中的股票

### 3. 观察池管理 (WatchlistManager)
完整的CRUD操作：
- 添加/移除候选股票
- 状态管理：pending → analyzing → watching → archived
- 分析结果记录
- 报告导出

### 4. 表现跟踪 (PerformanceTracker)
跟踪观察池股票的表现：
- **信号记录**：记录买入/观察/回避信号
- **价格更新**：每日收盘后更新价格快照
- **止损止盈**：自动检查并触发止损/止盈
- **收益率计算**：计算实际收益率、最大收益、最大回撤

### 5. 表现报告 (PerformanceReporter)
生成各类报告：
- **周报**：本周新增信号、平仓记录、持仓表现、胜率统计
- **月报**：月度汇总、平仓统计、胜率分析
- **信号报告**：单个或全部股票信号详情

### 6. 自动调度 (AutoScheduler)
定时任务执行：
- 每日16:30：数据采集
- 每日17:00：价格更新与止损止盈检查
- 每周六10:00：完整流程（采集+筛选+分析+推送）

## 命令行使用

### 股票分析（原功能）
```bash
python main.py --code 300750 --name 宁德时代
```

### 观察池管理
```bash
# 查看状态
python main.py watchlist status

# 列出所有股票
python main.py watchlist list

# 添加股票
python main.py watchlist add --code 300750 --name 宁德时代 --reason 看好新能源

# 移除股票
python main.py watchlist remove --code 300750 --reason 止盈

# 分析股票
python main.py watchlist analyze --code 300750

# 导出报告
python main.py watchlist export
```

### 数据采集
```bash
# 采集数据
python main.py collect

# 采集并添加到观察池
python main.py collect --add-to-watchlist
```

### 股票筛选
```bash
# 筛选股票（使用缓存数据）
python main.py screen

# 筛选并排除指定股票
python main.py screen --exclude 300750,600519
```

### 自动化执行
```bash
# 执行完整流程
python main.py auto

# 强制分析所有股票
python main.py auto --force

# 执行指定任务
python main.py auto --task daily_collect
```

### 调度器管理
```bash
# 列出所有任务
python main.py schedule list

# 启动调度器
python main.py schedule start

# 停止调度器
python main.py schedule stop

# 立即执行任务
python main.py schedule run --task-id daily_collect

# 启用/禁用任务
python main.py schedule enable --task-id daily_collect
python main.py schedule disable --task-id daily_collect
```

### 表现跟踪与报告
```bash
# 查看表现统计摘要
python run_watchlist.py performance --type summary

# 查看周报
python run_watchlist.py performance --type weekly

# 查看月报
python run_watchlist.py performance --type monthly

# 查看信号详情
python run_watchlist.py performance --type signal

# 查看当前持仓
python run_watchlist.py performance --type positions

# 查看已平仓记录
python run_watchlist.py performance --type closed --limit 20

# 更新价格
python run_watchlist.py price

# 平仓指定股票
python run_watchlist.py close 000001 --reason 手动平仓

# 导出报告
python run_watchlist.py export-report --type weekly
python run_watchlist.py export-report --type monthly --file ./reports/my_report.md
```

## 定时任务配置

编辑 `watchlist/task_config.py` 修改任务配置：

```python
DEFAULT_TASKS = [
    {
        "task_id": "daily_collect",
        "task_name": "每日数据采集",
        "schedule_time": "16:30",  # 修改执行时间
    },
    {
        "task_id": "weekly_update",
        "task_name": "每周观察池更新",
        "schedule_time": "10:00",
        "weekday": 6,  # 周六
    },
]
```

## 数据筛选标准

| 标准 | 默认值 | 说明 |
|------|--------|------|
| 最小流通市值 | 20亿 | 过滤小市值股票 |
| 最大5日涨幅 | 30% | 过滤短期涨幅过大股票 |
| 排除ST股 | 是 | 过滤风险股票 |
| 评分权重-龙虎榜 | 40% | 机构信号权重 |
| 评分权重-板块 | 30% | 板块热度权重 |
| 评分权重-调研 | 30% | 机构关注权重 |

## 测试

```bash
cd stock_agent_team
python watchlist/test_watchlist.py
```

## 注意事项

1. **首次使用**：建议先运行 `python watchlist/test_watchlist.py` 验证各模块功能
2. **数据缓存**：采集的数据会缓存24小时，避免重复请求
3. **分析频率**：建议每次分析不超过5只股票，避免API调用超时
4. **定时任务**：调度器需要在后台持续运行，适合部署在服务器

## 与主Agent集成

观察池系统可以与主对话Agent集成使用：

```python
# 在主Agent中调用
from stock_agent_team.watchlist import WatchlistManager, AutoScheduler

# 查看推荐买入
manager = WatchlistManager()
buy_list = manager.get_buy_recommended()

# 执行自动化流程
scheduler = AutoScheduler()
results = scheduler.run_full_pipeline()
```
