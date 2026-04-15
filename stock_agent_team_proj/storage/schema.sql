-- ============================================================
-- 中短线波段 Agent Team 数据库表结构
-- 数据库: SQLite
-- 版本: 1.0
-- ============================================================

-- ============================================================
-- 1. 交易记录表
-- ============================================================
CREATE TABLE IF NOT EXISTS trades (
    trade_id TEXT PRIMARY KEY,              -- 交易ID (格式: T_YYYYMMDD_HHMMSS_股票代码)
    stock_code TEXT NOT NULL,                -- 股票代码
    stock_name TEXT NOT NULL,                -- 股票名称
    market TEXT,                             -- 市场 (SZ/SH/BJ)
    
    -- 买入信息
    buy_date DATE NOT NULL,                  -- 买入日期
    buy_time TIME,                           -- 买入时间
    buy_price REAL NOT NULL,                 -- 买入价格
    buy_position REAL NOT NULL,              -- 买入仓位比例
    buy_amount REAL,                         -- 买入金额
    buy_reason TEXT,                         -- 买入理由
    
    -- 卖出信息
    sell_date DATE,                          -- 卖出日期
    sell_time TIME,                          -- 卖出时间
    sell_price REAL,                         -- 卖出价格
    sell_reason TEXT,                        -- 卖出原因 (止盈/止损/逻辑证伪/手动卖出)
    sell_amount REAL,                        -- 卖出金额
    
    -- 结果
    holding_days INTEGER,                    -- 持股天数
    return_rate REAL,                        -- 收益率
    profit_amount REAL,                      -- 盈亏金额
    max_profit REAL,                         -- 最大浮盈
    max_loss REAL,                           -- 最大浮亏
    
    -- 评分
    buy_score REAL,                          -- 买入时综合评分
    sell_score REAL,                         -- 卖出时综合评分
    
    -- 状态
    status TEXT NOT NULL DEFAULT 'holding',  -- 状态 (holding/closed/cancelled)
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trades_stock ON trades(stock_code);
CREATE INDEX idx_trades_buy_date ON trades(buy_date);
CREATE INDEX idx_trades_status ON trades(status);

-- ============================================================
-- 2. 各角色评分记录表
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_scores (
    score_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT NOT NULL,                  -- 关联交易ID
    
    -- 技术分析员评分
    technical_score REAL,                    -- 技术面评分
    technical_weight REAL,                   -- 技术面权重
    technical_accuracy TEXT,                 -- 技术面准确性 (accurate/partial/inaccurate)
    technical_comment TEXT,                  -- 技术面评价
    
    -- 情报员评分
    intelligence_score REAL,                 -- 情报面评分
    intelligence_weight REAL,                -- 情报面权重
    intelligence_accuracy TEXT,              -- 情报面准确性
    intelligence_comment TEXT,               -- 情报面评价
    
    -- 风控官评分
    risk_score REAL,                         -- 风控面评分
    risk_weight REAL,                        -- 风控面权重
    risk_accuracy TEXT,                      -- 风控面准确性
    risk_comment TEXT,                       -- 风控面评价
    
    -- 基本面分析师评分
    fundamental_score REAL,                  -- 基本面评分
    fundamental_weight REAL,                 -- 基本面权重
    fundamental_accuracy TEXT,               -- 基本面准确性
    fundamental_comment TEXT,                -- 基本面评价
    
    -- 综合
    composite_score REAL,                    -- 综合评分
    overall_accuracy TEXT,                   -- 整体准确性
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
);

CREATE INDEX idx_agent_scores_trade ON agent_scores(trade_id);

-- ============================================================
-- 3. Agent权重配置表
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_weights (
    weight_id INTEGER PRIMARY KEY AUTOINCREMENT,
    effective_date DATE NOT NULL,            -- 生效日期
    
    technical_weight REAL NOT NULL DEFAULT 0.35,
    intelligence_weight REAL NOT NULL DEFAULT 0.30,
    risk_weight REAL NOT NULL DEFAULT 0.20,
    fundamental_weight REAL NOT NULL DEFAULT 0.15,
    
    reason TEXT,                             -- 调整原因
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 插入默认权重
INSERT INTO agent_weights (effective_date, technical_weight, intelligence_weight, risk_weight, fundamental_weight, reason)
VALUES ('2026-01-01', 0.35, 0.30, 0.20, 0.15, '初始默认权重');

-- ============================================================
-- 4. 角色准确率统计表
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_accuracy_stats (
    stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_type TEXT NOT NULL,               -- 统计周期类型 (daily/weekly/monthly)
    period_start DATE NOT NULL,              -- 周期开始日期
    period_end DATE NOT NULL,                -- 周期结束日期
    
    -- 技术分析员统计
    technical_total INTEGER DEFAULT 0,       -- 总交易数
    technical_accurate INTEGER DEFAULT 0,    -- 准确数
    technical_partial INTEGER DEFAULT 0,     -- 部分准确数
    technical_inaccurate INTEGER DEFAULT 0,  -- 不准确数
    technical_accuracy_rate REAL,            -- 准确率
    
    -- 情报员统计
    intelligence_total INTEGER DEFAULT 0,
    intelligence_accurate INTEGER DEFAULT 0,
    intelligence_partial INTEGER DEFAULT 0,
    intelligence_inaccurate INTEGER DEFAULT 0,
    intelligence_accuracy_rate REAL,
    
    -- 风控官统计
    risk_total INTEGER DEFAULT 0,
    risk_accurate INTEGER DEFAULT 0,
    risk_partial INTEGER DEFAULT 0,
    risk_inaccurate INTEGER DEFAULT 0,
    risk_accuracy_rate REAL,
    
    -- 基本面分析师统计
    fundamental_total INTEGER DEFAULT 0,
    fundamental_accurate INTEGER DEFAULT 0,
    fundamental_partial INTEGER DEFAULT 0,
    fundamental_inaccurate INTEGER DEFAULT 0,
    fundamental_accuracy_rate REAL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_accuracy_stats_period ON agent_accuracy_stats(period_type, period_start);

-- ============================================================
-- 5. 分析报告存储表
-- ============================================================
CREATE TABLE IF NOT EXISTS analysis_reports (
    report_id TEXT PRIMARY KEY,              -- 报告ID
    trade_id TEXT,                           -- 关联交易ID
    stock_code TEXT NOT NULL,                -- 股票代码
    stock_name TEXT,                         -- 股票名称
    agent_type TEXT NOT NULL,                -- Agent类型 (technical/intelligence/risk/fundamental/leader/review)
    report_type TEXT NOT NULL,               -- 报告类型 (analysis/decision/review)
    report_date DATE NOT NULL,               -- 报告日期
    
    content TEXT,                            -- 报告内容 (JSON格式)
    file_path TEXT,                          -- 报告文件路径
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_reports_stock ON analysis_reports(stock_code);
CREATE INDEX idx_reports_agent ON analysis_reports(agent_type);
CREATE INDEX idx_reports_date ON analysis_reports(report_date);

-- ============================================================
-- 6. 复盘报告表
-- ============================================================
CREATE TABLE IF NOT EXISTS review_reports (
    review_id TEXT PRIMARY KEY,              -- 复盘ID
    review_type TEXT NOT NULL,               -- 复盘类型 (single/weekly/monthly/emergency)
    
    -- 关联交易
    trade_id TEXT,                           -- 单笔复盘关联交易ID
    period_start DATE,                       -- 周期开始 (周/月复盘)
    period_end DATE,                         -- 周期结束 (周/月复盘)
    
    -- 复盘数据
    total_trades INTEGER,                    -- 总交易数
    win_trades INTEGER,                      -- 盈利交易数
    loss_trades INTEGER,                     -- 亏损交易数
    win_rate REAL,                           -- 胜率
    total_return REAL,                       -- 总收益率
    max_drawdown REAL,                       -- 最大回撤
    
    -- 各角色准确率
    technical_accuracy_rate REAL,
    intelligence_accuracy_rate REAL,
    risk_accuracy_rate REAL,
    fundamental_accuracy_rate REAL,
    
    -- 权重调整建议
    weight_adjustment TEXT,                  -- 权重调整建议 (JSON)
    
    -- 报告内容
    content TEXT,                            -- 复盘报告内容
    file_path TEXT,                          -- 报告文件路径
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 7. 系统配置表
-- ============================================================
CREATE TABLE IF NOT EXISTS system_config (
    config_key TEXT PRIMARY KEY,
    config_value TEXT,
    config_type TEXT,                        -- 配置类型 (int/float/string/json)
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 插入默认配置
INSERT INTO system_config (config_key, config_value, config_type, description) VALUES
('score_threshold_strong_buy', '8.0', 'float', '强烈买入评分阈值'),
('score_threshold_buy', '7.0', 'float', '建议买入评分阈值'),
('score_threshold_watch', '5.0', 'float', '观望评分阈值'),
('max_single_position', '0.20', 'float', '单只股票最大仓位'),
('max_sector_position', '0.40', 'float', '单板块最大仓位'),
('max_total_position', '0.80', 'float', '总仓位上限'),
('default_stop_loss_rate', '0.06', 'float', '默认止损比例'),
('min_profit_loss_ratio', '1.5', 'float', '最小盈亏比'),
('max_holding_days', '10', 'int', '最大持股天数');

-- ============================================================
-- 8. 任务消息队列表
-- ============================================================
CREATE TABLE IF NOT EXISTS task_queue (
    task_id TEXT PRIMARY KEY,                -- 任务ID
    message_type TEXT NOT NULL,              -- 消息类型
    sender TEXT NOT NULL,                    -- 发送者
    receivers TEXT,                          -- 接收者列表 (JSON)
    task_data TEXT,                          -- 任务数据 (JSON)
    status TEXT DEFAULT 'pending',           -- 状态 (pending/processing/completed/failed)
    priority INTEGER DEFAULT 0,              -- 优先级
    retry_count INTEGER DEFAULT 0,           -- 重试次数
    error_message TEXT,                      -- 错误信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_task_queue_status ON task_queue(status);
CREATE INDEX idx_task_queue_created ON task_queue(created_at);

-- ============================================================
-- 9. 持仓跟踪表
-- ============================================================
CREATE TABLE IF NOT EXISTS holdings (
    holding_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT NOT NULL,                  -- 关联交易ID
    stock_code TEXT NOT NULL,                -- 股票代码
    stock_name TEXT,                         -- 股票名称
    
    current_price REAL,                      -- 当前价格
    cost_price REAL NOT NULL,                -- 成本价
    position REAL NOT NULL,                  -- 仓位
    shares REAL,                             -- 股数
    
    stop_loss_price REAL,                    -- 止损价
    take_profit_1 REAL,                      -- 止盈价1
    take_profit_2 REAL,                      -- 止盈价2
    take_profit_3 REAL,                      -- 止盈价3
    
    current_profit REAL,                     -- 当前浮盈
    current_profit_rate REAL,                -- 当前收益率
    days_held INTEGER DEFAULT 0,             -- 持有天数
    
    status TEXT DEFAULT 'holding',           -- 状态
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
);

CREATE INDEX idx_holdings_stock ON holdings(stock_code);
CREATE INDEX idx_holdings_status ON holdings(status);

-- ============================================================
-- 10. 风控预警表
-- ============================================================
CREATE TABLE IF NOT EXISTS risk_alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT,                           -- 关联交易ID
    stock_code TEXT,                         -- 股票代码
    
    alert_type TEXT NOT NULL,                -- 预警类型 (stop_loss/take_profit/position_limit/market_risk)
    alert_level TEXT NOT NULL,               -- 预警级别 (info/warning/critical)
    alert_message TEXT,                      -- 预警信息
    
    is_triggered BOOLEAN DEFAULT FALSE,      -- 是否已触发
    is_handled BOOLEAN DEFAULT FALSE,        -- 是否已处理
    handled_at TIMESTAMP,                    -- 处理时间
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_risk_alerts_stock ON risk_alerts(stock_code);
CREATE INDEX idx_risk_alerts_triggered ON risk_alerts(is_triggered, is_handled);

-- ============================================================
-- 视图: 活跃持仓视图
-- ============================================================
CREATE VIEW IF NOT EXISTS v_active_holdings AS
SELECT 
    h.holding_id,
    h.trade_id,
    h.stock_code,
    h.stock_name,
    h.current_price,
    h.cost_price,
    h.position,
    h.stop_loss_price,
    h.take_profit_1,
    h.take_profit_2,
    h.take_profit_3,
    h.current_profit_rate,
    h.days_held,
    t.buy_date
FROM holdings h
LEFT JOIN trades t ON h.trade_id = t.trade_id
WHERE h.status = 'holding';

-- ============================================================
-- 视图: 月度交易统计视图
-- ============================================================
CREATE VIEW IF NOT EXISTS v_monthly_stats AS
SELECT 
    strftime('%Y-%m', buy_date) as month,
    COUNT(*) as total_trades,
    SUM(CASE WHEN return_rate > 0 THEN 1 ELSE 0 END) as win_trades,
    SUM(CASE WHEN return_rate <= 0 THEN 1 ELSE 0 END) as loss_trades,
    ROUND(AVG(CASE WHEN return_rate > 0 THEN 1 ELSE 0 END) * 100, 2) as win_rate,
    ROUND(SUM(return_rate), 4) as total_return,
    ROUND(AVG(return_rate), 4) as avg_return,
    MIN(return_rate) as max_loss,
    MAX(return_rate) as max_profit
FROM trades
WHERE status = 'closed'
GROUP BY strftime('%Y-%m', buy_date)
ORDER BY month DESC;
