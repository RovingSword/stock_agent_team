"""
主程序入口
中短线波段 Agent Team 系统
"""
from datetime import datetime
from typing import Dict, Any, Optional

from agents.base_agent import AgentContext
from agents.leader import Leader
from agents.review_analyst import ReviewAnalyst
from protocols.message_protocol import TradeDecisionMessage
from storage.database import db
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
        
        self.logger.info("Stock Agent Team 系统初始化完成")
    
    def analyze(self, stock_code: str, stock_name: str, 
                user_request: str = "") -> TradeDecisionMessage:
        """
        分析股票
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            user_request: 用户请求描述
        
        Returns:
            交易决策消息
        """
        self.logger.info(f"开始分析: {stock_name}({stock_code})")
        
        # 创建分析上下文
        context = AgentContext(
            task_id=f"TASK_{datetime.now().strftime('%Y%m%d%H%M%S')}_{stock_code}",
            stock_code=stock_code,
            stock_name=stock_name,
            user_request=user_request
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


def main():
    """主函数"""
    print("=" * 60)
    print("中短线波段 Agent Team 系统")
    print("=" * 60)
    
    # 初始化系统
    team = StockAgentTeam()
    
    # 示例：分析宁德时代
    print("\n【示例分析】宁德时代(300750)")
    print("-" * 60)
    
    decision = team.analyze("300750", "宁德时代", "分析是否适合中短线买入")
    
    # 检查是否使用了模拟数据
    from utils.data_fetcher import data_fetcher
    is_mock = data_fetcher.is_mock_data("300750")

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
    
    # 示例：周度复盘
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
