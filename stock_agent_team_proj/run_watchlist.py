#!/usr/bin/env python
"""
观察池系统独立命令行入口

使用方法：
  python run_watchlist.py status           # 查看状态
  python run_watchlist.py list             # 列出所有股票
  python run_watchlist.py add 300750 宁德时代  # 添加股票
  python run_watchlist.py remove 300750     # 移除股票
  python run_watchlist.py analyze 300750    # 分析股票
  python run_watchlist.py collect          # 采集数据
  python run_watchlist.py screen           # 筛选股票
  python run_watchlist.py auto             # 执行完整流程
  python run_watchlist.py schedule         # 查看调度计划
"""

import sys
import os
import argparse

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime


def cmd_status():
    """查看观察池状态"""
    from watchlist.watchlist_manager import WatchlistManager
    
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
    
    buy_list = manager.get_buy_recommended()
    if buy_list:
        print("\n🔥 推荐买入:")
        for i, c in enumerate(buy_list, 1):
            print(f"  {i}. {c.name}({c.code}) 评分:{c.composite_score:.1f}")


def cmd_list(args):
    """列出观察池股票"""
    from watchlist.watchlist_manager import WatchlistManager
    
    manager = WatchlistManager()
    candidates = manager.get_all_candidates(status=args.status)
    
    status_text = f"({args.status})" if args.status else "(全部)"
    print("\n" + "=" * 60)
    print(f"📋 观察池列表 {status_text}")
    print("=" * 60)
    
    if not candidates:
        print("  暂无股票")
    else:
        for i, c in enumerate(candidates, 1):
            status_icon = {'pending': '⏳', 'watching': '👀', 'archived': '📁'}.get(c.status, '❓')
            score = f"{c.composite_score:.1f}" if c.composite_score else f"{c.source_score:.1f}*"
            print(f"  {i}. {status_icon} {c.name}({c.code}) 评分:{score} | {c.add_reason}")
    
    print("=" * 60)


def cmd_add(args):
    """添加股票到观察池"""
    from watchlist.models import StockCandidate
    from watchlist.watchlist_manager import WatchlistManager
    
    candidate = StockCandidate(
        code=args.code,
        name=args.name,
        add_date=datetime.now().strftime('%Y-%m-%d'),
        add_reason=args.reason or '手动添加',
        source='manual',
        source_score=50.0,
        added_by='cli',
    )
    
    manager = WatchlistManager()
    manager.add_candidate(candidate)


def cmd_remove(args):
    """从观察池移除股票"""
    from watchlist.watchlist_manager import WatchlistManager
    
    manager = WatchlistManager()
    manager.remove_candidate(args.code, args.reason or '手动移除')


def cmd_analyze(args):
    """分析观察池中的股票"""
    from watchlist.watchlist_manager import WatchlistManager
    from main import StockAgentTeam
    
    manager = WatchlistManager()
    candidate = manager.get_candidate(args.code)
    
    if not candidate:
        print(f"  ⚠️ {args.code} 不在观察池中")
        return
    
    manager.change_status(args.code, 'analyzing')
    print(f"\n开始分析: {candidate.name}({candidate.code})")
    
    team = StockAgentTeam()
    decision = team.analyze(
        candidate.code,
        candidate.name,
        "中短线波段分析",
        None
    )
    
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


def cmd_collect(args):
    """采集数据"""
    from watchlist.data_collector import DataCollector
    from watchlist.stock_screener import StockScreener
    from watchlist.watchlist_manager import WatchlistManager
    
    print("\n" + "=" * 60)
    print("📡 数据采集")
    print("=" * 60)
    
    collector = DataCollector()
    screener = StockScreener()
    manager = WatchlistManager()
    
    print("\n正在采集数据...")
    results = collector.collect_all()
    
    print(f"  龙虎榜: {len(results.get('dragon_tiger', []))} 条")
    print(f"  热门板块: {len(results.get('sector_hot', []))} 条")
    print(f"  机构调研: {len(results.get('research', []))} 条")
    
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
        
        if args.add_to_watchlist:
            added = manager.add_candidates_batch(candidates)
            print(f"\n已添加 {added} 只股票到观察池")
    else:
        print("  未筛选出符合条件的股票")


