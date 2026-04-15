"""
测试 LLM Agent Team 完整流程
"""
import os
import sys

# 设置环境变量
os.environ["OPENAI_API_KEY"] = "sk-mgzorsYLeEFnIJHrK2B1LQurNOn5VCj3nrSAtXymUGToTzcb"
os.environ["OPENAI_BASE_URL"] = "https://www.dmxapi.cn/v1"

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("🤖 LLM Agent Team 完整测试")
print("=" * 70)

# 1. 测试数据获取
print("\n【步骤1】获取股票数据...")
try:
    from utils.data_fetcher import DataFetcher
    fetcher = DataFetcher()
    
    stock_code = "300750"  # 宁德时代
    print(f"  获取 {stock_code} 数据...")
    
    data = {
        "technical": fetcher.get_technical_indicators(stock_code),
        "quote": fetcher.get_realtime_quote(stock_code),
    }
    
    if data["technical"]:
        print(f"  ✅ 技术指标: 当前价 ¥{data['technical'].get('current_price', 'N/A')}")
        print(f"     MA5: {data['technical'].get('ma5', 'N/A')}")
        print(f"     周期趋势: {data['technical'].get('weekly_trend', 'N/A')}")
    else:
        print("  ⚠️ 技术指标获取失败，使用模拟数据")
        
except Exception as e:
    print(f"  ❌ 数据获取失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 2. 测试 LLM Provider
print("\n【步骤2】测试 LLM Provider...")
try:
    from llm import get_provider
    
    provider = get_provider(
        "openai_compatible",
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ["OPENAI_BASE_URL"],
        model="deepseek-v3.1-thinking"
    )
    
    print("  发送测试消息...")
    response = provider.chat("请用一句话介绍股票投资的风险")
    print(f"  ✅ LLM 响应: {response.content[:100]}...")
    
except Exception as e:
    print(f"  ❌ LLM Provider 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. 测试单个 Agent
print("\n【步骤3】测试单个 LLM Agent...")
try:
    from agents.llm import create_llm_agent
    from agents.llm.models import StockAnalysisContext
    
    # 创建技术分析 Agent
    tech_agent = create_llm_agent(
        role="technical",
        provider="openai_compatible",
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ["OPENAI_BASE_URL"],
        model="deepseek-v3.1-thinking"
    )
    
    # 创建分析上下文
    context = StockAnalysisContext(
        stock_code=stock_code,
        stock_name="宁德时代",
        task_id="test_001",
        user_request="综合技术分析",
        market_data=data
    )
    
    print("  技术 Agent 分析中...")
    tech_report = tech_agent.analyze(context)
    
    print(f"  ✅ 技术分析完成:")
    print(f"     评分: {tech_report.score}/10")
    print(f"     置信度: {tech_report.confidence:.0%}")
    print(f"     总结: {tech_report.summary[:80]}...")
    
except Exception as e:
    print(f"  ❌ Agent 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. 测试完整 Agent Team 讨论
print("\n【步骤4】测试完整 Agent Team 讨论...")
print("  ⏳ 这可能需要 1-2 分钟，请耐心等待...")
try:
    from agents.llm import create_team
    from conversation import DiscussionManager
    
    # 创建 Agent 团队
    team = create_team(
        provider="openai_compatible",
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ["OPENAI_BASE_URL"],
        model="deepseek-v3.1-thinking"
    )
    
    leader = team["leader"]
    agents = [team["technical"], team["intelligence"], team["risk"], team["fundamental"]]
    
    print(f"  创建了 {len(agents)} 个 Agent")
    
    # 创建讨论管理器
    manager = DiscussionManager(
        leader=leader,
        agents=agents,
        max_rounds=2  # 限制2轮讨论，节省时间
    )
    
    # 开始讨论
    print("\n  开始多轮讨论...")
    result = manager.start_discussion_sync(
        stock_code=stock_code,
        stock_name="宁德时代",
        data=data
    )
    
    print("\n" + "=" * 70)
    print("📊 分析结果")
    print("=" * 70)
    print(f"\n  股票: {result.stock_name} ({result.stock_code})")
    print(f"  建议: {result.recommendation}")
    print(f"  综合评分: {result.overall_score}/10")
    print(f"  置信度: {result.confidence:.0%}")
    print(f"\n  决策理由:")
    print(f"  {result.reasoning}")
    
    if result.risks:
        print(f"\n  ⚠️ 风险提示:")
        for risk in result.risks[:3]:
            print(f"    - {risk}")
    
    print("\n" + "=" * 70)
    print("✅ 测试完成！")
    print("=" * 70)
    
except Exception as e:
    print(f"  ❌ Agent Team 测试失败: {e}")
    import traceback
    traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("⚠️ 部分测试未完成，请检查错误信息")
    print("=" * 70)
