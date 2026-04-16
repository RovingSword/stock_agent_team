"""
数据库操作模块
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Dict, Any, List

from config import DATABASE_PATH


class Database:
    """数据库操作类"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DATABASE_PATH
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """确保数据库存在且表结构已初始化"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # 检查数据库是否已存在且包含表结构
        if os.path.exists(self.db_path):
            # 文件存在但可能是空数据库，需要检查是否有表
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r[0] for r in cursor.fetchall()]
                conn.close()
                if tables:
                    return  # 数据库已有表结构，无需重新初始化
            except Exception:
                pass  # 数据库损坏，重新初始化
        
        # 读取并执行schema
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        if os.path.exists(schema_path):
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            with self.get_connection() as conn:
                conn.executescript(schema_sql)
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    # ============================================================
    # 交易相关操作
    # ============================================================
    
    def create_trade(self, trade_data: Dict[str, Any]) -> str:
        """创建交易记录"""
        trade_id = f"T_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{trade_data['stock_code']}"
        
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO trades (
                    trade_id, stock_code, stock_name, market,
                    buy_date, buy_price, buy_position, buy_reason, buy_score, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade_id,
                trade_data['stock_code'],
                trade_data['stock_name'],
                trade_data.get('market', 'SZ'),
                trade_data['buy_date'],
                trade_data['buy_price'],
                trade_data['buy_position'],
                trade_data.get('buy_reason', ''),
                trade_data.get('buy_score', 0),
                'holding'
            ))
        
        return trade_id
    
    def update_trade(self, trade_id: str, update_data: Dict[str, Any]) -> bool:
        """更新交易记录"""
        fields = []
        values = []
        
        for key, value in update_data.items():
            if key in ['sell_date', 'sell_price', 'sell_reason', 'holding_days', 
                       'return_rate', 'profit_amount', 'max_profit', 'max_loss',
                       'sell_score', 'status']:
                fields.append(f"{key} = ?")
                values.append(value)
        
        if not fields:
            return False
        
        values.append(trade_id)
        
        with self.get_connection() as conn:
            conn.execute(f'''
                UPDATE trades SET {', '.join(fields)}, updated_at = ?
                WHERE trade_id = ?
            ''', values + [datetime.now().isoformat()])
        
        return True
    
    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """获取交易记录"""
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM trades WHERE trade_id = ?', (trade_id,)).fetchone()
            return dict(row) if row else None
    
    def get_active_trades(self) -> List[Dict[str, Any]]:
        """获取所有活跃交易"""
        with self.get_connection() as conn:
            rows = conn.execute('SELECT * FROM trades WHERE status = "holding"').fetchall()
            return [dict(row) for row in rows]
    
    def get_trades_by_period(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """获取指定时间段的交易"""
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM trades 
                WHERE buy_date >= ? AND buy_date <= ?
                ORDER BY buy_date DESC
            ''', (start_date, end_date)).fetchall()
            return [dict(row) for row in rows]
    
    # ============================================================
    # Agent评分相关操作
    # ============================================================
    
    def save_agent_scores(self, score_data: Dict[str, Any]) -> int:
        """保存Agent评分"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO agent_scores (
                    trade_id,
                    technical_score, technical_weight, technical_accuracy, technical_comment,
                    intelligence_score, intelligence_weight, intelligence_accuracy, intelligence_comment,
                    risk_score, risk_weight, risk_accuracy, risk_comment,
                    fundamental_score, fundamental_weight, fundamental_accuracy, fundamental_comment,
                    composite_score, overall_accuracy
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                score_data['trade_id'],
                score_data.get('technical_score'), score_data.get('technical_weight'),
                score_data.get('technical_accuracy'), score_data.get('technical_comment'),
                score_data.get('intelligence_score'), score_data.get('intelligence_weight'),
                score_data.get('intelligence_accuracy'), score_data.get('intelligence_comment'),
                score_data.get('risk_score'), score_data.get('risk_weight'),
                score_data.get('risk_accuracy'), score_data.get('risk_comment'),
                score_data.get('fundamental_score'), score_data.get('fundamental_weight'),
                score_data.get('fundamental_accuracy'), score_data.get('fundamental_comment'),
                score_data.get('composite_score'), score_data.get('overall_accuracy')
            ))
            return cursor.lastrowid
    
    def get_agent_scores(self, trade_id: str) -> Optional[Dict[str, Any]]:
        """获取交易的Agent评分"""
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM agent_scores WHERE trade_id = ?', (trade_id,)).fetchone()
            return dict(row) if row else None
    
    # ============================================================
    # 权重相关操作
    # ============================================================
    
    def get_current_weights(self) -> Dict[str, float]:
        """获取当前生效的权重"""
        with self.get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM agent_weights 
                WHERE effective_date <= ? 
                ORDER BY effective_date DESC LIMIT 1
            ''', (datetime.now().strftime('%Y-%m-%d'),)).fetchone()
            
            if row:
                return {
                    'technical': row['technical_weight'],
                    'intelligence': row['intelligence_weight'],
                    'risk': row['risk_weight'],
                    'fundamental': row['fundamental_weight'],
                }
            return {
                'technical': 0.35,
                'intelligence': 0.30,
                'risk': 0.20,
                'fundamental': 0.15,
            }
    
    def save_weights(self, weights: Dict[str, float], reason: str, effective_date: str = None):
        """保存新的权重配置"""
        effective_date = effective_date or datetime.now().strftime('%Y-%m-%d')
        
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO agent_weights (
                    effective_date,
                    technical_weight, intelligence_weight, risk_weight, fundamental_weight,
                    reason
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                effective_date,
                weights['technical'],
                weights['intelligence'],
                weights['risk'],
                weights['fundamental'],
                reason
            ))
    
    # ============================================================
    # 准确率统计相关操作
    # ============================================================
    
    def calculate_accuracy_stats(self, period_type: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """计算准确率统计"""
        with self.get_connection() as conn:
            # 获取时间段内的所有已关闭交易评分
            rows = conn.execute('''
                SELECT as.* FROM agent_scores as
                JOIN trades t ON as.trade_id = t.trade_id
                WHERE t.status = 'closed' 
                AND t.sell_date >= ? AND t.sell_date <= ?
            ''', (start_date, end_date)).fetchall()
            
            stats = {
                'technical': {'total': 0, 'accurate': 0, 'partial': 0, 'inaccurate': 0},
                'intelligence': {'total': 0, 'accurate': 0, 'partial': 0, 'inaccurate': 0},
                'risk': {'total': 0, 'accurate': 0, 'partial': 0, 'inaccurate': 0},
                'fundamental': {'total': 0, 'accurate': 0, 'partial': 0, 'inaccurate': 0},
            }
            
            for row in rows:
                for agent in ['technical', 'intelligence', 'risk', 'fundamental']:
                    accuracy = row.get(f'{agent}_accuracy')
                    if accuracy:
                        stats[agent]['total'] += 1
                        stats[agent][accuracy] += 1
            
            # 计算准确率
            for agent in stats:
                total = stats[agent]['total']
                if total > 0:
                    stats[agent]['rate'] = (stats[agent]['accurate'] + 0.5 * stats[agent]['partial']) / total
                else:
                    stats[agent]['rate'] = 0
            
            return stats
    
    def save_accuracy_stats(self, stats_data: Dict[str, Any]):
        """保存准确率统计"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO agent_accuracy_stats (
                    period_type, period_start, period_end,
                    technical_total, technical_accurate, technical_partial, technical_inaccurate, technical_accuracy_rate,
                    intelligence_total, intelligence_accurate, intelligence_partial, intelligence_inaccurate, intelligence_accuracy_rate,
                    risk_total, risk_accurate, risk_partial, risk_inaccurate, risk_accuracy_rate,
                    fundamental_total, fundamental_accurate, fundamental_partial, fundamental_inaccurate, fundamental_accuracy_rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                stats_data['period_type'], stats_data['period_start'], stats_data['period_end'],
                stats_data['technical']['total'], stats_data['technical']['accurate'],
                stats_data['technical']['partial'], stats_data['technical']['inaccurate'],
                stats_data['technical'].get('rate', 0),
                stats_data['intelligence']['total'], stats_data['intelligence']['accurate'],
                stats_data['intelligence']['partial'], stats_data['intelligence']['inaccurate'],
                stats_data['intelligence'].get('rate', 0),
                stats_data['risk']['total'], stats_data['risk']['accurate'],
                stats_data['risk']['partial'], stats_data['risk']['inaccurate'],
                stats_data['risk'].get('rate', 0),
                stats_data['fundamental']['total'], stats_data['fundamental']['accurate'],
                stats_data['fundamental']['partial'], stats_data['fundamental']['inaccurate'],
                stats_data['fundamental'].get('rate', 0),
            ))
    
    # ============================================================
    # 报告相关操作
    # ============================================================
    
    def save_report(self, report_data: Dict[str, Any]) -> str:
        """保存报告"""
        report_id = f"R_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{report_data['agent_type']}"
        
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO analysis_reports (
                    report_id, trade_id, stock_code, stock_name,
                    agent_type, report_type, report_date, content, file_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                report_id,
                report_data.get('trade_id'),
                report_data['stock_code'],
                report_data.get('stock_name'),
                report_data['agent_type'],
                report_data['report_type'],
                datetime.now().strftime('%Y-%m-%d'),
                json.dumps(report_data.get('content', {}), ensure_ascii=False),
                report_data.get('file_path')
            ))
        
        return report_id
    
    def get_reports(self, stock_code: str = None, agent_type: str = None, 
                    start_date: str = None, end_date: str = None) -> List[Dict[str, Any]]:
        """获取报告列表"""
        conditions = []
        params = []
        
        if stock_code:
            conditions.append('stock_code = ?')
            params.append(stock_code)
        if agent_type:
            conditions.append('agent_type = ?')
            params.append(agent_type)
        if start_date:
            conditions.append('report_date >= ?')
            params.append(start_date)
        if end_date:
            conditions.append('report_date <= ?')
            params.append(end_date)
        
        where_clause = ' AND '.join(conditions) if conditions else '1=1'
        
        with self.get_connection() as conn:
            rows = conn.execute(f'''
                SELECT * FROM analysis_reports WHERE {where_clause}
                ORDER BY created_at DESC
            ''', params).fetchall()
            return [dict(row) for row in rows]
    
    # ============================================================
    # 持仓相关操作
    # ============================================================
    
    def create_holding(self, holding_data: Dict[str, Any]) -> int:
        """创建持仓记录"""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO holdings (
                    trade_id, stock_code, stock_name,
                    cost_price, position, shares,
                    stop_loss_price, take_profit_1, take_profit_2, take_profit_3,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                holding_data['trade_id'],
                holding_data['stock_code'],
                holding_data['stock_name'],
                holding_data['cost_price'],
                holding_data['position'],
                holding_data.get('shares', 0),
                holding_data.get('stop_loss_price'),
                holding_data.get('take_profit_1'),
                holding_data.get('take_profit_2'),
                holding_data.get('take_profit_3'),
                'holding'
            ))
            return cursor.lastrowid
    
    def update_holding(self, holding_id: int, update_data: Dict[str, Any]):
        """更新持仓"""
        fields = []
        values = []
        
        for key in ['current_price', 'current_profit', 'current_profit_rate', 
                     'days_held', 'status']:
            if key in update_data:
                fields.append(f"{key} = ?")
                values.append(update_data[key])
        
        if fields:
            values.extend([datetime.now().isoformat(), holding_id])
            with self.get_connection() as conn:
                conn.execute(f'''
                    UPDATE holdings SET {', '.join(fields)}, last_updated = ?
                    WHERE holding_id = ?
                ''', values)
    
    def get_active_holdings(self) -> List[Dict[str, Any]]:
        """获取所有活跃持仓"""
        with self.get_connection() as conn:
            rows = conn.execute('SELECT * FROM holdings WHERE status = "holding"').fetchall()
            return [dict(row) for row in rows]
    
    # ============================================================
    # 系统配置相关操作
    # ============================================================
    
    def get_config(self, key: str) -> Optional[str]:
        """获取配置"""
        with self.get_connection() as conn:
            row = conn.execute('SELECT config_value FROM system_config WHERE config_key = ?', (key,)).fetchone()
            return row['config_value'] if row else None
    
    def set_config(self, key: str, value: str, config_type: str = 'string', description: str = ''):
        """设置配置"""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO system_config (config_key, config_value, config_type, description, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (key, value, config_type, description, datetime.now().isoformat()))
    
    # ============================================================
    # 统计相关操作
    # ============================================================
    
    def get_trade_statistics(self, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """获取交易统计"""
        where_clause = "status = 'closed'"
        params = []
        
        if start_date:
            where_clause += " AND sell_date >= ?"
            params.append(start_date)
        if end_date:
            where_clause += " AND sell_date <= ?"
            params.append(end_date)
        
        with self.get_connection() as conn:
            row = conn.execute(f'''
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN return_rate > 0 THEN 1 ELSE 0 END) as win_trades,
                    SUM(CASE WHEN return_rate <= 0 THEN 1 ELSE 0 END) as loss_trades,
                    ROUND(AVG(CASE WHEN return_rate > 0 THEN 1 ELSE 0 END) * 100, 2) as win_rate,
                    ROUND(SUM(return_rate), 4) as total_return,
                    ROUND(AVG(return_rate), 4) as avg_return,
                    MIN(return_rate) as max_loss,
                    MAX(return_rate) as max_profit
                FROM trades
                WHERE {where_clause}
            ''', params).fetchone()
            
            return dict(row) if row else {}


# 全局数据库实例
db = Database()