def cmd_screen(args):
    """筛选股票"""
    from watchlist.data_collector import DataCollector
    from watchlist.stock_screener import StockScreener
    from watchlist.models import DragonTigerData, SectorHotData, ResearchData
    
    print("\n" + "=" * 60)
    print("📊 股票筛选")
    print("=" * 60)
    
    collector = DataCollector()
    screener = StockScreener()
    
    print("\n加载缓存数据...")
    dragon_data = collector.load_cache('dragon_tiger')
    sector_data = collector.load_cache('sector')
    research_data = collector.load_cache('research')
    
    if not dragon_data and not sector_data and not research_data:
        print("  缓存为空，开始采集...")
        results = collector.collect_all()
        dragon_data = [d.to_dict() if hasattr(d, 'to_dict') else d for d in results.get('dragon_tiger', [])]
        sector_data = [d.to_dict() if hasattr(d, 'to_dict') else d for d in results.get('sector_hot', [])]
        research_data = [d.to_dict() if hasattr(d, 'to_dict') else d for d in results.get('research', [])]
    
    dragon_objs = [DragonTigerData.from_dict(d) for d in (dragon_data or [])]
    sector_objs = [SectorHotData.from_dict(d) for d in (sector_data or [])]
    research_objs = [ResearchData.from_dict(d) for d in (research_data or [])]
    
    exclude_list = args.exclude.split(',') if args.exclude else []
    
    candidates = screener.screen_candidates(
        dragon_tiger_data=dragon_objs,
        sector_data=sector_objs,
        research_data=research_objs,
        existing_codes=exclude_list,
    )
    
    print(f"\n筛选出 {len(candidates)} 只候选股票")
    
    if candidates:
        report = screener.get_screening_report(candidates)
        print("\n" + report)


def cmd_auto(args):
    """执行自动化流程"""
    from watchlist.auto_scheduler import AutoScheduler
    
    print("\n" + "=" * 60)
    print("🤖 自动化执行")
    print("=" * 60)
    
    scheduler = AutoScheduler()
    
    if args.task:
        scheduler.run_task_now(args.task)
    else:
        results = scheduler.run_full_pipeline(force=args.force)
        
        print("\n" + "=" * 60)
        print("📋 执行结果")
        print("=" * 60)
        import json
        print(json.dumps(results, ensure_ascii=False, indent=2))


def cmd_schedule():
    """查看调度计划"""
    from watchlist.auto_scheduler import AutoScheduler
    
    scheduler = AutoScheduler()
    print(scheduler.get_schedule_report())


def cmd_performance(args):
    """查看表现统计"""
    from watchlist.watchlist_manager import WatchlistManager
    
    manager = WatchlistManager()
    
    if args.type == 'summary':
        manager.show_performance_summary()
    elif args.type == 'weekly':
        manager.show_performance_report('weekly')
    elif args.type == 'monthly':
        manager.show_performance_report('monthly')
    elif args.type == 'signal':
        manager.show_performance_report('signal')
    elif args.type == 'positions':
        # 持仓列表
        positions = manager.get_open_positions()
        print("\n" + "=" * 60)
        print("💼 当前持仓")
        print("=" * 60)
        if positions:
            for p in positions:
                ret = p.get('current_return', 0)
                emoji = "📈" if ret > 0 else "📉" if ret < 0 else "➖"
                print(f"  {emoji} {p.get('name')}({p.get('code')}) 入场:{p.get('entry_price')} 现价:{p.get('current_price')} {ret:.2f}%")
        else:
            print("  暂无持仓")
        print("=" * 60)
    elif args.type == 'closed':
        # 已平仓记录
        closed = manager.get_closed_positions(limit=args.limit)
        print("\n" + "=" * 60)
        print("🔚 已平仓记录")
        print("=" * 60)
        if closed:
            for s in closed:
                ret = s.get('return', 0)
                emoji = "✅" if ret > 0 else "❌"
                print(f"  {emoji} {s['name']}({s['code']}) {s['signal_date']}→{s['exit_date']} {ret:.2f}%")
        else:
            print("  暂无平仓记录")
        print("=" * 60)


def cmd_price_update(args):
    """更新价格"""
    from watchlist.watchlist_manager import WatchlistManager
    
    manager = WatchlistManager()
    print("\n正在更新价格...")
    results = manager.update_prices()
    print(f"  成功: {results['success']} 失败: {results['failed']}")
    for u in results.get('updates', [])[:5]:
        print(f"  {u['code']}: {u['price']} ({u['change_pct']:+.2f}%)")


def cmd_close(args):
    """平仓"""
    from watchlist.watchlist_manager import WatchlistManager
    
    manager = WatchlistManager()
    manager.close_position(args.code, args.reason or '手动平仓')


def cmd_export_report(args):
    """导出报告"""
    from watchlist.watchlist_manager import WatchlistManager
    
    manager = WatchlistManager()
    content = manager.export_performance_report(args.type, args.file)
    print(content)


