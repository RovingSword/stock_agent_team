"""
表现报告生成器
生成周报、月报和信号表现报告
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from .performance_tracker import PerformanceTracker


class PerformanceReporter:
    """表现报告生成器"""
    
    def __init__(self):
        self.tracker = PerformanceTracker()
    
    def generate_weekly_report(self) -> str:
        """
        生成周报
        
        Returns:
            Markdown格式报告
        """
        today = datetime.now()
        week_ago = (today - timedelta(days=7)).strftime('%Y-%m-%d')
        
        lines = [
            "=" * 70,
            "📊 股票观察池周报",
            "=" * 70,
            f"报告日期: {today.strftime('%Y-%m-%d %H:%M')}",
            f"统计周期: {week_ago} ~ {today.strftime('%Y-%m-%d')}",
            "",
        ]
        
        # 1. 本周新增信号
        lines.extend(self._get_new_signals_section(week_ago))
        lines.append("")
        
        # 2. 本周平仓记录
        lines.extend(self._get_closed_this_week_section(week_ago))
        lines.append("")
        
        # 3. 当前持仓表现
        lines.extend(self._get_open_positions_section())
        lines.append("")
        
        # 4. 累计胜率统计
        lines.extend(self._get_cumulative_stats_section())
        lines.append("")
        
        # 5. 最佳/最差表现
        lines.extend(self._get_best_worst_section())
        
        lines.extend([
            "",
            "=" * 70,
            "报告结束",
            "=" * 70,
        ])
        
        return '\n'.join(lines)
    
    def generate_monthly_report(self) -> str:
        """
        生成月报
        
        Returns:
            Markdown格式报告
        """
        today = datetime.now()
        month_ago = (today - timedelta(days=30)).strftime('%Y-%m-%d')
        
        lines = [
            "=" * 70,
            "📊 股票观察池月报",
            "=" * 70,
            f"报告日期: {today.strftime('%Y-%m-%d %H:%M')}",
            f"统计周期: {month_ago} ~ {today.strftime('%Y-%m-%d')}",
            "",
        ]
        
        # 1. 月度汇总
        lines.extend(self._get_monthly_summary_section(month_ago))
        lines.append("")
        
        # 2. 平仓统计
        lines.extend(self._get_closed_this_month_section(month_ago))
        lines.append("")
        
        # 3. 持仓分析
        lines.extend(self._get_open_positions_section())
        lines.append("")
        
        # 4. 胜率分析
        lines.extend(self._get_cumulative_stats_section())
        lines.append("")
        
        # 5. avoid信号追踪
        lines.extend(self._get_avoid_tracking_section())
        
        lines.extend([
            "",
            "=" * 70,
            "报告结束",
            "=" * 70,
        ])
        
        return '\n'.join(lines)
    
    def generate_signal_report(self, code: str = None) -> str:
        """
        生成信号表现报告
        
        Args:
            code: 股票代码，None表示全部
        
        Returns:
            Markdown格式报告
        """
        today = datetime.now()
        
        lines = [
            "=" * 70,
            "📈 信号表现详情",
            "=" * 70,
            f"生成时间: {today.strftime('%Y-%m-%d %H:%M')}",
            "",
        ]
        
        if code:
            lines.append(f"股票代码: {code}")
            lines.extend(self._get_single_stock_report(code))
        else:
            # 全部信号报告
            lines.extend(self._get_all_signals_overview())
        
        lines.extend([
            "",
            "=" * 70,
        ])
        
        return '\n'.join(lines)
    
    def export_to_markdown(self, report_type: str, filepath: str = None) -> str:
        """
        导出报告为Markdown文件
        
        Args:
            report_type: 报告类型 (weekly/monthly/signal)
            filepath: 保存路径
        
        Returns:
            报告内容
        """
        if report_type == 'weekly':
            content = self.generate_weekly_report()
        elif report_type == 'monthly':
            content = self.generate_monthly_report()
        elif report_type == 'signal':
            content = self.generate_signal_report()
        else:
            content = self.generate_weekly_report()
        
        if filepath:
            # 确保目录存在
            os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✅ 报告已保存: {filepath}")
        
        return content
    
    # ========== 报告各部分生成 ==========
    
    def _get_new_signals_section(self, since_date: str) -> List[str]:
        """本周新增信号"""
        signals = self.tracker.signal_history.signals
        new_signals = [s for s in signals if s['signal_date'] >= since_date]
        
        lines = ["【📥 本周新增信号】"]
        
        if not new_signals:
            lines.append("  本周无新增信号")
            return lines
        
        buy = [s for s in new_signals if s['signal_type'] == 'buy']
        watch = [s for s in new_signals if s['signal_type'] == 'watch']
        avoid = [s for s in new_signals if s['signal_type'] == 'avoid']
        
        if buy:
            lines.append(f"  🔥 买入信号 ({len(buy)}):")
            for s in buy:
                lines.append(f"    • {s['name']}({s['code']}) {s['signal_date']} 评分:{s['composite_score']:.1f}")
        
        if watch:
            lines.append(f"  👀 观察信号 ({len(watch)}):")
            for s in watch:
                lines.append(f"    • {s['name']}({s['code']}) {s['signal_date']} 评分:{s['composite_score']:.1f}")
        
        if avoid:
            lines.append(f"  ⚠️ 回避信号 ({len(avoid)}):")
            for s in avoid:
                lines.append(f"    • {s['name']}({s['code']}) {s['signal_date']} 评分:{s['composite_score']:.1f}")
        
        return lines
    
    def _get_closed_this_week_section(self, since_date: str) -> List[str]:
        """本周平仓记录"""
        closed = self.tracker.signal_history.get_closed_signals('buy')
        week_closed = [s for s in closed if s.exit_date and s.exit_date >= since_date]
        
        lines = ["【🔚 本周平仓记录】"]
        
        if not week_closed:
            lines.append("  本周无平仓记录")
            return lines
        
        for s in week_closed:
            ret = s.actual_return
            emoji = "✅" if ret and ret > 0 else "❌"
            lines.append(
                f"  {emoji} {s.name}({s.code}) "
                f"{s.signal_date}→{s.exit_date} "
                f"收益率:{ret:.2f}% 原因:{s.exit_reason or '手动'} "
                f"持仓:{s.holding_days}天"
            )
        
        # 汇总
        returns = [s.actual_return for s in week_closed if s.actual_return is not None]
        if returns:
            total = sum(returns)
            wins = sum(1 for r in returns if r > 0)
            lines.append(f"  📊 汇总: 平仓{len(returns)}笔 胜率{wins/len(returns)*100:.1f}% 合计收益:{total:.2f}%")
        
        return lines
    
    def _get_closed_this_month_section(self, since_date: str) -> List[str]:
        """本月平仓统计"""
        closed = self.tracker.signal_history.get_closed_signals('buy')
        month_closed = [s for s in closed if s.exit_date and s.exit_date >= since_date]
        
        lines = ["【📊 本月平仓统计】"]
        lines.append(f"  本月共平仓 {len(month_closed)} 笔")
        
        if month_closed:
            returns = [s.actual_return for s in month_closed if s.actual_return is not None]
            if returns:
                wins = [r for r in returns if r > 0]
                losses = [r for r in returns if r <= 0]
                
                lines.append(f"  盈利: {len(wins)} 笔 ({(len(wins)/len(returns)*100):.1f}%)")
                lines.append(f"  亏损: {len(losses)} 笔 ({(len(losses)/len(returns)*100):.1f}%)")
                lines.append(f"  胜率: {(len(wins)/len(returns)*100):.1f}%")
                lines.append(f"  平均收益: {sum(returns)/len(returns):.2f}%")
                lines.append(f"  合计收益: {sum(returns):.2f}%")
                if wins:
                    lines.append(f"  平均盈利: {sum(wins)/len(wins):.2f}%")
                if losses:
                    lines.append(f"  平均亏损: {sum(losses)/len(losses):.2f}%")
        
        return lines
    
    def _get_monthly_summary_section(self, since_date: str) -> List[str]:
        """月度汇总"""
        signals = self.tracker.signal_history.signals
        month_signals = [s for s in signals if s['signal_date'] >= since_date]
        
        lines = ["【📋 月度汇总】"]
        lines.append(f"  本月新增信号: {len(month_signals)} 笔")
        
        buy = [s for s in month_signals if s['signal_type'] == 'buy']
        watch = [s for s in month_signals if s['signal_type'] == 'watch']
        avoid = [s for s in month_signals if s['signal_type'] == 'avoid']
        
        lines.append(f"    买入: {len(buy)} 观察: {len(watch)} 回避: {len(avoid)}")
        
        return lines
    
    def _get_open_positions_section(self) -> List[str]:
        """当前持仓表现"""
        positions = self.tracker.get_open_positions()
        
        lines = ["【💼 当前持仓】"]
        
        if not positions:
            lines.append("  暂无持仓")
            return lines
        
        lines.append(f"  共 {len(positions)} 只股票:")
        lines.append("  " + "-" * 60)
        lines.append(f"  {'代码':<10} {'名称':<12} {'入场价':>8} {'现价':>8} {'收益率':>8} {'最大收益':>8} {'持仓':>4}")
        lines.append("  " + "-" * 60)
        
        for p in positions:
            ret = p.get('current_return', 0)
            max_ret = p.get('max_return', 0)
            emoji = "📈" if ret > 0 else "📉" if ret < 0 else "➖"
            
            lines.append(
                f"  {emoji} {p.get('code', ''):<8} {p.get('name', ''):<10} "
                f"{p.get('entry_price', 0):>8.2f} {p.get('current_price', 0):>8.2f} "
                f"{ret:>7.2f}% {max_ret:>7.2f}% {p.get('holding_days', 0):>4}天"
            )
        
        # 汇总
        returns = [p.get('current_return', 0) for p in positions if p.get('current_return') is not None]
        if returns:
            lines.append("  " + "-" * 60)
            lines.append(f"  持仓汇总: 平均收益 {sum(returns)/len(returns):.2f}% 合计 {sum(returns):.2f}%")
        
        return lines
    
    def _get_cumulative_stats_section(self) -> List[str]:
        """累计胜率统计"""
        summary = self.tracker.get_performance_summary()
        
        lines = ["【📈 累计胜率统计】"]
        lines.extend([
            f"  总信号数: {summary['total_signals']}",
            f"    买入: {summary['buy_signals']} 观察: {summary['watch_signals']} 回避: {summary['avoid_signals']}",
            "",
            f"  已平仓: {summary['closed_signals']} 笔",
            f"  胜率: {summary['win_rate']}",
            f"  平均收益: {summary['avg_return']}",
            f"  平均盈利: {summary['avg_win_return']}",
            f"  平均亏损: {summary['avg_loss_return']}",
            f"  累计收益: {summary['total_return']}",
        ])
        
        return lines
    
    def _get_best_worst_section(self) -> List[str]:
        """最佳/最差表现"""
        closed = self.tracker.get_closed_positions(limit=50)
        
        lines = ["【🏆 最佳/最差表现】"]
        
        if not closed:
            lines.append("  暂无平仓记录")
            return lines
        
        sorted_by_return = sorted(closed, key=lambda x: x.get('return', 0), reverse=True)
        
        # 最佳
        if sorted_by_return:
            best = sorted_by_return[0]
            lines.append(f"  🥇 最佳: {best['name']}({best['code']}) 收益率:{best['return']:.2f}%")
        
        # 最差
        if len(sorted_by_return) > 1:
            worst = sorted_by_return[-1]
            lines.append(f"  🥉 最差: {worst['name']}({worst['code']}) 收益率:{worst['return']:.2f}%")
        
        # Top3 盈利
        wins = [x for x in sorted_by_return if x.get('return', 0) > 0][:3]
        if wins:
            lines.append("  📈 Top3 盈利:")
            for i, w in enumerate(wins, 1):
                lines.append(f"    {i}. {w['name']}({w['code']}) {w['return']:.2f}%")
        
        # Top3 亏损
        losses = [x for x in sorted_by_return if x.get('return', 0) <= 0][:3]
        if losses:
            lines.append("  📉 Top3 亏损:")
            for i, l in enumerate(losses, 1):
                lines.append(f"    {i}. {l['name']}({l['code']}) {l['return']:.2f}%")
        
        return lines
    
    def _get_avoid_tracking_section(self) -> List[str]:
        """回避信号追踪"""
        avoid_signals = self.tracker.signal_history.get_closed_signals('avoid')
        
        lines = ["【⚠️ 回避信号追踪】"]
        lines.append(f"  回避信号总数: {len(avoid_signals)}")
        
        if avoid_signals:
            lines.append("  最近回避记录:")
            for s in avoid_signals[-5:]:
                lines.append(f"    • {s.name}({s.code}) {s.signal_date}")
        
        summary = self.tracker.get_performance_summary()
        lines.append(f"  回避准确率: {summary['avoid_accuracy']}")
        
        return lines
    
    def _get_all_signals_overview(self) -> List[str]:
        """全部信号概览"""
        summary = self.tracker.get_performance_summary()
        
        lines = ["【📊 信号概览】"]
        lines.extend([
            f"  总信号: {summary['total_signals']}",
            f"  买入信号: {summary['buy_signals']}",
            f"  观察信号: {summary['watch_signals']}",
            f"  回避信号: {summary['avoid_signals']}",
        ])
        
        lines.append("")
        lines.append("【🔚 已平仓信号】")
        closed = self.tracker.get_closed_positions(limit=20)
        if closed:
            lines.append(f"  共 {len(closed)} 笔 (显示最近20笔)")
            for s in closed:
                ret = s.get('return', 0)
                emoji = "✅" if ret > 0 else "❌"
                lines.append(
                    f"  {emoji} {s['name']}({s['code']}) "
                    f"入场:{s['entry_price']}→出场:{s['exit_price']} "
                    f"{ret:.2f}% {s.get('exit_reason', '')}"
                )
        else:
            lines.append("  暂无")
        
        lines.append("")
        lines.append("【💼 未平仓信号】")
        open_pos = self.tracker.get_open_positions()
        if open_pos:
            for p in open_pos:
                ret = p.get('current_return', 0)
                emoji = "📈" if ret > 0 else "📉" if ret < 0 else "➖"
                lines.append(
                    f"  {emoji} {p['name']}({p['code']}) "
                    f"入场:{p['entry_price']} 现价:{p['current_price']} "
                    f"{ret:.2f}% 持仓:{p['holding_days']}天"
                )
        else:
            lines.append("  暂无")
        
        return lines
    
    def _get_single_stock_report(self, code: str) -> List[str]:
        """单个股票报告"""
        lines = []
        
        # 获取该股票的所有信号
        signals = [s for s in self.tracker.signal_history.signals if s['code'] == code]
        
        if not signals:
            lines.append("  未找到该股票的相关信号")
            return lines
        
        for sig in signals:
            lines.append("")
            lines.append(f"信号日期: {sig['signal_date']}")
            lines.append(f"信号类型: {sig['signal_type']}")
            lines.append(f"综合评分: {sig['composite_score']:.1f}")
            
            if sig.get('entry_price'):
                lines.append(f"入场价: {sig['entry_price']}")
            if sig.get('stop_loss'):
                lines.append(f"止损价: {sig['stop_loss']}")
            if sig.get('take_profit'):
                lines.append(f"止盈价: {sig['take_profit']}")
            
            if sig.get('exit_date'):
                lines.append(f"平仓日期: {sig['exit_date']}")
                lines.append(f"平仓原因: {sig.get('exit_reason', 'N/A')}")
                if sig.get('exit_price'):
                    lines.append(f"出场价: {sig['exit_price']}")
                if sig.get('actual_return') is not None:
                    lines.append(f"实际收益率: {sig['actual_return']:.2f}%")
                if sig.get('holding_days'):
                    lines.append(f"持仓天数: {sig['holding_days']}天")
            else:
                # 未平仓，计算当前表现
                perf = self.tracker._calculate_single_performance(sig)
                if 'current_return' in perf:
                    lines.append(f"当前价: {perf['current_price']}")
                    lines.append(f"当前收益率: {perf['current_return']:.2f}%")
                    lines.append(f"最大收益: {perf['max_return']:.2f}%")
                    lines.append(f"最大回撤: {perf['max_drawdown']:.2f}%")
                    lines.append(f"持仓天数: {perf['holding_days']}天")
        
        return lines
    
    # ========== 快捷方法 ==========
    
    def quick_stats(self) -> str:
        """快速统计（单行显示）"""
        summary = self.tracker.get_performance_summary()
        positions = self.tracker.get_open_positions()
        
        pos_returns = [p.get('current_return', 0) for p in positions if p.get('current_return') is not None]
        avg_pos = sum(pos_returns) / len(pos_returns) if pos_returns else 0
        
        return (
            f"胜率:{summary['win_rate']} | "
            f"已平仓:{summary['closed_signals']}笔 | "
            f"持仓均收益:{avg_pos:.2f}% | "
            f"在仓:{len(positions)}只"
        )
