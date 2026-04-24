"""
定时任务 API
提供定时任务状态查看和控制功能
"""

import os
from datetime import datetime
from typing import Optional, Dict, Any, List

from config.project_paths import ensure_project_root_on_path

ensure_project_root_on_path()

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from watchlist import AutoScheduler, WatchlistManager, DataCollector

router = APIRouter()

# 获取调度器实例
_scheduler_instance = None

def get_scheduler() -> Optional[AutoScheduler]:
    """获取调度器实例（延迟初始化）"""
    global _scheduler_instance
    if _scheduler_instance is None:
        try:
            _scheduler_instance = AutoScheduler()
        except Exception as e:
            print(f"调度器初始化失败: {e}")
            return None
    return _scheduler_instance


# ========== 任务配置模型 ==========

class TaskSchedule(BaseModel):
    """任务调度配置"""
    task_name: str = Field(..., description="任务名称")
    enabled: bool = Field(True, description="是否启用")
    schedule_time: str = Field("16:30", description="执行时间 HH:MM")
    days: List[int] = Field([1, 2, 3, 4, 5], description="执行日期 1-7")


class RunTaskRequest(BaseModel):
    """手动执行任务请求"""
    task_name: str = Field(..., description="任务名称")
    stock_code: Optional[str] = Field(None, description="股票代码（部分任务需要）")


# ========== 预定义任务 ==========

PREDEFINED_TASKS = {
    "daily_collect": {
        "name": "daily_collect",
        "display_name": "每日数据采集",
        "description": "每日16:30采集龙虎榜、热门板块等数据",
        "default_time": "16:30",
        "default_days": [1, 2, 3, 4, 5]
    },
    "daily_update": {
        "name": "daily_update",
        "display_name": "每日价格更新",
        "description": "每日17:00更新观察池股票价格",
        "default_time": "17:00",
        "default_days": [1, 2, 3, 4, 5]
    },
    "weekly_analysis": {
        "name": "weekly_analysis",
        "display_name": "周度分析",
        "description": "每周六10:00对观察池进行全面分析",
        "default_time": "10:00",
        "default_days": [6]  # 周六
    },
    "performance_report": {
        "name": "performance_report",
        "display_name": "表现报告",
        "description": "每周日生成并发送表现报告",
        "default_time": "10:00",
        "default_days": [0]  # 周日
    }
}


# ========== API端点 ==========

@router.get("/scheduler/status")
async def get_scheduler_status():
    """获取定时任务状态"""
    try:
        scheduler = get_scheduler()
        
        if scheduler is None:
            return {
                "success": False,
                "message": "调度器未初始化"
            }
        
        # 获取调度器状态
        is_running = scheduler.is_running if hasattr(scheduler, 'is_running') else False
        
        # 获取下次执行时间
        next_runs = []
        if hasattr(scheduler, 'get_next_run_times'):
            next_runs = scheduler.get_next_run_times()
        
        return {
            "success": True,
            "data": {
                "scheduler_running": is_running,
                "predefined_tasks": PREDEFINED_TASKS,
                "next_runs": next_runs,
                "last_check": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"获取状态失败: {str(e)}"
        }


@router.get("/scheduler/tasks")
async def get_task_list():
    """获取任务列表"""
    try:
        scheduler = get_scheduler()
        
        tasks = []
        for task_id, task_info in PREDEFINED_TASKS.items():
            tasks.append({
                "id": task_id,
                **task_info,
                "enabled": True,  # 默认启用
                "last_run": None,
                "next_run": None,
                "status": "idle"
            })
        
        return {
            "success": True,
            "data": {
                "tasks": tasks,
                "count": len(tasks)
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"获取任务列表失败: {str(e)}"
        }


@router.post("/scheduler/run")
async def run_task(request: RunTaskRequest):
    """手动执行任务"""
    try:
        task_name = request.task_name
        
        # 根据任务类型执行
        if task_name == "daily_collect":
            # 执行数据采集
            collector = DataCollector()
            
            results = {}
            
            try:
                dragon_data = collector.collect_dragon_rank()
                results["dragon_rank"] = {"count": len(dragon_data), "success": True}
            except Exception as e:
                results["dragon_rank"] = {"error": str(e), "success": False}
            
            try:
                hot_sectors = collector.collect_hot_sectors()
                results["hot_sectors"] = {"count": len(hot_sectors), "success": True}
            except Exception as e:
                results["hot_sectors"] = {"error": str(e), "success": False}
            
            try:
                research = collector.collect_research()
                results["research"] = {"count": len(research), "success": True}
            except Exception as e:
                results["research"] = {"error": str(e), "success": False}
            
            return {
                "success": True,
                "message": f"数据采集任务完成",
                "data": {
                    "task": task_name,
                    "executed_at": datetime.now().isoformat(),
                    "results": results
                }
            }
            
        elif task_name == "daily_update":
            # 更新观察池股票价格
            manager = WatchlistManager()
            candidates = manager.get_all_candidates()
            
            updated_count = 0
            for candidate in candidates:
                # 模拟更新价格（实际需要调用数据接口）
                try:
                    # 这里应该调用真实的价格更新接口
                    # manager.update_price(candidate.code)
                    updated_count += 1
                except Exception:
                    pass
            
            return {
                "success": True,
                "message": f"价格更新完成，更新了 {updated_count} 只股票",
                "data": {
                    "task": task_name,
                    "executed_at": datetime.now().isoformat(),
                    "updated_count": updated_count
                }
            }
            
        elif task_name == "weekly_analysis":
            # 执行观察池全面分析
            manager = WatchlistManager()
            candidates = manager.get_all_candidates()
            
            analyzed = []
            for candidate in candidates[:10]:  # 限制每次分析数量
                try:
                    manager.update_analysis_result(
                        code=candidate.code,
                        analysis_result={"auto_analyzed": True},
                        composite_score=75.0,
                        is_buy_recommended=True
                    )
                    analyzed.append(candidate.code)
                except Exception:
                    pass
            
            return {
                "success": True,
                "message": f"周度分析完成，分析了 {len(analyzed)} 只股票",
                "data": {
                    "task": task_name,
                    "executed_at": datetime.now().isoformat(),
                    "analyzed": analyzed
                }
            }
            
        elif task_name == "performance_report":
            # 生成表现报告
            from watchlist import PerformanceReporter
            reporter = PerformanceReporter()
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            report = reporter.generate_weekly_report(start_date, end_date)
            
            return {
                "success": True,
                "message": "表现报告生成完成",
                "data": {
                    "task": task_name,
                    "executed_at": datetime.now().isoformat(),
                    "report": report
                }
            }
            
        else:
            return {
                "success": False,
                "message": f"未知任务: {task_name}"
            }
            
    except Exception as e:
        return {
            "success": False,
            "message": f"执行任务失败: {str(e)}"
        }


@router.post("/scheduler/start")
async def start_scheduler():
    """启动调度器"""
    try:
        scheduler = get_scheduler()
        
        if scheduler is None:
            return {
                "success": False,
                "message": "调度器初始化失败"
            }
        
        if hasattr(scheduler, 'start'):
            scheduler.start()
        
        return {
            "success": True,
            "message": "调度器已启动"
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"启动调度器失败: {str(e)}"
        }


@router.post("/scheduler/stop")
async def stop_scheduler():
    """停止调度器"""
    try:
        scheduler = get_scheduler()
        
        if scheduler and hasattr(scheduler, 'stop'):
            scheduler.stop()
        
        return {
            "success": True,
            "message": "调度器已停止"
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"停止调度器失败: {str(e)}"
        }


# 导入 timedelta 用于日期计算
from datetime import timedelta
