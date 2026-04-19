"""
主程序入口
中短线波段 Agent Team 系统
支持网络情报注入，增强情报分析能力

情报注入模式：
1. 自动模式：配置搜索API后，--with-intel 会自动搜索并注入
2. 桥接模式：未配置API时，输出搜索任务JSON，等待外部注入
"""
import argparse
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

from agents.base_agent import AgentContext
from agents.leader import Leader
from agents.review_analyst import ReviewAnalyst
from agents.web_intelligence import WebIntelligenceGatherer
from config.intel_config import has_search_capability, get_active_search_provider
from protocols.message_protocol import TradeDecisionMessage
from storage.database import db
from utils.intel_searcher import intel_searcher, format_intel_for_injection
from utils.logger import get_logger


class StockAgentTeam:
    """股票Agent Team系统"""
    
    def __init__(self):
        """初始化系统"""
        self.logger = get_logger('StockAgentTeam')
        
        # 初始化Leader
        self.leader = Leader()
        
        # 初始化复盘分析师
        self.reviewer = ReviewAnalyst()
        
        # 网络情报搜集器
        self.web_intel_gatherer = WebIntelligenceGatherer()
        
        self.logger.info("Stock Agent Team 系统初始化完成")
    
    def get_web_intel_tasks(self, stock_code: str, stock_name: str) -> List[Dict[str, Any]]:
        """获取网络情报搜索任务
        
        供主Agent执行，返回需要搜索的任务列表
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            
        Returns:
            搜索任务列表
        """
        return self.web_intel_gatherer.get_search_tasks(stock_code, stock_name)
    
    def analyze(self, stock_code: str, stock_name: str, 
                user_request: str = "",
                web_intelligence: Optional[Dict[str, Any]] = None) -> TradeDecisionMessage:
        """
        分析股票
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            user_request: 用户请求描述
            web_intelligence: 网络情报数据（由主Agent搜集后传入）
                格式: {type: [results]} 如 {'news': [...], 'research': [...]}
        
        Returns:
            交易决策消息
        """
        self.logger.info(f"开始分析: {stock_name}({stock_code})")
        
        # 处理网络情报
        additional_info = {}
        if web_intelligence:
            # 检测是否是已构建的报告格式
            if 'stock_code' in web_intelligence and 'gather_time' in web_intelligence:
                # 已经是处理过的报告格式，直接使用
                additional_info['web_intelligence'] = web_intelligence
                self.logger.info(f"已注入网络情报报告: {web_intelligence.get('stock_code')}")
            else:
                # 原始搜索结果格式，需要构建报告
                intel_report = self.web_intel_gatherer.build_report(
                    stock_code, stock_name, web_intelligence
                )
                additional_info['web_intelligence'] = intel_report.to_dict()
                self.logger.info(f"已注入网络情报: {len(web_intelligence)} 类")
        
        # 创建分析上下文
        context = AgentContext(
            task_id=f"TASK_{datetime.now().strftime('%Y%m%d%H%M%S')}_{stock_code}",
            stock_code=stock_code,
            stock_name=stock_name,
            user_request=user_request,
            additional_info=additional_info
        )
        
        # 执行分析
        decision = self.leader.analyze(context)
        
        return decision
    
    def review(self, review_type: str = 'weekly', 
               trade_id: Optional[str] = None) -> Dict[str, Any]:
        """
        执行复盘
        
        Args:
            review_type: 复盘类型 (single/weekly/monthly)
            trade_id: 交易ID（单笔复盘时需要）
        
        Returns:
            复盘结果
        """
        self.logger.info(f"开始复盘: {review_type}")
        
        result = self.reviewer.execute_review(review_type, trade_id)
        
        return result
    
    def get_current_weights(self) -> Dict[str, float]:
        """获取当前权重配置"""
        return db.get_current_weights()
    
    def update_weights(self, weights: Dict[str, float], reason: str):
        """更新权重配置"""
        db.save_weights(weights, reason)
        self.logger.info(f"权重已更新: {weights}")
    
    def get_trade_statistics(self, start_date: str = None, 
                             end_date: str = None) -> Dict[str, Any]:
        """获取交易统计"""
        return db.get_trade_statistics(start_date, end_date)
    
    def get_active_holdings(self) -> list:
        """获取当前持仓"""
        return db.get_active_holdings()


