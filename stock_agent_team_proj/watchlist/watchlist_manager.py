"""
观察池管理器
负责观察池的增删改查操作
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from .config import config
from .models import StockCandidate, WatchlistData, CandidateStatus
from .performance_tracker import PerformanceTracker
from .performance_reporter import PerformanceReporter


class WatchlistManager:
    """观察池管理器"""
    
    def __init__(self):
        self.config = config
        self.data_path = self.config.get_watchlist_path()
        self._data: Optional[WatchlistData] = None
    
    @property
    def data(self) -> WatchlistData:
        """懒加载观察池数据"""
        if self._data is None:
            self._data = WatchlistData.load(self.data_path)
        return self._data
    
    def reload(self):
        """重新加载数据"""
        self._data = WatchlistData.load(self.data_path)
    
    def save(self):
        """保存数据"""
        self.data.update_time = datetime.now().isoformat()
        self.data.update_stats()
        self.data.save(self.data_path)
    
    # ========== 基础操作 ==========
    
    def add_candidate(self, candidate: StockCandidate) -> bool:
        """
        添加候选股票
        
        Args:
            candidate: 候选股票
        
        Returns:
            是否添加成功
        """
        # 检查是否已存在
        existing = self.get_candidate(candidate.code)
        if existing:
            print(f"  ⚠️ {candidate.name}({candidate.code}) 已在观察池中")
            # 更新现有记录
            self.update_candidate(candidate.code, candidate.__dict__)
            return False
        
        # 检查容量
        if len(self.data.candidates) >= self.config.max_watchlist_size:
            print(f"  ⚠️ 观察池已满({self.config.max_watchlist_size}只)，请先移除部分股票")
            return False
        
        # 添加
        self.data.candidates.append(candidate)
        self.save()
        print(f"  ✅ 已添加 {candidate.name}({candidate.code}) 到观察池")
        return True
    
    def add_candidates_batch(self, candidates: List[StockCandidate]) -> int:
        """
        批量添加候选股票
        
        Args:
            candidates: 候选股票列表
        
        Returns:
            成功添加的数量
        """
        count = 0
        for candidate in candidates:
            if self.add_candidate(candidate):
                count += 1
        return count
    
    def remove_candidate(self, code: str, reason: str = '') -> bool:
        """
        移除候选股票
        
        Args:
            code: 股票代码
            reason: 移除原因
        
        Returns:
            是否移除成功
        """
        candidate = self.get_candidate(code)
        if not candidate:
            print(f"  ⚠️ {code} 不在观察池中")
            return False
        
        # 从列表中移除
        self.data.candidates = [c for c in self.data.candidates if c.code != code]
        
        # 添加到已移除列表
        candidate.status = 'removed'
        candidate.add_reason = f'{candidate.add_reason} | 移除原因:{reason}'
        self.data.removed.append(candidate)
        
        self.save()
        print(f"  ✅ 已移除 {candidate.name}({candidate.code})")
        return True
    
    def update_candidate(self, code: str, updates: Dict[str, Any]) -> bool:
        """
        更新候选股票信息
        
        Args:
            code: 股票代码
            updates: 要更新的字段
        
        Returns:
            是否更新成功
        """
        candidate = self.get_candidate(code)
        if not candidate:
            return False
        
        for key, value in updates.items():
            if hasattr(candidate, key):
                setattr(candidate, key, value)
        
        self.save()
        return True
    
    def get_candidate(self, code: str) -> Optional[StockCandidate]:
        """获取候选股票"""
        for candidate in self.data.candidates:
            if candidate.code == code:
                return candidate
        return None
    
    def get_all_candidates(self, status: Optional[str] = None) -> List[StockCandidate]:
        """
        获取所有候选股票
        
        Args:
            status: 按状态过滤
        
        Returns:
            候选股票列表
        """
        if status:
            return [c for c in self.data.candidates if c.status == status]
        return self.data.candidates.copy()
    
    def get_removed_candidates(self) -> List[StockCandidate]:
        """获取已移除的股票"""
        return self.data.removed.copy()
    
    # ========== 状态管理 ==========
    
    def change_status(self, code: str, new_status: str) -> bool:
        """
        更改股票状态
        
        Args:
            code: 股票代码
            new_status: 新状态
        """
        if new_status not in self.config.candidate_statuses:
            print(f"  ⚠️ 无效状态: {new_status}")
            return False
        
        candidate = self.get_candidate(code)
        if not candidate:
            return False
        
        old_status = candidate.status
        candidate.status = new_status
        self.save()
        
        print(f"  ✅ {candidate.name}({code}): {old_status} -> {new_status}")
        return True
    
    def archive_expired(self, days: int = 30) -> int:
        """
        归档过期股票（长期未分析）
        
        Args:
            days: 超过多少天未分析则归档
        
        Returns:
            归档数量
        """
        now = datetime.now()
        archived = 0
        
        for candidate in self.data.candidates:
            if candidate.last_analysis_date:
                try:
                    last_date = datetime.fromisoformat(candidate.last_analysis_date)
                    if (now - last_date).days > days:
                        candidate.status = 'archived'
                        archived += 1
                except Exception:
                    pass
        
        if archived > 0:
            self.save()
            print(f"  ✅ 已归档 {archived} 只过期股票")
        
        return archived
    
    # ========== 分析结果管理 ==========
    
    def update_analysis_result(
        self,
        code: str,
        analysis_result: Dict[str, Any],
        composite_score: float,
        is_buy_recommended: bool
    ) -> bool:
        """
        更新分析结果
        
        Args:
            code: 股票代码
            analysis_result: 分析结果
            composite_score: 综合评分
            is_buy_recommended: 是否推荐买入
        
        Returns:
            是否更新成功
        """
        candidate = self.get_candidate(code)
        if not candidate:
            return False
        
        candidate.analysis_result = analysis_result
        candidate.composite_score = composite_score
        candidate.is_buy_recommended = is_buy_recommended
        candidate.last_analysis_date = datetime.now().isoformat()
        candidate.status = 'watching'  # 分析后进入观察状态
        
        self.save()
        return True
    
    # ========== 查询功能 ==========
    
    def get_pending_candidates(self) -> List[StockCandidate]:
        """获取待处理的候选股票"""
        return self.get_all_candidates(status='pending')
    
    def get_watching_candidates(self) -> List[StockCandidate]:
        """获取正在观察的股票"""
        return self.get_all_candidates(status='watching')
    
    def get_buy_recommended(self) -> List[StockCandidate]:
        """获取推荐买入的股票"""
        return [
            c for c in self.data.candidates
            if c.is_buy_recommended is True
        ]
    
    def search(self, keyword: str) -> List[StockCandidate]:
        """
        搜索股票
        
        Args:
            keyword: 搜索关键词（代码或名称）
        
        Returns:
            匹配的股票列表
        """
        keyword = keyword.lower()
        results = []
        
        for candidate in self.data.candidates:
            if (keyword in candidate.code.lower() or 
                keyword in candidate.name.lower()):
                results.append(candidate)
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        self.data.update_stats()
        
        return {
            'total': len(self.data.candidates),
            'by_status': self.data.stats,
            'buy_recommended': len(self.get_buy_recommended()),
            'last_update': self.data.update_time,
        }
    
    # ========== 导出功能 ==========
    
    def export_report(self, filepath: str = None, include_removed: bool = False) -> str:
        """
        导出观察池报告
        
        Args:
            filepath: 保存路径（可选）
            include_removed: 是否包含已移除股票
        
        Returns:
            报告文本
        """
        lines = [
            "=" * 70,
            "📋 股票观察池报告",
            "=" * 70,
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"更新时间: {self.data.update_time}",
            "",
        ]
        
        # 统计信息
        stats = self.get_statistics()
        lines.extend([
            "【统计概览】",
            f"  股票总数: {stats['total']}",
            f"  推荐买入: {stats['buy_recommended']}",
            f"  待处理: {stats['by_status'].get('pending', 0)}",
            f"  观察中: {stats['by_status'].get('watching', 0)}",
            f"  已归档: {stats['by_status'].get('archived', 0)}",
            "",
        ])
        
        # 推荐买入列表
        buy_list = self.get_buy_recommended()
        if buy_list:
            lines.extend([
                "-" * 70,
                "【🔥 推荐买入】",
                "-" * 70,
            ])
            for i, c in enumerate(buy_list, 1):
                lines.append(
                    f"  {i}. {c.name}({c.code}) "
                    f"综合评分:{c.composite_score:.1f} "
                    f"| {c.add_reason}"
                )
        
        # 观察中列表
        watching = self.get_watching_candidates()
        if watching:
            lines.extend([
                "",
                "-" * 70,
                "【👀 观察中】",
                "-" * 70,
            ])
            for i, c in enumerate(watching, 1):
                score_str = f"{c.composite_score:.1f}" if c.composite_score else "N/A"
                lines.append(
                    f"  {i}. {c.name}({c.code}) "
                    f"评分:{score_str} | {c.add_reason}"
                )
        
        # 待处理列表
        pending = self.get_pending_candidates()
        if pending:
            lines.extend([
                "",
                "-" * 70,
                "【⏳ 待处理】",
                "-" * 70,
            ])
            for i, c in enumerate(pending, 1):
                lines.append(
                    f"  {i}. {c.name}({c.code}) "
                    f"来源评分:{c.source_score:.1f} | {c.add_reason}"
                )
        
        # 已移除列表
        if include_removed and self.data.removed:
            lines.extend([
                "",
                "-" * 70,
                "【📁 已移除】",
                "-" * 70,
            ])
            for i, c in enumerate(self.data.removed[-10:], 1):  # 只显示最近10只
                lines.append(f"  {i}. {c.name}({c.code}) | {c.add_reason}")
        
        lines.extend([
            "",
            "=" * 70,
            "报告结束",
            "=" * 70,
        ])
        
        report = '\n'.join(lines)
        
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"  ✅ 报告已保存到: {filepath}")
        
        return report
    
    def export_json(self, filepath: str = None) -> str:
        """
        导出JSON格式数据
        
        Args:
            filepath: 保存路径（可选）
        
        Returns:
            JSON字符串
        """
        data = self.data.to_dict()
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(json_str)
            print(f"  ✅ 数据已导出到: {filepath}")
        
        return json_str
    
    def import_candidates(self, candidates: List[StockCandidate], mode: str = 'add') -> int:
        """
        导入候选股票
        
        Args:
            candidates: 候选股票列表
            mode: 导入模式 - 'add'(追加) 或 'replace'(替换)
        
        Returns:
            导入数量
        """
        if mode == 'replace':
            self.data.candidates = []
        
        return self.add_candidates_batch(candidates)
    
    def clear(self, confirm: bool = False) -> bool:
        """
        清空观察池
        
        Args:
            confirm: 是否确认
        
        Returns:
            是否成功
        """
        if not confirm:
            print("  ⚠️ 请确认清空操作: clear(confirm=True)")
            return False
        
        self.data.candidates = []
        self.save()
        print("  ✅ 观察池已清空")
        return True
    
    # ========== 表现跟踪集成方法 ==========
    
    @property
    def tracker(self) -> 'PerformanceTracker':
        """获取表现跟踪器"""
        if not hasattr(self, '_tracker'):
            self._tracker = PerformanceTracker()
        return self._tracker
    
    @property
    def reporter(self) -> 'PerformanceReporter':
        """获取表现报告生成器"""
        if not hasattr(self, '_reporter'):
            self._reporter = PerformanceReporter()
        return self._reporter
    
    def record_signal_from_analysis(
        self,
        code: str,
        name: str,
        decision: Dict[str, Any]
    ) -> bool:
        """
        从分析结果记录信号
        
        Args:
            code: 股票代码
            name: 股票名称
            decision: 分析决策
        
        Returns:
            是否记录成功
        """
        return self.tracker.record_from_analysis(code, name, decision)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取表现统计数据"""
        return self.tracker.get_performance_summary()
    
    def get_open_positions(self) -> List[Dict[str, Any]]:
        """获取未平仓持仓"""
        return self.tracker.get_open_positions()
    
    def get_closed_positions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取已平仓记录"""
        return self.tracker.get_closed_positions(limit)
    
    def update_prices(self) -> Dict[str, Any]:
        """更新观察池股票价格"""
        candidates = self.get_all_candidates()
        codes = [c.code for c in candidates]
        return self.tracker.update_prices(codes)
    
    def show_performance_summary(self):
        """显示表现摘要"""
        summary = self.get_performance_stats()
        positions = self.get_open_positions()
        
        print("\n" + "=" * 60)
        print("📈 表现跟踪摘要")
        print("=" * 60)
        print(f"  总信号: {summary['total_signals']}")
        print(f"  买入: {summary['buy_signals']} 观察: {summary['watch_signals']} 回避: {summary['avoid_signals']}")
        print(f"  已平仓: {summary['closed_signals']}笔")
        print(f"  胜率: {summary['win_rate']} | 平均收益: {summary['avg_return']}")
        print(f"  回避准确率: {summary['avoid_accuracy']}")
        print("-" * 60)
        print(f"  当前持仓: {len(positions)}只")
        
        if positions:
            returns = [p.get('current_return', 0) for p in positions if p.get('current_return') is not None]
            if returns:
                print(f"  持仓均收益: {sum(returns)/len(returns):.2f}%")
        
        print("=" * 60)
    
    def show_performance_report(self, report_type: str = 'weekly'):
        """显示表现报告"""
        if report_type == 'weekly':
            print(self.reporter.generate_weekly_report())
        elif report_type == 'monthly':
            print(self.reporter.generate_monthly_report())
        else:
            print(self.reporter.generate_signal_report())
    
    def export_performance_report(
        self,
        report_type: str = 'weekly',
        filepath: str = None
    ) -> str:
        """导出表现报告"""
        if filepath is None:
            today = datetime.now().strftime('%Y%m%d')
            filename = f"performance_{report_type}_{today}.md"
            filepath = os.path.join(self.config.data_dir, 'reports', filename)
        
        return self.reporter.export_to_markdown(report_type, filepath)
    
    def close_position(self, code: str, reason: str = '手动平仓') -> bool:
        """
        平仓指定股票
        
        Args:
            code: 股票代码
            reason: 平仓原因
        
        Returns:
            是否成功
        """
        return self.tracker.remove_signal(code, reason)
