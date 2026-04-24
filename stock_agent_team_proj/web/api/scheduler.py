"""
定时任务 API
提供定时任务状态查看和控制功能
"""

from datetime import datetime
from typing import Optional, Dict, Any, List

from config.project_paths import ensure_project_root_on_path

ensure_project_root_on_path()

from fastapi import APIRouter
from pydantic import BaseModel, Field

from watchlist import AutoScheduler

router = APIRouter()

# 获取调度器实例
_scheduler_instance = None

# Web 预定义任务 ID -> AutoScheduler 持久化任务 ID
WEB_TASK_TO_INTERNAL = {
    "daily_collect": AutoScheduler.TASK_DAILY_COLLECT,
    "daily_update": AutoScheduler.TASK_DAILY_PRICE_UPDATE,
    "weekly_analysis": AutoScheduler.TASK_WEEKLY_UPDATE,
}


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
        
        return {
            "success": True,
            "data": {
                "scheduler_running": scheduler.is_running,
                "predefined_tasks": PREDEFINED_TASKS,
                "next_runs": scheduler.get_next_run_times(),
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
        next_by_id: Dict[str, str] = {}
        if scheduler:
            for item in scheduler.get_next_run_times():
                next_by_id[item["task_id"]] = item["next_run"]
        
        tasks = []
        for task_id, task_info in PREDEFINED_TASKS.items():
            row: Dict[str, Any] = {
                "id": task_id,
                **task_info,
                "enabled": True,
                "last_run": None,
                "next_run": None,
                "status": "idle"
            }
            internal = WEB_TASK_TO_INTERNAL.get(task_id)
            if scheduler and internal and internal in scheduler.tasks:
                st = scheduler.tasks[internal]
                row["enabled"] = st.enabled
                row["last_run"] = st.last_run
                row["next_run"] = next_by_id.get(internal)
            tasks.append(row)
        
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
        scheduler = get_scheduler()
        executed_at = datetime.now().isoformat()
        
        if task_name == "daily_collect":
            if scheduler is None:
                return {"success": False, "message": "调度器未初始化"}
            counts = scheduler.run_daily_collect()
            return {
                "success": True,
                "message": "数据采集任务完成",
                "data": {
                    "task": task_name,
                    "executed_at": executed_at,
                    "results": {
                        "dragon_rank": {"count": counts["dragon_tiger_count"], "success": True},
                        "hot_sectors": {"count": counts["sector_count"], "success": True},
                        "research": {"count": counts["research_count"], "success": True},
                    },
                    "collect_summary": counts,
                }
            }
            
        elif task_name == "daily_update":
            if scheduler is None:
                return {"success": False, "message": "调度器未初始化"}
            price_result = scheduler.run_price_update()
            ok = price_result.get("success", 0)
            fail = price_result.get("failed", 0)
            return {
                "success": True,
                "message": f"价格更新完成，成功 {ok} 只，失败 {fail} 只",
                "data": {
                    "task": task_name,
                    "executed_at": executed_at,
                    **price_result,
                }
            }
            
        elif task_name == "weekly_analysis":
            if scheduler is None:
                return {"success": False, "message": "调度器未初始化"}
            pipeline = scheduler.run_full_pipeline(force=False)
            an = pipeline.get("analyze") or {}
            tot = an.get("total", 0)
            suc = an.get("success", 0)
            msg = (
                f"周度流程完成：分析成功 {suc}/{tot}"
                if tot
                else "周度流程完成：无待分析股票"
            )
            return {
                "success": True,
                "message": msg,
                "data": {
                    "task": task_name,
                    "executed_at": executed_at,
                    "pipeline": pipeline,
                }
            }
            
        elif task_name == "performance_report":
            from watchlist import PerformanceReporter
            reporter = PerformanceReporter()
            report = reporter.generate_weekly_report()
            
            return {
                "success": True,
                "message": "表现报告生成完成",
                "data": {
                    "task": task_name,
                    "executed_at": executed_at,
                    "report": report,
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
        
        if scheduler:
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