def gather_intelligence_auto(stock_code: str, stock_name: str) -> Dict[str, Any]:
    """
    自动搜索并收集情报（需要配置搜索API）
    
    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        
    Returns:
        格式化后的情报数据
    """
    team = StockAgentTeam()
    tasks = team.get_web_intel_tasks(stock_code, stock_name)
    
    search_results = {}
    
    for task in tasks:
        task_type = task['type']
        query = task['query']
        max_results = task['max_results']
        
        print(f"  搜索 {task_type}: {query}")
        results = intel_searcher.search(query, max_results)
        
        if results:
            search_results[task_type] = results
            print(f"    -> 获取 {len(results)} 条结果")
    
    return format_intel_for_injection(search_results)


def print_bridge_mode_instructions(stock_code: str, stock_name: str):
    """
    打印桥接模式的使用说明
    
    当未配置搜索API时，输出JSON格式的搜索任务，
    等待外部Agent（如主对话Agent）执行搜索并注入结果
    """
    team = StockAgentTeam()
    tasks = team.get_web_intel_tasks(stock_code, stock_name)
    
    print("\n" + "=" * 60)
    print("📡 网络情报注入 - 桥接模式")
    print("=" * 60)
    print("\n未配置搜索API，需要外部Agent执行搜索。")
    print("请将以下搜索任务JSON传递给具有搜索能力的Agent：\n")
    
    # 输出搜索任务JSON
    bridge_data = {
        "mode": "bridge",
        "action": "search_and_inject",
        "stock_code": stock_code,
        "stock_name": stock_name,
        "search_tasks": tasks,
        "instruction": "请执行上述搜索任务，将结果格式化为 {type: [{title, snippet, url, time}]} 后注入"
    }
    
    print("```json")
    print(json.dumps(bridge_data, ensure_ascii=False, indent=2))
    print("```")
    
    print("\n" + "-" * 60)
    print("提示：配置搜索API后可启用自动模式")
    print("配置文件: config/intel_config.py")
    print("支持的API: Bing / Google / Serper")
    print("=" * 60)


