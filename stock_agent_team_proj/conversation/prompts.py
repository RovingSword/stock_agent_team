"""
讨论提示词模板 - 定义各轮讨论的提示词
"""

# ==================== Leader 提示词 ====================

LEADER_START_DISCUSSION = """## 股票分析团队讨论

各位分析师，我们需要对 **{stock_name}**（代码：{stock_code}）进行综合分析决策。

以下是各位的初步独立分析意见：

{agent_reports}

---

### 讨论议题

请各位就以下关键问题展开讨论：

1. **趋势一致性**：技术面和基本面信号是否一致？
2. **风险识别**：是否存在被忽略的风险因素？
3. **仓位建议**：当前建议的仓位是否合理？
4. **时间维度**：短期、中期、长期观点是否有分歧？

请各位逐一发表看法，可以质疑其他人的观点，也可以补充自己的分析。
"""


LEADER_SUMMARY = """## 达成共识

经过充分讨论，请各位根据交流结果调整并给出最终分析：

### 输出格式

请每位分析师提供：
1. **最终评分**（0-10分）：基于综合考量
2. **置信度**（0-1）：对自己判断的信心程度
3. **核心理由**（50字内）：最关键的判断依据
4. **风险提示**（可选）：需要特别关注的风险点

### 特别要求

- 如果你改变了之前的观点，请说明原因
- 如果你坚持原观点，请简要解释
- 风控官的意见具有一票否决权（特殊情况需特别说明）
"""


LEADER_FINAL_SUMMARY = """## 最终决策汇总

基于所有分析师的最终意见，请 Leader 综合各方观点，给出：

### 决策内容

1. **综合评分**（0-10）：
2. **建议操作**（买入/持有/卖出）：
3. **建议仓位**（0-100%）：
4. **置信度**（0-1）：
5. **主要理由**：
6. **风险提示**：
7. **时间建议**（持有周期）：

请给出明确的决策建议，格式如下：

```
【最终决策】
操作: XXX
仓位: XX%
置信度: X.X
理由: XXX
风险: XXX
周期: XXX
```
"""


# ==================== Agent 回应提示词 ====================

AGENT_RESPONSE_TEMPLATE = """你是 **{name}**（{role_description}）。

### 当前讨论背景

{discussion_context}

### 其他 Agent 的观点

{other_views}

### 你的任务

1. 仔细阅读其他 Agent 的观点
2. 评估是否认同他们的分析
3. 如果有不同意见或补充，请明确指出
4. 可以针对特定观点提问或质疑

### 输出要求

请发表你的看法，**控制在 100-200 字以内**：
- 直接回应讨论议题
- 避免重复已表达的观点
- 如需质疑，请给出理由
- 如有新的发现或数据，请分享
"""


AGENT_INITIAL_REPORT = """你是 **{name}**（{role_description}）。

### 股票信息

- **股票名称**：{stock_name}
- **股票代码**：{stock_code}
- **当前价格**：{current_price}
- **市场环境**：{market_context}

### 已有数据

```
{available_data}
```

### 你的任务

作为 {role_description}，请进行独立分析并输出报告：

### 输出格式

1. **分析摘要**（100字内）：简述你的核心发现
2. **评分**（0-10）：基于你的专业判断
3. **置信度**（0-1）：你对这个评分的信心
4. **关键因素**：
   - 利好因素：
   - 利空因素：
5. **风险提示**：需要关注的风险点
6. **建议**：简短的行动建议

请基于以上数据进行分析，保持客观独立。
"""


# ==================== 反驳/追问提示词 ====================

CHALLENGE_PROMPT = """你是 **{name}**。

### 被质疑的观点

来自 **{challenger}** 对你的观点提出质疑：

**他们的质疑**：
{challenge_content}

**你的原始观点**：
{original_view}

### 你的任务

请回应这个质疑：
1. 是否接受这个质疑？为什么？
2. 如果接受，你的观点如何调整？
3. 如果不接受，请说明理由并提供支撑

**控制在 100 字以内**。
"""


# ==================== 轮次说明提示词 ====================

ROUND_INSTRUCTIONS = {
    "round1": """
## 第一轮：独立分析

**目标**：每位分析师独立评估，不受他人影响

**规则**：
- 基于自己的专业领域进行分析
- 不与其他分析师沟通
- 给出独立的评分和理由

**参与者**：技术分析员、情报员、风控官、基本面分析员
""",
    
    "round2": """
## 第二轮：集体讨论

**目标**：通过讨论发现分歧、统一认识

**规则**：
- Leader 主持讨论，引导议题
- 各 Agent 可以质疑他人观点
- 允许修改自己的分析（需说明原因）
- 重点解决分歧点

**参与者**：全体分析师
""",
    
    "round3": """
## 第三轮：达成共识

**目标**：收敛各方意见，形成最终建议

**规则**：
- 各 Agent 给出最终评分
- 说明是否改变观点及原因
- 风控官有一票否决权（特殊情况需说明）

**参与者**：全体分析师
"""
}


# ==================== 格式辅助函数 ====================

def format_agent_reports(reports: list) -> str:
    """格式化 Agent 报告列表"""
    formatted = []
    for i, report in enumerate(reports, 1):
        formatted.append(f"""
### {i}. {report['agent_name']}（{report['agent_role']}）

**评分**：{report['score']}/10 | **置信度**：{report['confidence']:.0%}

**分析**：
{report['analysis']}
""")
    return "\n---\n".join(formatted)


def format_discussion_context(messages: list) -> str:
    """格式化讨论上下文"""
    if not messages:
        return "这是本轮讨论的开始，请发表你的初始观点。"
    
    formatted = []
    for msg in messages[-5:]:  # 只显示最近5条消息
        formatted.append(f"**{msg['agent_name']}**：{msg['content']}")
    
    return "\n\n".join(formatted)


def format_other_views(exclude_agent: str, reports: list) -> str:
    """格式化其他 Agent 的观点"""
    other_reports = [r for r in reports if r['agent_name'] != exclude_agent]
    if not other_reports:
        return "暂无其他观点"
    
    formatted = []
    for report in other_reports:
        formatted.append(f"- **{report['agent_name']}**：{report['analysis'][:50]}...（评分{report['score']}）")
    
    return "\n".join(formatted)
