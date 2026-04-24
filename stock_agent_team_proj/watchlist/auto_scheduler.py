"""
自动调度器
实现定时任务的注册、执行和管理
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, Any, List, Optional, Callable
from .config import config
from .models import ScheduledTask


class AutoScheduler:
    """自动调度器"""
    
    # 定时任务ID常量
    TASK_DAILY_COLLECT = 'daily_collect'      # 每日数据采集
    TASK_WEEKLY_UPDATE = 'weekly_update'     # 每周观察池更新
    TASK_DAILY_PRICE_UPDATE = 'daily_price_update'  # 每日价格更新
    TASK_AUTO_ANALYZE = 'auto_analyze'          # 自动分析
    
    def __init__(self):
        self.config = config
        self.tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._callbacks: Dict[str, Callable] = {}
        
        # 加载任务配置
        self._load_tasks()
        
        # 注册默认任务
        self._register_default_tasks()
        self._normalize_task_weekdays()
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    def _load_tasks(self):
        """加载任务配置"""
        config_path = os.path.join(self.config.data_dir, 'scheduled_tasks.json')
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for task_data in data.get('tasks', []):
                        task = ScheduledTask.from_dict(task_data)
                        self.tasks[task.task_id] = task
            except Exception as e:
                print(f"  ⚠️ 加载任务配置失败: {e}")
    
    def _save_tasks(self):
        """保存任务配置"""
        config_path = os.path.join(self.config.data_dir, 'scheduled_tasks.json')
        
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        data = {
            'tasks': [t.to_dict() for t in self.tasks.values()]
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _register_default_tasks(self):
        """注册默认任务"""
        if self.TASK_DAILY_COLLECT not in self.tasks:
            self.tasks[self.TASK_DAILY_COLLECT] = ScheduledTask(
                task_id=self.TASK_DAILY_COLLECT,
                task_name='每日数据采集',
                task_type='collect',
                schedule_time=self.config.daily_collect_time,
                enabled=True,
                run_weekdays=[1, 2, 3, 4, 5],
            )
        
        if self.TASK_WEEKLY_UPDATE not in self.tasks:
            self.tasks[self.TASK_WEEKLY_UPDATE] = ScheduledTask(
                task_id=self.TASK_WEEKLY_UPDATE,
                task_name='每周观察池更新',
                task_type='full',
                schedule_time=self.config.weekly_update_time,
                enabled=True,
                run_weekdays=[6],
            )
        
        if self.TASK_DAILY_PRICE_UPDATE not in self.tasks:
            self.tasks[self.TASK_DAILY_PRICE_UPDATE] = ScheduledTask(
                task_id=self.TASK_DAILY_PRICE_UPDATE,
                task_name='每日价格更新',
                task_type='price_update',
                schedule_time='17:00',
                enabled=True,
                run_weekdays=[1, 2, 3, 4, 5],
            )
    
    def _normalize_task_weekdays(self):
        """为旧版持久化任务补全 run_weekdays，与 Web 预定义一致。"""
        defaults = {
            self.TASK_DAILY_COLLECT: [1, 2, 3, 4, 5],
            self.TASK_DAILY_PRICE_UPDATE: [1, 2, 3, 4, 5],
            self.TASK_WEEKLY_UPDATE: [6],
        }
        changed = False
        for tid, days in defaults.items():
            t = self.tasks.get(tid)
            if t and t.run_weekdays is None:
                t.run_weekdays = days
                changed = True
        if changed:
            self._save_tasks()
    
    def register_callback(self, task_id: str, callback: Callable):
        """
        注册任务回调函数
        
        Args:
            task_id: 任务ID
            callback: 回调函数
        """
        self._callbacks[task_id] = callback
    
    def register_task(
        self,
        task_id: str,
        task_name: str,
        task_type: str,
        schedule_time: str,
        enabled: bool = True,
        run_weekdays: Optional[List[int]] = None,
    ) -> ScheduledTask:
        """
        注册新任务
        
        Args:
            task_id: 任务ID
            task_name: 任务名称
            task_type: 任务类型 ('collect', 'screen', 'analyze', 'full')
            schedule_time: 执行时间 (HH:MM 或 cron格式)
            enabled: 是否启用
        
        Returns:
            创建的任务
        """
        task = ScheduledTask(
            task_id=task_id,
            task_name=task_name,
            task_type=task_type,
            schedule_time=schedule_time,
            enabled=enabled,
            run_weekdays=run_weekdays,
        )
        
        self.tasks[task_id] = task
        self._save_tasks()
        
        print(f"  ✅ 已注册任务: {task_name}({task_id})")
        return task
    
    def enable_task(self, task_id: str) -> bool:
        """启用任务"""
        task = self.tasks.get(task_id)
        if task:
            task.enabled = True
            self._save_tasks()
            print(f"  ✅ 已启用任务: {task.task_name}")
            return True
        return False
    
    def disable_task(self, task_id: str) -> bool:
        """禁用任务"""
        task = self.tasks.get(task_id)
        if task:
            task.enabled = False
            self._save_tasks()
            print(f"  ✅ 已禁用任务: {task.task_name}")
            return True
        return False
    
    def remove_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id in self.tasks:
            task_name = self.tasks[task_id].task_name
            del self.tasks[task_id]
            self._save_tasks()
            print(f"  ✅ 已删除任务: {task_name}")
            return True
        return False
    
    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[ScheduledTask]:
        """获取所有任务"""
        return list(self.tasks.values())
    
    def get_enabled_tasks(self) -> List[ScheduledTask]:
        """获取已启用的任务"""
        return [t for t in self.tasks.values() if t.enabled]
    
    @staticmethod
    def _js_weekday(dt: datetime) -> int:
        """与前端一致：0=周日 … 6=周六。"""
        return (dt.weekday() + 1) % 7
    
    def _time_hm(self, task: ScheduledTask) -> tuple:
        parts = task.schedule_time.split(':')
        if len(parts) >= 2:
            return int(parts[0]), int(parts[1])
        return 0, 0
    
    def _next_run_after(self, now: datetime, task: ScheduledTask) -> datetime:
        """下次触发时刻（严格晚于 now）。"""
        h, m = self._time_hm(task)
        for day_offset in range(0, 8):
            day = (now + timedelta(days=day_offset)).date()
            cand = datetime.combine(day, dt_time(hour=h, minute=m))
            if cand <= now:
                continue
            if task.run_weekdays is not None:
                if self._js_weekday(cand) not in task.run_weekdays:
                    continue
            return cand
        return now + timedelta(days=7)
    
    def _calculate_next_run(self, task: ScheduledTask) -> datetime:
        """计算下次执行时间（用于展示）。"""
        return self._next_run_after(datetime.now(), task)
    
    def _should_run_now(self, task: ScheduledTask) -> bool:
        """检查是否处于当日计划触发的 ±60 秒窗口内。"""
        if not task.enabled:
            return False
        now = datetime.now()
        if task.run_weekdays is not None:
            if self._js_weekday(now) not in task.run_weekdays:
                return False
        h, m = self._time_hm(task)
        slot = now.replace(hour=h, minute=m, second=0, microsecond=0)
        return abs((now - slot).total_seconds()) < 60
    
    def get_next_run_times(self) -> List[Dict[str, Any]]:
        """供 Web 展示各任务下次运行时间。"""
        out: List[Dict[str, Any]] = []
        now = datetime.now()
        for task in self.tasks.values():
            if not task.enabled:
                continue
            nxt = self._next_run_after(now, task)
            out.append({
                "task_id": task.task_id,
                "task_name": task.task_name,
                "next_run": nxt.isoformat(timespec="seconds"),
                "schedule_time": task.schedule_time,
                "run_weekdays": task.run_weekdays,
            })
        out.sort(key=lambda x: x["next_run"])
        return out
    
    def run_daily_collect(self) -> Dict[str, Any]:
        """执行数据采集并返回统计（与 _execute_task collect 共用逻辑）。"""
        from .data_collector import DataCollector
        collector = DataCollector()
        collect_results = collector.collect_all()
        return {
            "dragon_tiger_count": len(collect_results.get("dragon_tiger", [])),
            "sector_count": len(collect_results.get("sector_hot", [])),
            "research_count": len(collect_results.get("research", [])),
        }
    
    def start(self, check_interval: int = 60):
        """
        启动调度器
        
        Args:
            check_interval: 检查间隔（秒）
        """
        if self._running:
            print("  ⚠️ 调度器已在运行中")
            return
        
        self._running = True
        self._scheduler_thread = threading.Thread(
            target=self._run_loop,
            args=(check_interval,),
            daemon=True
        )
        self._scheduler_thread.start()
        print(f"  ✅ 调度器已启动 (检查间隔: {check_interval}秒)")
    
    def stop(self):
        """停止调度器"""
        self._running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
        print("  ✅ 调度器已停止")
    
    def _run_loop(self, check_interval: int):
        """运行循环"""
        while self._running:
            try:
                self._check_and_run_tasks()
            except Exception as e:
                print(f"  ⚠️ 调度器执行异常: {e}")
            
            time.sleep(check_interval)
    
    def _check_and_run_tasks(self):
        """检查并执行任务"""
        for task in self.tasks.values():
            if self._should_run_now(task):
                self._execute_task(task)
    
    def _execute_task(self, task: ScheduledTask):
        """执行任务"""
        print(f"\n{'='*60}")
        print(f"📋 执行任务: {task.task_name}")
        print(f"   任务ID: {task.task_id}")
        print(f"   类型: {task.task_type}")
        print(f"   执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print('='*60)
        
        task.last_run = datetime.now().isoformat()
        task.run_count += 1
        
        # 根据任务类型执行
        if task.task_type == 'price_update':
            self.run_price_update()
        elif task.task_type == 'collect':
            self.run_daily_collect()
        elif task.task_type == 'full':
            self.run_full_pipeline()
        
        # 执行回调
        callback = self._callbacks.get(task.task_id)
        if callback:
            try:
                callback(task)
            except Exception as e:
                print(f"  ⚠️ 任务执行失败: {e}")
        
        self._save_tasks()
        print(f"\n  ✅ 任务执行完成")
    
    def run_task_now(self, task_id: str) -> bool:
        """
        立即执行指定任务
        
        Args:
            task_id: 任务ID
        
        Returns:
            是否执行成功
        """
        task = self.tasks.get(task_id)
        if not task:
            print(f"  ⚠️ 任务不存在: {task_id}")
            return False
        
        self._execute_task(task)
        return True
    
    def run_full_pipeline(self, force: bool = False) -> Dict[str, Any]:
        """
        执行完整流程（采集+筛选+分析）
        
        Args:
            force: 是否强制分析所有股票
        
        Returns:
            执行结果
        """
        from .data_collector import DataCollector
        from .stock_screener import StockScreener
        from .watchlist_manager import WatchlistManager
        
        results = {
            'start_time': datetime.now().isoformat(),
            'collect': {},
            'screen': {},
            'analyze': {},
            'errors': [],
        }
        
        try:
            # 1. 数据采集
            print("\n📡 第一步：数据采集")
            print("-" * 40)
            collector = DataCollector()
            collect_results = collector.collect_all()
            results['collect'] = {
                'dragon_tiger_count': len(collect_results.get('dragon_tiger', [])),
                'sector_count': len(collect_results.get('sector_hot', [])),
                'research_count': len(collect_results.get('research', [])),
            }
            print(f"  龙虎榜: {results['collect']['dragon_tiger_count']} 条")
            print(f"  热门板块: {results['collect']['sector_count']} 条")
            print(f"  机构调研: {results['collect']['research_count']} 条")
            
            # 2. 股票筛选
            print("\n📊 第二步：股票筛选")
            print("-" * 40)
            manager = WatchlistManager()
            existing_codes = [c.code for c in manager.get_all_candidates()]
            
            screener = StockScreener()
            new_candidates = screener.screen_candidates(
                dragon_tiger_data=collect_results.get('dragon_tiger', []),
                sector_data=collect_results.get('sector_hot', []),
                research_data=collect_results.get('research', []),
                existing_codes=existing_codes,
            )
            
            results['screen'] = {
                'total_candidates': len(new_candidates),
                'added_to_watchlist': 0,
            }
            
            if new_candidates:
                # 添加到观察池
                added = manager.add_candidates_batch(new_candidates)
                results['screen']['added_to_watchlist'] = added
                print(f"  筛选出 {len(new_candidates)} 只候选股票")
                print(f"  新增 {added} 只到观察池")
            
            # 3. 分析观察池中的待处理股票
            print("\n🔍 第三步：分析候选股票")
            print("-" * 40)
            
            pending = manager.get_pending_candidates()
            if pending:
                if force:
                    to_analyze = pending
                else:
                    to_analyze = pending[:5]  # 默认分析前5只
                
                results['analyze'] = {
                    'total': len(to_analyze),
                    'success': 0,
                    'failed': 0,
                }
                
                for candidate in to_analyze:
                    try:
                        # 导入分析模块
                        from main import StockAgentTeam
                        
                        team = StockAgentTeam()
                        decision = team.analyze(
                            candidate.code,
                            candidate.name,
                            "中短线波段分析",
                            None
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
                        
                        results['analyze']['success'] += 1
                        print(f"  ✅ {candidate.name}({candidate.code}): {decision.final_action} ({decision.composite_score:.1f})")
                        
                    except Exception as e:
                        results['analyze']['failed'] += 1
                        results['errors'].append(f"{candidate.code}: {str(e)}")
                        print(f"  ❌ {candidate.name}({candidate.code}): {e}")
            else:
                results['analyze'] = {'total': 0, 'success': 0, 'failed': 0}
                print("  无待分析股票")
            
        except Exception as e:
            results['errors'].append(str(e))
            print(f"  ⚠️ 执行异常: {e}")
        
        results['end_time'] = datetime.now().isoformat()
        
        # 生成总结
        print("\n" + "=" * 60)
        print("📋 执行总结")
        print("=" * 60)
        print(f"  数据采集: 龙虎榜{results['collect'].get('dragon_tiger_count',0)}条, "
              f"板块{results['collect'].get('sector_count',0)}条, "
              f"调研{results['collect'].get('research_count',0)}条")
        print(f"  股票筛选: 候选{results['screen'].get('total_candidates',0)}只, "
              f"新增{results['screen'].get('added_to_watchlist',0)}只")
        print(f"  分析执行: 共{results['analyze'].get('total',0)}只, "
              f"成功{results['analyze'].get('success',0)}只, "
              f"失败{results['analyze'].get('failed',0)}只")
        if results['errors']:
            print(f"  错误信息: {results['errors'][:3]}")
        print("=" * 60)
        
        return results
    
    def run_price_update(self) -> Dict[str, Any]:
        """
        执行价格更新任务
        
        Returns:
            更新结果
        """
        from .watchlist_manager import WatchlistManager
        
        print("\n📈 执行价格更新")
        print("-" * 40)
        
        manager = WatchlistManager()
        results = manager.update_prices()
        
        print(f"  成功更新: {results.get('success', 0)} 只")
        print(f"  更新失败: {results.get('failed', 0)} 只")
        
        # 显示触发止损止盈的情况
        positions = manager.get_open_positions()
        if positions:
            print(f"  当前持仓: {len(positions)} 只")
            for p in positions[:5]:
                ret = p.get('current_return', 0)
                print(f"    {p.get('name')}({p.get('code')}): {p.get('current_price')} ({ret:+.2f}%)")
        
        return results
    
    def get_schedule_report(self) -> str:
        """获取调度计划报告"""
        lines = [
            "=" * 60,
            "📅 定时任务调度计划",
            "=" * 60,
            "",
        ]
        
        for task in self.tasks.values():
            status_icon = "✅" if task.enabled else "❌"
            next_run = self._calculate_next_run(task)
            
            lines.extend([
                f"{status_icon} {task.task_name}",
                f"   任务ID: {task.task_id}",
                f"   类型: {task.task_type}",
                f"   执行时间: {task.schedule_time}",
                f"   下次执行: {next_run.strftime('%Y-%m-%d %H:%M')}",
                f"   已执行次数: {task.run_count}",
                f"   最后执行: {task.last_run or '从未执行'}",
                "",
            ])
        
        lines.append("=" * 60)
        return '\n'.join(lines)