def run_with_bridge_intel(stock_code: str, stock_name: str, search_results: Dict[str, List]) -> TradeDecisionMessage:
    """
    使用桥接模式传入的情报运行分析
    
    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        search_results: 外部Agent搜索得到的结果
        
    Returns:
        交易决策
    """
    team = StockAgentTeam()
    
    # 格式化情报
    web_intel = format_intel_for_injection(search_results)
    
    # 执行分析
    return team.analyze(stock_code, stock_name, "分析是否适合中短线买入", web_intel)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='中短线波段 Agent Team 系统')
    parser.add_argument('--code', type=str, default='300750', help='股票代码')
    parser.add_argument('--name', type=str, default='宁德时代', help='股票名称')
    parser.add_argument('--no-review', action='store_true', help='跳过复盘')
    parser.add_argument('--with-intel', action='store_true', help='启用网络情报注入')
    parser.add_argument('--intel-data', type=str, default=None, help='直接注入情报JSON（桥接模式）')
    args = parser.parse_args()
    
    print("=" * 60)
    print("中短线波段 Agent Team 系统")
    print("=" * 60)
    
    # 初始化系统
    team = StockAgentTeam()
    
    # 处理网络情报
    web_intelligence = None
    
    if args.with_intel:
        print("\n【网络情报】已启用")
        print("-" * 60)
        
        # 检查是否有直接传入的情报数据
        if args.intel_data:
            try:
                web_intelligence = json.loads(args.intel_data)
                print(f"  已接收外部情报数据: {len(web_intelligence)} 类")
            except json.JSONDecodeError as e:
                print(f"  ⚠️ 情报JSON解析失败: {e}")
        
        # 检查是否配置了自动搜索
        elif has_search_capability():
            print(f"  使用自动搜索模式 (provider: {get_active_search_provider()})")
            web_intelligence = gather_intelligence_auto(args.code, args.name)
            print(f"  情报收集完成: {len(web_intelligence)} 类")
        
        # 未配置API，进入桥接模式
        else:
            print_bridge_mode_instructions(args.code, args.name)
            sys.exit(0)  # 等待外部注入
    
    # 分析股票
    print(f"\n【分析股票】{args.name}({args.code})")
    print("-" * 60)
    
    decision = team.analyze(
        args.code, args.name, 
        "分析是否适合中短线买入",
        web_intelligence
    )
    
    # 检查是否使用了模拟数据
    from utils.data_fetcher import data_fetcher
    is_mock = data_fetcher.is_mock_data(args.code)

    # 打印决策结果
    print(f"\n决策结果:")
    print(f"  股票: {decision.stock_name}({decision.stock_code})")
    print(f"  动作: {decision.final_action}")
    print(f"  综合评分: {decision.composite_score:.2f}")
    print(f"  置信度: {decision.confidence}")
    
    if is_mock:
        print(f"  ⚠️ 注意: 技术分析使用了模拟数据，结果仅供参考")

    if decision.is_buy:
        print(f"  入场区间: {decision.entry_zone}")
        print(f"  止损位: {decision.stop_loss:.2f}")
        print(f"  建议仓位: {decision.position_size*100:.0f}%")
    
    # 打印买入理由
    print(f"\n买入理由:")
    for reason in decision.rationale.get('buy_reasons', []):
        print(f"  - {reason}")
    
    # 打印风险点
    print(f"\n风险点:")
    for risk in decision.rationale.get('risk_warnings', []):
        print(f"  - {risk}")
    
    # 示例：周度复盘（可选）
    if not args.no_review:
        print("\n" + "=" * 60)
        print("【示例复盘】周度复盘")
        print("-" * 60)
        
        review_result = team.review('weekly')
        
        # 正确输出复盘报告
        report_text = review_result.get('report', '无报告')
        if isinstance(report_text, str) and report_text.strip():
            print(f"\n{report_text}")
        else:
            # 如果没有格式化报告，输出关键数据
            print(f"\n复盘类型: {review_result.get('review_type', 'unknown')}")
            stats = review_result.get('stats', {})
            if stats:
                print(f"  总交易: {stats.get('total_trades', 0)}笔")
                print(f"  胜率: {stats.get('win_rate', 0):.1f}%")
                print(f"  总收益: {stats.get('total_return', 0):.2f}%")
            print(f"  复盘评分: {review_result.get('overall_score', 0):.1f}")

    print("\n" + "=" * 60)
    print("系统运行完成")
    print("=" * 60)


if __name__ == "__main__":
    main()



# ==============================================================================
# 观察池模块命令行入口
# ==============================================================================

