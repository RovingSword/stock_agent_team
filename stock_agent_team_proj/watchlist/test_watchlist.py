"""
观察池系统 - 快速测试脚本
用于验证各模块功能
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_models():
    """测试数据模型"""
    print("\n" + "=" * 60)
    print("测试数据模型")
    print("=" * 60)
    
    from watchlist.models import (
        StockCandidate, WatchlistData, 
        DragonTigerData, SectorHotData, ResearchData
    )
    
    # 测试候选股票
    candidate = StockCandidate(
        code='300750',
        name='宁德时代',
        add_date='2024-04-18',
        add_reason='龙虎榜',
        source_score=85.0,
    )
    print(f"✅ 候选股票: {candidate.name}({candidate.code}) 评分:{candidate.source_score}")
    
    # 测试龙虎榜数据
    dt_data = DragonTigerData(
        date='2024-04-18',
        stock_code='300750',
        stock_name='宁德时代',
        reason='当日涨停',
        net_buy=5000.0,
        close_change=10.0,
    )
    print(f"✅ 龙虎榜数据: {dt_data.stock_name} {dt_data.reason}")
    
    # 测试观察池数据
    watchlist = WatchlistData(update_time='2024-04-18')
    watchlist.candidates.append(candidate)
    watchlist.update_stats()
    print(f"✅ 观察池: 共{watchlist.stats['total']}只股票")
    
    return True


def test_config():
    """测试配置"""
    print("\n" + "=" * 60)
    print("测试配置")
    print("=" * 60)
    
    from watchlist.config import config
    
    print(f"✅ 数据目录: {config.data_dir}")
    print(f"✅ 最小市值: {config.min_market_cap}亿")
    print(f"✅ 最大5日涨幅: {config.max_5day_gain}%")
    print(f"✅ 评分权重: {config.weights}")
    print(f"✅ 每日采集时间: {config.daily_collect_time}")
    print(f"✅ 每周更新时间: {config.weekly_update_time}")
    
    return True


def test_collector():
    """测试数据采集"""
    print("\n" + "=" * 60)
    print("测试数据采集")
    print("=" * 60)
    
    from watchlist.data_collector import DataCollector
    
    collector = DataCollector()
    
    # 测试龙虎榜采集
    print("采集龙虎榜数据...")
    dragon_data = collector.collect_dragon_tiger()
    print(f"✅ 龙虎榜: 采集{len(dragon_data)}条数据")
    
    # 测试板块采集
    print("采集板块数据...")
    sector_data = collector.collect_sector_hot()
    print(f"✅ 热门板块: 采集{len(sector_data)}条数据")
    
    # 测试机构调研采集
    print("采集机构调研数据...")
    research_data = collector.collect_research()
    print(f"✅ 机构调研: 采集{len(research_data)}条数据")
    
    return True


def test_screener():
    """测试股票筛选"""
    print("\n" + "=" * 60)
    print("测试股票筛选")
    print("=" * 60)
    
    from watchlist.data_collector import DataCollector
    from watchlist.stock_screener import StockScreener
    
    collector = DataCollector()
    screener = StockScreener()
    
    # 采集数据
    print("采集数据...")
    results = collector.collect_all()
    
    # 筛选
    print("筛选股票...")
    candidates = screener.screen_candidates(
        dragon_tiger_data=results.get('dragon_tiger', []),
        sector_data=results.get('sector_hot', []),
        research_data=results.get('research', []),
        existing_codes=[],
    )
    
    print(f"✅ 筛选出 {len(candidates)} 只候选股票")
    
    if candidates:
        report = screener.get_screening_report(candidates[:3])
        print("\n筛选报告预览:")
        print(report[:500])
    
    return True


def test_manager():
    """测试观察池管理"""
    print("\n" + "=" * 60)
    print("测试观察池管理")
    print("=" * 60)
    
    from watchlist.models import StockCandidate
    from watchlist.watchlist_manager import WatchlistManager
    
    manager = WatchlistManager()
    
    # 添加测试股票
    print("添加测试股票...")
    test_candidate = StockCandidate(
        code='TEST001',
        name='测试股票',
        add_date='2024-04-18',
        add_reason='测试添加',
        source='manual',
        source_score=70.0,
    )
    manager.add_candidate(test_candidate)
    
    # 查看状态
    stats = manager.get_statistics()
    print(f"✅ 观察池状态: 总{stats['total']}只股票")
    
    # 列出所有股票
    candidates = manager.get_all_candidates()
    print(f"✅ 当前股票: {[c.name for c in candidates]}")
    
    # 移除测试股票
    print("移除测试股票...")
    manager.remove_candidate('TEST001', '测试完成')
    
    return True


def test_scheduler():
    """测试调度器"""
    print("\n" + "=" * 60)
    print("测试调度器")
    print("=" * 60)
    
    from watchlist.auto_scheduler import AutoScheduler
    
    scheduler = AutoScheduler()
    
    # 列出任务
    tasks = scheduler.get_all_tasks()
    print(f"✅ 注册任务数: {len(tasks)}")
    
    for task in tasks:
        print(f"   - {task.task_name}({task.task_id}): {task.schedule_time}")
    
    # 查看调度报告
    report = scheduler.get_schedule_report()
    print("\n调度计划:")
    print(report[:300])
    
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("🧪 观察池系统测试")
    print("=" * 60)
    
    tests = [
        ("数据模型", test_models),
        ("配置", test_config),
        ("数据采集", test_collector),
        ("股票筛选", test_screener),
        ("观察池管理", test_manager),
        ("调度器", test_scheduler),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name}测试失败: {e}")
            results.append((name, False))
    
    # 总结
    print("\n" + "=" * 60)
    print("📊 测试结果")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {name}: {status}")
    
    passed = sum(1 for _, r in results if r)
    print(f"\n总计: {passed}/{len(results)} 项测试通过")
    
    return all(r for _, r in results)


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
