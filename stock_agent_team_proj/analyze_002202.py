"""
002202（金风科技）股票分析脚本
使用 LLM Agent Team 进行股票分析，检测系统功能
"""
import os
import sys
import json
from datetime import datetime

# 设置环境变量
os.environ["OPENAI_API_KEY"] = "sk-mgzorsYLeEFnIJHrK2B1LQurNOn5VCj3nrSAtXymUGToTzcb"
os.environ["OPENAI_BASE_URL"] = "https://www.dmxapi.cn/v1"

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 输出日志文件
LOG_FILE = "analyze_002202.log"

def log(msg):
    """记录日志到文件和控制台"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")

def log_section(title):
    """记录分段标题"""
    sep = "=" * 70
    log(sep)
    log(f"  {title}")
    log(sep)

def main():
    """主函数"""
    log_section("LLM Agent Team 002202（金风科技）股票分析")
    
    stock_code = "002202"
    stock_name = "金风科技"
    
    # ===== 步骤1: 数据获取 =====
    log_section("步骤1: 获取股票数据")
    
    try:
        from utils.data_fetcher import DataFetcher
        fetcher = DataFetcher()
        log(f"DataFetcher 初始化成功")
        log(f"可用数据源: {fetcher.data_sources}")
        
        # 获取实时行情
        log(f"\n获取实时行情...")
        quote = fetcher.get_realtime_quote(stock_code)
        if quote:
            log(f"✅ 实时行情获取成功")
            log(f"   当前价: {quote.get('current_price', 'N/A')}")
            log(f"   涨跌额: {quote.get('change', 'N/A')}")
            log(f"   涨跌幅: {quote.get('change_pct', 'N/A')}%")
        else:
            log(f"⚠️ 实时行情获取失败")
        
        # 获取技术指标
        log(f"\n获取技术指标...")
        technical = fetcher.get_technical_indicators(stock_code)
        if technical:
            log(f"✅ 技术指标获取成功")
            for key, value in technical.items():
                if value is not None:
                    log(f"   {key}: {value}")
        else:
            log(f"⚠️ 技术指标获取失败")
        
        # 获取基本面数据
        log(f"\n获取基本面数据...")
        fundamental = fetcher.get_fundamental_data(stock_code)
        if fundamental:
            log(f"✅ 基本面数据获取成功")
            for key, value in list(fundamental.items())[:10]:
                if value is not None:
                    log(f"   {key}: {value}")
        else:
            log(f"⚠️ 基本面数据获取失败")
            
        data = {
            "quote": quote,
            "technical": technical,
            "fundamental": fundamental
        }
        data_step_success = True
        
    except ImportError as e:
        log(f"❌ 导入错误: {e}")
        data = {"technical": {}, "quote": {}, "fundamental": {}}
        data_step_success = False
    except Exception as e:
        log(f"❌ 数据获取异常: {e}")
        import traceback
        traceback.print_exc()
        data = {"technical": {}, "quote": {}, "fundamental": {}}
        data_step_success = False
    
    # ===== 步骤2: 测试 LLM Provider =====
    log_section("步骤2: 测试 LLM Provider")
    
    try:
        from llm import get_provider
        
        log(f"创建 OpenAI Compatible Provider...")
        log(f"  API Key: {os.environ['OPENAI_API_KEY'][:15]}...")
        log(f"  Base URL: {os.environ['OPENAI_BASE_URL']}")
        log(f"  Model: deepseek-v3.1-thinking")
        
        provider = get_provider(
            "openai_compatible",
            api_key=os.environ["OPENAI_API_KEY"],
            base_url=os.environ["OPENAI_BASE_URL"],
            model="deepseek-v3.1-thinking"
        )
        log(f"✅ Provider 创建成功")
        
        log(f"\n发送测试请求...")
        response = provider.chat("请用简短的一句话介绍自己")
        log(f"✅ LLM 响应成功")
        log(f"   响应长度: {len(response.content)} 字符")
        log(f"   响应内容: {response.content[:200]}...")
        
        llm_step_success = True
        
    except ImportError as e:
        log(f"❌ 导入错误: {e}")
        llm_step_success = False
    except Exception as e:
        log(f"❌ LLM Provider 测试失败: {e}")
        import traceback
        traceback.print_exc()
        llm_step_success = False
    
    # ===== 步骤3: 测试单个 Agent =====
    log_section("步骤3: 测试单个 LLM Agent")
    
    try:
        from agents.llm import create_llm_agent
        from agents.llm.models import StockAnalysisContext
        
        log(f"创建 Technical Analyst Agent...")
        tech_agent = create_llm_agent(
            role="technical",
            provider="openai_compatible",
            api_key=os.environ["OPENAI_API_KEY"],
            base_url=os.environ["OPENAI_BASE_URL"],
            model="deepseek-v3.1-thinking"
        )
        log(f"✅ 技术分析 Agent 创建成功")
        
        context = StockAnalysisContext(
            stock_code=stock_code,
            stock_name=stock_name,
            task_id="002202_001",
            user_request="技术分析",
            market_data=data
        )
        
        log(f"\n执行技术分析...")
        tech_report = tech_agent.analyze(context)
        log(f"✅ 技术分析完成")
        log(f"   评分: {tech_report.score}/10")
        log(f"   置信度: {tech_report.confidence:.0%}")
        log(f"   总结: {tech_report.summary[:200]}...")
        
        single_agent_success = True
        
    except ImportError as e:
        log(f"❌ 导入错误: {e}")
        single_agent_success = False
    except Exception as e:
        log(f"❌ 单个 Agent 测试失败: {e}")
        import traceback
        traceback.print_exc()
        single_agent_success = False
    
    # ===== 步骤4: 测试完整 Agent Team 讨论 =====
    log_section("步骤4: 测试完整 Agent Team 讨论 (2轮)")
    
    try:
        from agents.llm import create_team
        from conversation import DiscussionManager
        
        log(f"创建 Agent 团队...")
        team = create_team(
            provider="openai_compatible",
            api_key=os.environ["OPENAI_API_KEY"],
            base_url=os.environ["OPENAI_BASE_URL"],
            model="deepseek-v3.1-thinking"
        )
        
        leader = team["leader"]
        agents = [team["technical"], team["intelligence"], team["risk"], team["fundamental"]]
        log(f"✅ Agent 团队创建成功")
        log(f"   Leader: {type(leader).__name__}")
        log(f"   Agents: {[type(a).__name__ for a in agents]}")
        
        manager = DiscussionManager(
            leader=leader,
            agents=agents,
            max_rounds=2
        )
        log(f"✅ 讨论管理器创建成功")
        
        log(f"\n开始2轮多 Agent 讨论...")
        result = manager.start_discussion_sync(
            stock_code=stock_code,
            stock_name=stock_name,
            data=data
        )
        
        log(f"\n✅ Agent Team 讨论完成")
        log(f"\n" + "-" * 50)
        log(f"【分析结果】")
        log(f"-" * 50)
        log(f"股票: {result.stock_name} ({result.stock_code})")
        log(f"建议: {result.recommendation}")
        log(f"综合评分: {result.overall_score}/10")
        log(f"置信度: {result.confidence:.0%}")
        log(f"\n决策理由:")
        log(f"{result.reasoning}")
        
        if result.risks:
            log(f"\n风险提示:")
            for i, risk in enumerate(result.risks[:5], 1):
                log(f"  {i}. {risk}")
        
        team_success = True
        final_result = result
        
    except ImportError as e:
        log(f"❌ 导入错误: {e}")
        team_success = False
    except Exception as e:
        log(f"❌ Agent Team 讨论失败: {e}")
        import traceback
        traceback.print_exc()
        team_success = False
    
    # ===== 最终报告 =====
    log_section("最终报告")
    
    report = {
        "分析目标": f"{stock_name} ({stock_code})",
        "分析时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "步骤执行情况": {
            "数据获取": "✅ 成功" if data_step_success else "❌ 失败",
            "LLM Provider": "✅ 成功" if llm_step_success else "❌ 失败",
            "单个Agent": "✅ 成功" if single_agent_success else "❌ 失败",
            "Agent Team讨论": "✅ 成功" if team_success else "❌ 失败"
        },
        "系统问题": [],
        "改进建议": []
    }
    
    # 检测问题
    if not data_step_success:
        report["系统问题"].append("数据获取模块存在问题，可能是akshare/efinance库未安装或API接口变更")
    
    if not llm_step_success:
        report["系统问题"].append("LLM Provider无法正常连接，可能是API Key无效或Base URL配置错误")
    
    if not single_agent_success:
        report["系统问题"].append("单个LLM Agent执行失败，可能是Agent实现问题或LLM调用异常")
    
    if not team_success:
        report["系统问题"].append("Agent Team多轮讨论失败，可能是讨论引擎实现问题")
    
    if data_step_success and data.get("technical"):
        tech_data = data["technical"]
        if not tech_data.get("current_price"):
            report["系统问题"].append("技术指标数据不完整，缺少current_price字段")
    
    # 改进建议
    if not data_step_success:
        report["改进建议"].append("安装/更新依赖: pip install akshare efinance")
        report["改进建议"].append("检查网络连接和防火墙设置")
    
    if not llm_step_success:
        report["改进建议"].append("验证API Key是否有效")
        report["改进建议"].append("检查Base URL是否可访问")
    
    if len(report["系统问题"]) == 0:
        report["系统问题"].append("未发现明显问题")
    
    if len(report["改进建议"]) == 0:
        report["改进建议"].append("系统运行正常，可以正常使用")
    
    log(f"\n【问题汇总】")
    for i, issue in enumerate(report["系统问题"], 1):
        log(f"  {i}. {issue}")
    
    log(f"\n【改进建议】")
    for i, suggestion in enumerate(report["改进建议"], 1):
        log(f"  {i}. {suggestion}")
    
    if team_success:
        log(f"\n【002202金风科技分析结果】")
        log(f"  建议: {final_result.recommendation}")
        log(f"  评分: {final_result.overall_score}/10")
        log(f"  置信度: {final_result.confidence:.0%}")
    
    # 保存报告到文件
    report_file = "002202_analysis_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log(f"\n报告已保存到: {report_file}")
    
    log("\n" + "=" * 70)
    log("分析完成!")
    log("=" * 70)
    
    return report

if __name__ == "__main__":
    main()