def run_watchlist_command(args):
    """
    执行观察池命令
    
    Args:
        args: 解析后的命令行参数
    """
    from watchlist import (
        WatchlistManager
    )
    
    action = args.watchlist_action
    
    if action == 'status':
        # 查看观察池状态
        manager = WatchlistManager()
        stats = manager.get_statistics()
        
        print("\n" + "=" * 60)
        print("📊 观察池状态")
        print("=" * 60)
        print(f"  股票总数: {stats['total']}")
        print(f"  推荐买入: {stats['buy_recommended']}")
        print(f"  待处理: {stats['by_status'].get('pending', 0)}")
        print(f"  观察中: {stats['by_status'].get('watching', 0)}")
        print(f"  已归档: {stats['by_status'].get('archived', 0)}")
        print(f"  更新时间: {stats['last_update']}")
        print("=" * 60)
        
        # 显示推荐买入列表
        buy_list = manager.get_buy_recommended()
        if buy_list:
            print("\n🔥 推荐买入:")
            for i, c in enumerate(buy_list, 1):
                print(f"  {i}. {c.name}({c.code}) 评分:{c.composite_score:.1f}")
        
        return
    
    elif action == 'list':
        # 列出所有股票
        manager = WatchlistManager()
        status_filter = args.status if hasattr(args, 'status') and args.status else None
        candidates = manager.get_all_candidates(status=status_filter)
        
        print("\n" + "=" * 60)
        print(f"📋 观察池列表 {'(' + status_filter + ')' if status_filter else '(全部)'}")
        print("=" * 60)
        
        if not candidates:
            print("  暂无股票")
        else:
            for i, c in enumerate(candidates, 1):
                status_icon = {'pending': '⏳', 'watching': '👀', 'archived': '📁'}.get(c.status, '❓')
                score = f"{c.composite_score:.1f}" if c.composite_score else f"{c.source_score:.1f}*"
                print(f"  {i}. {status_icon} {c.name}({c.code}) 评分:{score} | {c.add_reason}")
        
        print("=" * 60)
        return
    
    elif action == 'add':
        # 添加股票
        from watchlist.models import StockCandidate
        
        candidate = StockCandidate(
            code=args.code,
            name=args.name,
            add_date=datetime.now().strftime('%Y-%m-%d'),
            add_reason=args.reason if hasattr(args, 'reason') and args.reason else '手动添加',
            source='manual',
            source_score=50.0,
            added_by='cli',
        )
        
        manager = WatchlistManager()
        manager.add_candidate(candidate)
        return
    
    elif action == 'remove':
        # 移除股票
        manager = WatchlistManager()
        reason = args.reason if hasattr(args, 'reason') and args.reason else '手动移除'
        manager.remove_candidate(args.code, reason)
        return
    
    elif action == 'analyze':
        # 分析股票
        manager = WatchlistManager()
        candidate = manager.get_candidate(args.code)
        
        if not candidate:
            print(f"  ⚠️ {args.code} 不在观察池中")
            return
        
        manager.change_status(args.code, 'analyzing')
        
        print(f"\n开始分析: {candidate.name}({candidate.code})")
        
        team = StockAgentTeam()

        # 自动收集网络情报（如果搜索API可用）
        web_intel = None
        if has_search_capability():
            print(f"  正在收集网络情报 (provider: {get_active_search_provider()})...")
            try:
                web_intel = gather_intelligence_auto(candidate.code, candidate.name)
                print(f"  情报收集完成: {len(web_intel)} 类")
            except Exception as e:
                print(f"  ⚠️ 情报收集失败: {e}")
        else:
            # 尝试读取已存储的情报（由IntelligenceOfficer._load_stored_intel处理）
            print(f"  未配置搜索API，将使用已存储的情报数据")

        decision = team.analyze(
            candidate.code,
            candidate.name,
            "中短线波段分析",
            web_intel
        )
        
        # 更新分析结果
        manager.update_analysis_result(
            candidate.code,
            {
                'action': decision.final_action,
                'confidence': decision.confidence,
                'rationale': decision.rationale,
            },
            decision.composite_score,
            decision.is_buy,
        )
        
        print(f"\n分析结果:")
        print(f"  动作: {decision.final_action}")
        print(f"  评分: {decision.composite_score:.2f}")
        print(f"  置信度: {decision.confidence}")
        return
    
    elif action == 'export':
        # 导出报告
        manager = WatchlistManager()
        include_removed = args.include_removed if hasattr(args, 'include_removed') else False
        
        report = manager.export_report(include_removed=include_removed)
        print(report)
        return
    
    else:
        print(f"  ⚠️ 未知操作: {action}")


