"""
讨论引擎使用示例

展示如何初始化 Agent 并运行多轮讨论。

注意：本目录示例若使用 `from stock_agent_team.conversation import ...`，
需与已安装的包名一致；在本文仓根目录开发时可改为
`from conversation import ...`。
生产环境 LLM 请通过 `llm/llm_factory.py` 与 `agents/llm/` 接入，勿仅依赖下方模拟输出。
"""

from stock_agent_team.conversation import (
    DiscussionManager,
    SimpleLLMAgent,
    AgentRole,
)


def create_stock_analysis_team():
    """创建股票分析团队"""
    
    # Leader
    leader = SimpleLLMAgent(
        name="讨论主持",
        role=AgentRole.LEADER,
        role_description="股票分析团队主持人"
    )
    
    # 各专业 Agent
    agents = [
        SimpleLLMAgent(
            name="技术分析员",
            role=AgentRole.TECHNICAL,
            role_description="技术分析专家，擅长K线、均线、MACD等技术指标"
        ),
        SimpleLLMAgent(
            name="情报员",
            role=AgentRole.INTELLIGENCE,
            role_description="市场情报分析师，关注资金流向、市场情绪"
        ),
        SimpleLLMAgent(
            name="风控官",
            role=AgentRole.RISK,
            role_description="风险控制专家，关注下行风险和波动率"
        ),
        SimpleLLMAgent(
            name="基本面分析员",
            role=AgentRole.FUNDAMENTAL,
            role_description="基本面分析师，关注财务数据和估值"
        ),
    ]
    
    return leader, agents


def run_discussion_example():
    """运行讨论示例"""
    
    leader, agents = create_stock_analysis_team()
    
    # 创建讨论管理器
    manager = DiscussionManager(leader, agents)
    
    # 准备数据
    data = {
        "current_price": "158.50",
        "market_context": "牛市氛围，北向资金持续流入",
        "technical": {
            "MACD": "日线金叉，形成多头排列",
            "KDJ": "J值超买，短期有回调压力",
            "MA5": "上穿MA10，形成支撑",
            "VOLUME": "量能温和放大，较昨日+15%",
        },
        "intelligence": {
            "north_flow": "近5日净流入12亿",
            "news": "公司发布业绩预增公告，同比增长30%",
            "sentiment": "分析师评级调高，目标价180元",
        },
        "risk": {
            "volatility": "历史波动率中等偏高",
            "position_analysis": "机构持仓分散，无明显集中风险",
            "external": "关注美联储加息预期影响",
        },
        "fundamental": {
            "PE": "28倍，同行业平均32倍",
            "ROE": "15%，盈利能力良好",
            "growth": "营收同比增长25%，超预期",
            "debt_ratio": "45%，负债率合理",
        }
    }
    
    # 启动讨论（同步版本）
    result = manager.start_discussion_sync(
        stock_code="600519",
        stock_name="贵州茅台",
        data=data
    )
    
    # 输出结果
    print("=" * 60)
    print("讨论结果")
    print("=" * 60)
    print(f"股票: {result.stock_name}({result.stock_code})")
    print(f"综合评分: {result.overall_score:.1f}/10")
    print(f"置信度: {result.confidence:.0%}")
    print(f"建议操作: {result.recommendation}")
    print()
    
    print("各 Agent 最终报告:")
    print("-" * 40)
    for report in result.final_reports:
        print(f"\n{report.agent_name}（{report.agent_role.value}）:")
        print(f"  评分: {report.score}/10")
        print(f"  置信度: {report.confidence:.0%}")
        print(f"  分析: {report.analysis[:80]}...")
    
    print()
    print("最终决策:")
    print("-" * 40)
    print(result.final_summary)
    
    # 讨论历史
    print()
    print("讨论历史:")
    print("-" * 40)
    history = result.discussion_history
    for round_obj in history.rounds:
        print(f"\n【第{round_obj.round_number}轮】{round_obj.round_type}")
        print(f"  消息数: {len(round_obj.messages)}")
        print(f"  总结: {round_obj.summary}")
    
    return result


async def run_discussion_async():
    """异步版本示例"""
    leader, agents = create_stock_analysis_team()
    manager = DiscussionManager(leader, agents)
    
    data = {
        "current_price": "50.00",
        "market_context": "震荡市",
        "technical": {"MACD": "零轴附近徘徊"},
        "intelligence": {"volume": "近期缩量"},
        "risk": {"dividend": "高股息率5%"},
        "fundamental": {"PE": "12倍", "PB": "1.2倍"},
    }
    
    result = await manager.start_discussion(
        stock_code="601318",
        stock_name="中国平安",
        data=data
    )
    
    return result


# ==================== 自定义 Agent 示例 ====================

class CustomStockAgent(BaseLLMAgent):
    """
    自定义 Agent 示例
    
    用户可以实现自己的 Agent 类来接入真实的 LLM
    """
    
    def __init__(self, name: str, role: AgentRole, role_description: str):
        super().__init__(name, role, role_description)
        # 可以在此初始化 LLM client
        # self.llm_client = SomeLLMClient()
    
    async def analyze(self, prompt: str) -> str:
        """
        实现 LLM 调用逻辑
        
        Args:
            prompt: 提示词
            
        Returns:
            LLM 响应文本
        """
        # 真实 LLM 请用 llm/llm_factory 创建 provider 并在此调用；此处为可读性的模拟结果。
        return f"[{self.name}] 模拟分析（未接 LLM，仅示例用）"


class TradingSignalAgent(CustomStockAgent):
    """交易信号 Agent - 专门生成交易信号"""
    
    async def analyze(self, prompt: str) -> str:
        """生成交易信号"""
        # 实现交易信号生成逻辑
        response = await super().analyze(prompt)
        return response


if __name__ == "__main__":
    # 运行示例
    result = run_discussion_example()
