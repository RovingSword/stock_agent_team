# LLM Agent 模块

基于 LLM 的智能 Agent 实现，与原有规则引擎 Agent 平行。

## 目录结构

```
agents/llm/
├── __init__.py        # 模块入口，导出所有类和工厂函数
├── models.py          # 数据模型（AgentReport, DiscussionMessage, StockAnalysisContext）
├── base_llm_agent.py  # Agent 基类（BaseLLMAgent, DiscussionAgent）
├── llm_leader.py      # LLM 决策队长
├── llm_technical.py   # LLM 技术分析员
├── llm_intelligence.py # LLM 情报员
├── llm_risk.py        # LLM 风控官
└── llm_fundamental.py # LLM 基本面分析员
```

## 快速开始

### 方式一：使用工厂函数

```python
from agents.llm import create_llm_agent, create_team

# 创建单个 Agent
agent = create_llm_agent('technical', provider='mock')

# 创建完整团队
team = create_team(provider='mock')
```

### 方式二：直接导入

```python
from agents.llm import (
    LLMLeader,
    LLMTechnical,
    LLMIntelligence,
    LLMRisk,
    LLMFundamental
)

# 直接实例化
agent = LLMTechnical(name='我的技术员', provider='mock')
```

## 数据模型

### StockAnalysisContext

股票分析上下文：

```python
from agents.llm import StockAnalysisContext

context = StockAnalysisContext(
    stock_code='000001',
    stock_name='平安银行',
    task_id='task_001',
    user_request='分析一下',
    market_data={'price': 12.5},
    fundamental_data={'pe': 8.5}
)
```

### AgentReport

Agent 分析报告：

```python
from agents.llm import AgentReport

report = AgentReport(
    agent_name='技术分析员',
    agent_role='technical',
    score=7.5,  # 0-10 评分
    confidence=0.8,  # 0-1 置信度
    summary='一句话总结',
    analysis='详细分析',
    risks=['风险点1', '风险点2'],
    opportunities=['机会点1', '机会点2']
)
```

## 使用示例

### 单 Agent 分析

```python
from agents.llm import LLMTechnical, StockAnalysisContext

# 创建 Agent
agent = LLMTechnical(provider='mock')

# 创建分析上下文
context = StockAnalysisContext(
    stock_code='600519',
    stock_name='贵州茅台',
    task_id='test_001'
)

# 执行分析
report = agent.analyze(context)
print(f"评分: {report.score}")
print(f"结论: {report.summary}")
```

### 团队协作分析

```python
from agents.llm import create_team, StockAnalysisContext

# 创建团队
team = create_team(provider='mock')

# 创建上下文
context = StockAnalysisContext(
    stock_code='000001',
    stock_name='平安银行',
    task_id='team_test'
)

# 各 Agent 独立分析
reports = {}
for role, agent in team.items():
    if role != 'leader':  # Leader 单独处理
        reports[role] = agent.analyze(context)

# Leader 综合决策
leader_report = team['leader'].analyze(context)
```

## Provider 配置

LLM Agent 支持多种 LLM Provider：

```python
# 使用 Mock（默认，用于测试）
agent = create_llm_agent('technical', provider='mock')

# 使用通义千问
agent = create_llm_agent('technical', provider='qwen')

# 使用 DeepSeek
agent = create_llm_agent('technical', provider='deepseek')

# 使用智谱AI
agent = create_llm_agent('technical', provider='zhipu')

# 使用 Moonshot
agent = create_llm_agent('technical', provider='moonshot')
```

## System Prompt 设计

每个 Agent 都有精心设计的 System Prompt：

- **LLMLeader**: 经验丰富的投资决策专家
- **LLMTechnical**: 技术分析专家，精通 MACD、KDJ、均线等
- **LLMIntelligence**: 市场情报专家，擅长资金面分析
- **LLMRisk**: 风险管理专家，保守谨慎
- **LLMFundamental**: 基本面分析专家，关注企业内在价值

## 与规则引擎 Agent 对比

| 特性 | 规则引擎 Agent | LLM Agent |
|------|---------------|-----------|
| 定位 | `agents/` 目录 | `agents/llm/` 目录 |
| 分析方式 | 基于规则的算法 | 基于 LLM 的自然语言 |
| 输出格式 | 固定格式 | 结构化 JSON |
| 灵活性 | 低 | 高 |
| 可解释性 | 明确 | 依赖模型 |
| 响应速度 | 快 | 依赖 API |

## 注意事项

1. 使用真实 Provider 时需要配置对应的 API Key
2. Mock Provider 适用于开发测试，返回模拟响应
3. 建议使用环境变量存储敏感配置