def run_collect_command(args):
    """执行数据采集命令"""
    from watchlist import DataCollector, StockScreener, WatchlistManager
    
    print("\n" + "=" * 60)
    print("📡 数据采集")
    print("=" * 60)
    
    collector = DataCollector()
    screener = StockScreener()
    manager = WatchlistManager()
    
    # 采集数据
    print("\n正在采集数据...")
    results = collector.collect_all()
    
    print(f"  龙虎榜: {len(results.get('dragon_tiger', []))} 条")
    print(f"  热门板块: {len(results.get('sector_hot', []))} 条")
    print(f"  机构调研: {len(results.get('research', []))} 条")
    
    # 筛选
    print("\n正在筛选候选股票...")
    existing_codes = [c.code for c in manager.get_all_candidates()]
    
    candidates = screener.screen_candidates(
        dragon_tiger_data=results.get('dragon_tiger', []),
        sector_data=results.get('sector_hot', []),
        research_data=results.get('research', []),
        existing_codes=existing_codes,
    )
    
    print(f"  筛选出 {len(candidates)} 只候选股票")
    
    if candidates:
        print("\n候选股票列表:")
        report = screener.get_screening_report(candidates)
        print(report)
        
        # 询问是否添加到观察池
        if args.add_to_watchlist if hasattr(args, 'add_to_watchlist') else False:
            added = manager.add_candidates_batch(candidates)
            print(f"\n已添加 {added} 只股票到观察池")
    else:
        print("  未筛选出符合条件的股票")


def run_screen_command(args):
    """执行股票筛选命令"""
    from watchlist import DataCollector, StockScreener
    
    print("\n" + "=" * 60)
    print("📊 股票筛选")
    print("=" * 60)
    
    collector = DataCollector()
    screener = StockScreener()
    
    # 尝试加载缓存数据
    print("\n加载缓存数据...")
    dragon_data = collector.load_cache('dragon_tiger')
    sector_data = collector.load_cache('sector')
    research_data = collector.load_cache('research')
    
    # 如果没有缓存，进行采集
    if not dragon_data and not sector_data and not research_data:
        print("  缓存为空，开始采集...")
        results = collector.collect_all()
        dragon_data = [d.to_dict() if hasattr(d, 'to_dict') else d for d in results.get('dragon_tiger', [])]
        sector_data = [d.to_dict() if hasattr(d, 'to_dict') else d for d in results.get('sector_hot', [])]
        research_data = [d.to_dict() if hasattr(d, 'to_dict') else d for d in results.get('research', [])]
    
    from watchlist.models import DragonTigerData, SectorHotData, ResearchData
    
    # 转换数据
    dragon_objs = [DragonTigerData.from_dict(d) for d in (dragon_data or [])]
    sector_objs = [SectorHotData.from_dict(d) for d in (sector_data or [])]
    research_objs = [ResearchData.from_dict(d) for d in (research_data or [])]
    
    # 筛选
    candidates = screener.screen_candidates(
        dragon_tiger_data=dragon_objs,
        sector_data=sector_objs,
        research_data=research_objs,
        existing_codes=args.exclude.split(',') if hasattr(args, 'exclude') and args.exclude else [],
    )
    
    print(f"\n筛选出 {len(candidates)} 只候选股票")
    
    if candidates:
        report = screener.get_screening_report(candidates)
        print("\n" + report)


def run_auto_command(args):
    """执行完整自动化流程"""
    from watchlist import AutoScheduler
    
    print("\n" + "=" * 60)
    print("🤖 自动化执行")
    print("=" * 60)
    
    scheduler = AutoScheduler()
    
    if args.task:
        # 执行指定任务
        scheduler.run_task_now(args.task)
    else:
        # 执行完整流程
        results = scheduler.run_full_pipeline(force=args.force)
        
        # 输出结果
        print("\n" + "=" * 60)
        print("📋 执行结果")
        print("=" * 60)
        print(json.dumps(results, ensure_ascii=False, indent=2))


