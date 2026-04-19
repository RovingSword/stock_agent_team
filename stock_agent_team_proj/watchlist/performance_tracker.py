"""
表现跟踪器
负责跟踪观察池股票的表现，计算收益率和统计数据
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import asdict

from .config import config
from .models import (
    PriceSnapshot, SignalRecord, PerformanceStats,
    PriceHistory, SignalHistory
)


class PerformanceTracker:
    """表现跟踪器"""
    
    def __init__(self):
        self.config = config
        self.data_dir = self.config.data_dir
        
        # 数据文件路径
        self.price_history_path = os.path.join(self.data_dir, 'price_history.json')
        self.signal_history_path = os.path.join(self.data_dir, 'signal_history.json')
        self.performance_stats_path = os.path.join(self.data_dir, 'performance_stats.json')
        
        # 懒加载数据
        self._price_history: Optional[PriceHistory] = None
        self._signal_history: Optional[SignalHistory] = None
        self._performance_stats: Optional[PerformanceStats] = None
        
        # 确保数据目录存在
        os.makedirs(self.data_dir, exist_ok=True)
    
    @property
    def price_history(self) -> PriceHistory:
        """懒加载价格历史"""
        if self._price_history is None:
            self._price_history = PriceHistory.load(self.price_history_path)
        return self._price_history
    
    @property
    def signal_history(self) -> SignalHistory:
        """懒加载信号历史"""
        if self._signal_history is None:
            self._signal_history = SignalHistory.load(self.signal_history_path)
        return self._signal_history
    
    @property
    def performance_stats(self) -> PerformanceStats:
        """懒加载统计数据"""
        if self._performance_stats is None:
            self._performance_stats = self._load_stats()
        return self._performance_stats
    
    def _load_stats(self) -> PerformanceStats:
        """加载统计数据"""
        if os.path.exists(self.performance_stats_path):
            try:
                with open(self.performance_stats_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return PerformanceStats.from_dict(data)
            except Exception:
                pass
        return PerformanceStats(update_time=datetime.now().isoformat())
    
    def save_all(self):
        """保存所有数据"""
        self.price_history.update_time = datetime.now().isoformat()
        self.price_history.save(self.price_history_path)
        
        self.signal_history.update_time = datetime.now().isoformat()
        self.signal_history.save(self.signal_history_path)
        
        self.performance_stats.update_time = datetime.now().isoformat()
        self._save_stats()
    
    def _save_stats(self):
        """保存统计数据"""
        with open(self.performance_stats_path, 'w', encoding='utf-8') as f:
            json.dump(self.performance_stats.to_dict(), f, ensure_ascii=False, indent=2)
    
    # ========== 信号记录 ==========
    
    def record_signal(
        self,
        code: str,
        name: str,
        signal: Dict[str, Any]
    ) -> bool:
        """
        记录分析信号
        
        Args:
            code: 股票代码
            name: 股票名称
            signal: 信号信息，包含:
                - signal_type: 信号类型 (buy/watch/avoid)
                - composite_score: 综合评分
                - entry_price: 建议入场价
                - stop_loss: 止损价
                - take_profit: 止盈价
                - position_size: 建议仓位
                - add_reason: 添加原因
                - source: 来源 (analysis/manual)
        
        Returns:
            是否记录成功
        """
        try:
            signal_date = datetime.now().strftime('%Y-%m-%d')
            
            record = SignalRecord(
                code=code,
                name=name,
                signal_date=signal_date,
                signal_type=signal.get('signal_type', 'watch'),
                composite_score=signal.get('composite_score', 0),
                entry_price=signal.get('entry_price'),
                stop_loss=signal.get('stop_loss'),
                take_profit=signal.get('take_profit'),
                position_size=signal.get('position_size'),
                add_reason=signal.get('add_reason', ''),
                source=signal.get('source', 'analysis'),
            )
            
            self.signal_history.add_signal(record)
            self.signal_history.save(self.signal_history_path)
            
            print(f"  ✅ 已记录信号: {name}({code}) - {record.signal_type}")
            return True
            
        except Exception as e:
            print(f"  ⚠️ 记录信号失败: {e}")
            return False
    
    def remove_signal(self, code: str, reason: str = '手动移除') -> bool:
        """
        移除信号（平仓）
        
        Args:
            code: 股票代码
            reason: 平仓原因
        
        Returns:
            是否成功
        """
        # 查找未平仓的信号
        for sig in self.signal_history.signals:
            if sig['code'] == code and sig.get('exit_date') is None:
                exit_date = datetime.now().strftime('%Y-%m-%d')
                
                # 计算收益率
                if sig.get('entry_price'):
                    current_price = self.get_current_price(code)
                    if current_price:
                        exit_price = current_price
                        sig['exit_price'] = exit_price
                        sig['actual_return'] = round(
                            (exit_price - sig['entry_price']) / sig['entry_price'] * 100, 2
                        )
                
                sig['exit_date'] = exit_date
                sig['exit_reason'] = reason
                
                # 计算持仓天数
                signal_date = datetime.strptime(sig['signal_date'], '%Y-%m-%d')
                exit_dt = datetime.strptime(exit_date, '%Y-%m-%d')
                sig['holding_days'] = (exit_dt - signal_date).days
                
                self.signal_history.save(self.signal_history_path)
                self.update_stats()
                
                print(f"  ✅ 已平仓: {sig['name']}({code}) 收益率:{sig.get('actual_return', 'N/A')}%")
                return True
        
        print(f"  ⚠️ 未找到未平仓信号: {code}")
        return False
    
    # ========== 价格更新 ==========
    
    def update_prices(self, codes: List[str] = None) -> Dict[str, Any]:
        """
        更新价格数据
        
        Args:
            codes: 要更新的股票代码列表，None表示更新所有观察池股票
        
        Returns:
            更新结果
        """
        today = datetime.now().strftime('%Y-%m-%d')
        results = {'success': 0, 'failed': 0, 'updates': []}
        
        if not codes:
            # 获取观察池中所有股票
            from .watchlist_manager import WatchlistManager
            manager = WatchlistManager()
            candidates = manager.get_all_candidates()
            codes = [c.code for c in candidates]
        
        for code in codes:
            try:
                price_data = self._fetch_price(code)
                if price_data:
                    snapshot = PriceSnapshot(
                        code=code,
                        date=today,
                        close_price=price_data['close'],
                        change_pct=price_data.get('change_pct', 0),
                        volume=price_data.get('volume', 0),
                        turnover=price_data.get('turnover', 0),
                    )
                    self.price_history.add_snapshot(code, snapshot)
                    results['success'] += 1
                    results['updates'].append({
                        'code': code,
                        'price': price_data['close'],
                        'change_pct': price_data.get('change_pct', 0),
                    })
                else:
                    results['failed'] += 1
            except Exception as e:
                results['failed'] += 1
                print(f"  ⚠️ 更新价格失败 {code}: {e}")
        
        # 保存价格历史
        self.price_history.save(self.price_history_path)
        
        # 检查止损止盈
        self._check_stop_loss_take_profit()
        
        return results
    
    def _fetch_price(self, code: str) -> Optional[Dict[str, Any]]:
        """获取股票价格"""
        try:
            import efinance as ef
            
            # 获取当日行情
            quote = ef.stock.get_realtime_quote(code)
            if quote is not None and len(quote) > 0:
                row = quote.iloc[0]
                return {
                    'close': float(row.get('最新价', 0)),
                    'change_pct': float(row.get('涨跌幅', 0)),
                    'volume': float(row.get('成交量', 0)),
                    'turnover': float(row.get('成交额', 0)),
                }
        except Exception:
            pass
        
        # 尝试使用akshare
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            stock = df[df['代码'] == code]
            if len(stock) > 0:
                row = stock.iloc[0]
                return {
                    'close': float(row.get('最新价', 0)),
                    'change_pct': float(row.get('涨跌幅', 0)),
                    'volume': float(row.get('成交量', 0)),
                    'turnover': float(row.get('成交额', 0)),
                }
        except Exception:
            pass
        
        return None
    
    def get_current_price(self, code: str) -> Optional[float]:
        """获取当前价格"""
        return self.price_history.get_latest_price(code)
    
    # ========== 止损止盈检查 ==========
    
    def _check_stop_loss_take_profit(self):
        """检查止损止盈"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        for sig in self.signal_history.signals:
            if sig.get('exit_date') is not None:
                continue  # 已平仓
            
            if sig['signal_type'] != 'buy':
                continue  # 只检查买入信号
            
            code = sig['code']
            current_price = self.get_current_price(code)
            
            if not current_price or not sig.get('entry_price'):
                continue
            
            entry_price = sig['entry_price']
            stop_loss = sig.get('stop_loss')
            take_profit = sig.get('take_profit')
            
            triggered = None
            
            # 检查止损
            if stop_loss and current_price <= stop_loss:
                triggered = '止损'
                sig['exit_price'] = current_price
            
            # 检查止盈
            elif take_profit and current_price >= take_profit:
                triggered = '止盈'
                sig['exit_price'] = current_price
            
            if triggered:
                sig['exit_date'] = today
                sig['exit_reason'] = triggered
                sig['actual_return'] = round(
                    (current_price - entry_price) / entry_price * 100, 2
                )
                
                # 计算持仓天数
                signal_date = datetime.strptime(sig['signal_date'], '%Y-%m-%d')
                exit_dt = datetime.strptime(today, '%Y-%m-%d')
                sig['holding_days'] = (exit_dt - signal_date).days
                
                print(f"  🚨 {sig['name']}({code}) 触发{triggered}!")
                print(f"     入场价:{entry_price} 当前价:{current_price} 收益率:{sig['actual_return']}%")
        
        self.signal_history.save(self.signal_history_path)
        self.update_stats()
    
    # ========== 表现计算 ==========
    
    def calculate_signal_performance(self, code: str, signal_date: str = None) -> Optional[Dict[str, Any]]:
        """
        计算信号表现
        
        Args:
            code: 股票代码
            signal_date: 信号日期，None表示最新的信号
        
        Returns:
            表现数据
        """
        for sig in self.signal_history.signals:
            if sig['code'] == code:
                if signal_date is None or sig['signal_date'] == signal_date:
                    return self._calculate_single_performance(sig)
        return None
    
    def _calculate_single_performance(self, sig: Dict[str, Any]) -> Dict[str, Any]:
        """计算单个信号的表现"""
        code = sig['code']
        entry_price = sig.get('entry_price')
        
        if entry_price is None:
            return {'error': '无入场价'}
        
        current_price = self.get_current_price(code)
        
        if current_price is None:
            return {'error': '无当前价格'}
        
        # 计算当前收益率
        current_return = round((current_price - entry_price) / entry_price * 100, 2)
        
        # 获取价格历史计算最大回撤
        prices = self.price_history.get_price_series(code)
        max_return, max_drawdown = self._calculate_max_drawdown(prices, entry_price)
        
        # 持仓天数
        signal_date = datetime.strptime(sig['signal_date'], '%Y-%m-%d')
        holding_days = (datetime.now() - signal_date).days
        
        result = {
            'code': code,
            'name': sig['name'],
            'signal_date': sig['signal_date'],
            'signal_type': sig['signal_type'],
            'entry_price': entry_price,
            'current_price': current_price,
            'current_return': current_return,
            'max_return': max_return,
            'max_drawdown': max_drawdown,
            'holding_days': holding_days,
            'is_closed': sig.get('exit_date') is not None,
            'exit_date': sig.get('exit_date'),
            'exit_reason': sig.get('exit_reason'),
            'actual_return': sig.get('actual_return'),
        }
        
        # 更新信号记录中的最大收益和回撤
        if not sig.get('exit_date'):
            sig['max_return'] = max_return
            sig['max_drawdown'] = max_drawdown
        
        return result
    
    def _calculate_max_drawdown(
        self,
        prices: List[float],
        entry_price: float
    ) -> Tuple[float, float]:
        """计算最大收益和最大回撤"""
        if not prices:
            return 0.0, 0.0
        
        max_return = 0.0
        max_drawdown = 0.0
        peak = entry_price
        
        for price in prices:
            if price > peak:
                peak = price
            
            ret = (price - entry_price) / entry_price * 100
            dd = (peak - price) / peak * 100
            
            max_return = max(max_return, ret)
            max_drawdown = max(max_drawdown, dd)
        
        return round(max_return, 2), round(max_drawdown, 2)
    
    # ========== 统计更新 ==========
    
    def update_stats(self):
        """更新统计数据"""
        stats = self.performance_stats
        stats.update_time = datetime.now().isoformat()
        
        signals = self.signal_history.signals
        
        # 清零重新计算
        stats.total_signals = len(signals)
        stats.buy_signals = sum(1 for s in signals if s['signal_type'] == 'buy')
        stats.watch_signals = sum(1 for s in signals if s['signal_type'] == 'watch')
        stats.avoid_signals = sum(1 for s in signals if s['signal_type'] == 'avoid')
        
        # 买入信号表现
        closed_buy = [s for s in signals if s['signal_type'] == 'buy' and s.get('exit_date')]
        stats.closed_signals = len(closed_buy)
        
        if closed_buy:
            returns = [s['actual_return'] for s in closed_buy if s.get('actual_return') is not None]
            wins = [r for r in returns if r > 0]
            losses = [r for r in returns if r <= 0]
            
            stats.buy_wins = len(wins)
            stats.buy_losses = len(losses)
            stats.win_rate = round(len(wins) / len(returns) * 100, 2) if returns else 0
            stats.avg_return = round(sum(returns) / len(returns), 2) if returns else 0
            stats.avg_win_return = round(sum(wins) / len(wins), 2) if wins else 0
            stats.avg_loss_return = round(sum(losses) / len(losses), 2) if losses else 0
            stats.total_return = round(sum(returns), 2)
        
        # 观察中股票表现
        watching_buy = [s for s in signals if s['signal_type'] == 'buy' and not s.get('exit_date')]
        stats.watching_count = len(watching_buy)
        
        if watching_buy:
            watching_returns = []
            for sig in watching_buy:
                result = self._calculate_single_performance(sig)
                if 'current_return' in result:
                    watching_returns.append(result['current_return'])
            
            if watching_returns:
                stats.avg_watching_return = round(sum(watching_returns) / len(watching_returns), 2)
        
        # avoid准确率
        avoid_signals = [s for s in signals if s['signal_type'] == 'avoid']
        if avoid_signals:
            correct = 0
            for sig in avoid_signals:
                code = sig['code']
                current_price = self.get_current_price(code)
                if current_price and sig.get('entry_price'):
                    # 如果当前价比入场价低，说明避免了损失
                    if current_price < sig['entry_price']:
                        correct += 1
            
            stats.avoid_accuracy = round(correct / len(avoid_signals) * 100, 2)
        
        self._save_stats()
        return stats
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取表现摘要"""
        self.update_stats()
        stats = self.performance_stats
        
        return {
            'update_time': stats.update_time,
            'total_signals': stats.total_signals,
            'buy_signals': stats.buy_signals,
            'watch_signals': stats.watch_signals,
            'avoid_signals': stats.avoid_signals,
            'closed_signals': stats.closed_signals,
            'win_rate': f"{stats.win_rate}%",
            'avg_return': f"{stats.avg_return}%",
            'avg_win_return': f"{stats.avg_win_return}%",
            'avg_loss_return': f"{stats.avg_loss_return}%",
            'total_return': f"{stats.total_return}%",
            'avoid_accuracy': f"{stats.avoid_accuracy}%",
            'watching_count': stats.watching_count,
            'avg_watching_return': f"{stats.avg_watching_return}%",
        }
    
    def get_open_positions(self) -> List[Dict[str, Any]]:
        """获取未平仓持仓"""
        results = []
        for sig in self.signal_history.signals:
            if sig.get('exit_date') is None and sig['signal_type'] == 'buy':
                perf = self._calculate_single_performance(sig)
                results.append(perf)
        return results
    
    def get_closed_positions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取已平仓记录"""
        closed = self.signal_history.get_closed_signals('buy')
        closed.sort(key=lambda x: x.signal_date, reverse=True)
        
        results = []
        for sig in closed[:limit]:
            results.append({
                'code': sig.code,
                'name': sig.name,
                'signal_date': sig.signal_date,
                'exit_date': sig.exit_date,
                'entry_price': sig.entry_price,
                'exit_price': sig.exit_price,
                'return': sig.actual_return,
                'exit_reason': sig.exit_reason,
                'holding_days': sig.holding_days,
            })
        return results
    
    # ========== 集成方法 ==========
    
    def record_from_analysis(
        self,
        code: str,
        name: str,
        decision: Dict[str, Any]
    ):
        """
        从分析结果记录信号
        
        Args:
            code: 股票代码
            name: 股票名称
            decision: 分析决策，包含:
                - final_action: 最终动作
                - composite_score: 综合评分
                - confidence: 置信度
                - entry_price: 入场价
                - stop_loss: 止损价
                - take_profit: 止盈价
                - position_size: 仓位
        """
        action = decision.get('final_action', '').lower()
        
        if 'buy' in action:
            signal_type = 'buy'
        elif 'avoid' in action or 'warning' in action:
            signal_type = 'avoid'
        else:
            signal_type = 'watch'
        
        signal = {
            'signal_type': signal_type,
            'composite_score': decision.get('composite_score', 0),
            'entry_price': decision.get('entry_price'),
            'stop_loss': decision.get('stop_loss'),
            'take_profit': decision.get('take_profit'),
            'position_size': decision.get('position_size'),
            'add_reason': decision.get('rationale', '')[:100],
            'source': 'analysis',
        }
        
        self.record_signal(code, name, signal)