def main():
    parser = argparse.ArgumentParser(
        description='股票观察池系统命令行工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python run_watchlist.py status                    # 查看状态
  python run_watchlist.py list                      # 列出所有股票
  python run_watchlist.py list --status pending     # 只看待处理
  python run_watchlist.py add 300750 宁德时代       # 添加股票
  python run_watchlist.py remove 300750             # 移除股票
  python run_watchlist.py analyze 300750             # 分析股票
  python run_watchlist.py collect                    # 采集数据
  python run_watchlist.py collect --add            # 采集并添加
  python run_watchlist.py screen                    # 筛选股票
  python run_watchlist.py screen --exclude 300750  # 排除指定股票
  python run_watchlist.py auto                      # 执行完整流程
  python run_watchlist.py schedule                  # 查看调度计划
  python run_watchlist.py performance               # 查看表现统计
  python run_watchlist.py performance --type weekly # 查看周报
  python run_watchlist.py performance --type positions # 查看持仓
  python run_watchlist.py price                     # 更新价格
  python run_watchlist.py close 300750             # 平仓股票
  python run_watchlist.py export-report            # 导出报告
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='子命令')
    
    # status
    subparsers.add_parser('status', help='查看观察池状态')
    
    # list
    list_parser = subparsers.add_parser('list', help='列出观察池股票')
    list_parser.add_argument('--status', choices=['pending', 'watching', 'archived'],
                            help='按状态过滤')
    
    # add
    add_parser = subparsers.add_parser('add', help='添加股票')
    add_parser.add_argument('code', help='股票代码')
    add_parser.add_argument('name', help='股票名称')
    add_parser.add_argument('--reason', default='手动添加', help='添加原因')
    
    # remove
    remove_parser = subparsers.add_parser('remove', help='移除股票')
    remove_parser.add_argument('code', help='股票代码')
    remove_parser.add_argument('--reason', default='手动移除', help='移除原因')
    
    # analyze
    analyze_parser = subparsers.add_parser('analyze', help='分析股票')
    analyze_parser.add_argument('code', help='股票代码')
    
    # collect
    collect_parser = subparsers.add_parser('collect', help='采集数据')
    collect_parser.add_argument('--add', action='store_true', 
                               dest='add_to_watchlist',
                               help='采集后添加到观察池')
    
    # screen
    screen_parser = subparsers.add_parser('screen', help='筛选股票')
    screen_parser.add_argument('--exclude', help='排除的股票代码(逗号分隔)')
    
    # auto
    auto_parser = subparsers.add_parser('auto', help='自动化执行')
    auto_parser.add_argument('--task', help='指定任务ID')
    auto_parser.add_argument('--force', action='store_true', help='强制分析所有股票')
    
    # schedule
    subparsers.add_parser('schedule', help='查看调度计划')
    
    # performance
    perf_parser = subparsers.add_parser('performance', help='查看表现统计')
    perf_parser.add_argument('--type', '-t', default='summary',
                            choices=['summary', 'weekly', 'monthly', 'signal', 'positions', 'closed'],
                            help='统计类型')
    perf_parser.add_argument('--limit', '-l', type=int, default=20,
                            help='显示数量限制')
    
    # price
    subparsers.add_parser('price', help='更新价格')
    
    # close
    close_parser = subparsers.add_parser('close', help='平仓')
    close_parser.add_argument('code', help='股票代码')
    close_parser.add_argument('--reason', help='平仓原因')
    
    # export-report
    export_parser = subparsers.add_parser('export-report', help='导出报告')
    export_parser.add_argument('--type', '-t', default='weekly',
                             choices=['weekly', 'monthly', 'signal'],
                             help='报告类型')
    export_parser.add_argument('--file', '-f', help='保存路径')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 执行相应命令
    commands = {
        'status': cmd_status,
        'list': cmd_list,
        'add': cmd_add,
        'remove': cmd_remove,
        'analyze': cmd_analyze,
        'collect': cmd_collect,
        'screen': cmd_screen,
        'auto': cmd_auto,
        'schedule': cmd_schedule,
        'performance': cmd_performance,
        'price': cmd_price_update,
        'close': cmd_close,
        'export-report': cmd_export_report,
    }
    
    cmd_func = commands.get(args.command)
    if cmd_func:
        try:
            if args.command in ['list', 'add', 'remove', 'analyze', 'collect', 'screen', 'auto', 'performance', 'close', 'export-report']:
                cmd_func(args)
            else:
                cmd_func()
        except Exception as e:
            print(f"\n❌ 执行失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"未知命令: {args.command}")


if __name__ == "__main__":
    main()