def run_schedule_command(args):
    """执行调度器命令"""
    from watchlist import AutoScheduler
    
    scheduler = AutoScheduler()
    
    if args.schedule_action == 'list':
        # 列出所有任务
        print(scheduler.get_schedule_report())
        
    elif args.schedule_action == 'start':
        # 启动调度器
        interval = args.interval if hasattr(args, 'interval') else 60
        scheduler.start(check_interval=interval)
        print("调度器已启动，按 Ctrl+C 停止")
        
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            scheduler.stop()
            
    elif args.schedule_action == 'stop':
        # 停止调度器
        scheduler.stop()
        
    elif args.schedule_action == 'run':
        # 立即执行任务
        if args.task_id:
            scheduler.run_task_now(args.task_id)
        else:
            print("  ⚠️ 请指定任务ID (--task-id)")
            
    elif args.schedule_action == 'enable':
        if args.task_id:
            scheduler.enable_task(args.task_id)
        else:
            print("  ⚠️ 请指定任务ID (--task_id)")
            
    elif args.schedule_action == 'disable':
        if args.task_id:
            scheduler.disable_task(args.task_id)
        else:
            print("  ⚠️ 请指定任务ID (--task_id)")


def add_watchlist_parser(subparsers):
    """添加观察池子命令解析器"""
    parser = subparsers.add_parser('watchlist', help='观察池管理')
    parser.add_argument('watchlist_action', 
                        choices=['status', 'list', 'add', 'remove', 'analyze', 'export'],
                        help='观察池操作')
    parser.add_argument('--code', type=str, help='股票代码')
    parser.add_argument('--name', type=str, help='股票名称')
    parser.add_argument('--reason', type=str, help='添加/移除原因')
    parser.add_argument('--status', type=str, choices=['pending', 'watching', 'archived', 'removed'],
                        help='按状态过滤')
    parser.add_argument('--include-removed', action='store_true', help='导出时包含已移除股票')
    return parser


def add_collect_parser(subparsers):
    """添加采集子命令解析器"""
    parser = subparsers.add_parser('collect', help='采集数据')
    parser.add_argument('--add-to-watchlist', action='store_true', help='采集后添加到观察池')
    return parser


def add_screen_parser(subparsers):
    """添加筛选子命令解析器"""
    parser = subparsers.add_parser('screen', help='筛选股票')
    parser.add_argument('--exclude', type=str, help='排除的股票代码(逗号分隔)')
    return parser


def add_auto_parser(subparsers):
    """添加自动执行子命令解析器"""
    parser = subparsers.add_parser('auto', help='自动化执行')
    parser.add_argument('--task', type=str, help='指定任务ID')
    parser.add_argument('--force', action='store_true', help='强制分析所有股票')
    return parser


def add_schedule_parser(subparsers):
    """添加调度器子命令解析器"""
    parser = subparsers.add_parser('schedule', help='调度器管理')
    parser.add_argument('schedule_action',
                        choices=['list', 'start', 'stop', 'run', 'enable', 'disable'],
                        help='调度器操作')
    parser.add_argument('--task-id', type=str, help='任务ID')
    parser.add_argument('--interval', type=int, default=60, help='检查间隔(秒)')


# 模块级别：检查是否需要转发到独立命令行
import sys
if len(sys.argv) > 1 and sys.argv[1] in ['watchlist', 'collect', 'screen', 'auto', 'schedule', 'wl']:
    import os
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    os.system(f'{sys.executable} run_watchlist.py {" ".join(sys.argv[1:])}')
    sys.exit(0)


def main_with_watchlist():
    """带观察池功能的主函数"""
    import argparse
    import sys
    
    # 没有子命令时，使用原有逻辑
    parser = argparse.ArgumentParser(description='中短线波段 Agent Team 系统')
    parser.add_argument('--code', type=str, default='300750', help='股票代码')
    parser.add_argument('--name', type=str, default='宁德时代', help='股票名称')
    parser.add_argument('--no-review', action='store_true', help='跳过复盘')
    parser.add_argument('--with-intel', action='store_true', help='启用网络情报注入')
    parser.add_argument('--intel-data', type=str, default=None, help='直接注入情报JSON（桥接模式）')
    parser.add_argument('--watchlist', action='store_true', help='使用观察池命令行工具')
    
    args, unknown = parser.parse_known_args()
    
    if args.watchlist or unknown:
        import os
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        os.system(f'{sys.executable} run_watchlist.py status')
        return
    
    # 原有的股票分析逻辑
    print("=" * 60)
    print("中短线波段 Agent Team 系统")
    print("=" * 60)
    
    team = StockAgentTeam()
    
    web_intelligence = None
    
    if args.with_intel:
        print("\n【网络情报】已启用")
        print("-" * 60)
        
        if args.intel_data:
            try:
                web_intelligence = json.loads(args.intel_data)
                print(f"  已接收外部情报数据: {len(web_intelligence)} 类")
            except json.JSONDecodeError as e:
                print(f"  ⚠️ 情报JSON解析失败: {e}")
        
        elif has_search_capability():
            print(f"  使用自动搜索模式 (provider: {get_active_search_provider()})")
            web_intelligence = gather_intelligence_auto(args.code, args.name)
            print(f"  情报收集完成: {len(web_intelligence)} 类")
        
        else:
            print_bridge_mode_instructions(args.code, args.name)
            sys.exit(0)
    
    print(f"\n【分析股票】{args.name}({args.code})")
    print("-" * 60)
    
    decision = team.analyze(
        args.code, args.name, 
        "分析是否适合中短线买入",
        web_intelligence
    )
    
    from utils.data_fetcher import data_fetcher
    is_mock = data_fetcher.is_mock_data(args.code)

    print(f"\n决策结果:")
    print(f"  股票: {decision.stock_name}({decision.stock_code})")
    print(f"  动作: {decision.final_action}")
    print(f"  综合评分: {decision.composite_score:.2f}")
    print(f"  置信度: {decision.confidence}")
    
    if is_mock:
        print(f"  ⚠️ 注意: 技术分析使用了模拟数据，结果仅供参考")

    if decision.is_buy:
        print(f"  入场区间: {decision.entry_zone}")
        print(f"  止损位: {decision.stop_loss:.2f}")
        print(f"  建议仓位: {decision.position_size*100:.0f}%")
    
    print(f"\n买入理由:")
    for reason in decision.rationale.get('buy_reasons', []):
        print(f"  - {reason}")
    
    print(f"\n风险点:")
    for risk in decision.rationale.get('risk_warnings', []):
        print(f"  - {risk}")
    
    if not args.no_review:
        print("\n" + "=" * 60)
        print("【示例复盘】周度复盘")
        print("-" * 60)
        
        review_result = team.review('weekly')
        
        report_text = review_result.get('report', '无报告')
        if isinstance(report_text, str) and report_text.strip():
            print(f"\n{report_text}")
        else:
            print(f"\n复盘类型: {review_result.get('review_type', 'unknown')}")
            stats = review_result.get('stats', {})
            if stats:
                print(f"  总交易: {stats.get('total_trades', 0)}笔")
                print(f"  胜率: {stats.get('win_rate', 0):.1f}%")
                print(f"  总收益: {stats.get('total_return', 0):.2f}%")
            print(f"  复盘评分: {review_result.get('overall_score', 0):.1f}")

    print("\n" + "=" * 60)
    print("系统运行完成")
    print("=" * 60)


if __name__ == "__main__":
    main_with_watchlist()
