#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票分析器 - 主程序
每日收盘前信号分析 + 模拟交易
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import DataFetcher
from indicators import TechnicalIndicators
from notifier import NotificationManager, MessageConfig, load_config

# 配置日志
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/analyzer.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class StockAnalyzer:
    """股票分析器主类"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config = load_config(config_path)
        self.data_fetcher = DataFetcher()
        self.notifier = NotificationManager(self.config)
        
        # 股票池
        self.stock_pool = self._load_stock_pool()
        
        # 信号记录
        self.signal_history = []
        
        logger.info(f"股票分析器初始化完成，监控 {len(self.stock_pool)} 只股票")
    
    def _load_stock_pool(self) -> List[str]:
        """加载股票池"""
        try:
            with open('stock_pool.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('stocks', ['600519', '000001', '300750'])
        except FileNotFoundError:
            logger.warning("stock_pool.json 不存在，使用默认股票池")
            return ['600519', '000001', '300750', '600036', '000858']
    
    def analyze_stock(self, symbol: str, lookback_days: int = 30) -> Optional[Dict]:
        """
        分析单只股票
        
        Args:
            symbol: 股票代码
            lookback_days: 回看天数
        
        Returns:
            分析结果字典
        """
        logger.info(f"分析股票: {symbol}")
        
        # 获取数据
        df = self.data_fetcher.get_stock_data(symbol, days=lookback_days + 30)
        
        if df is None or len(df) < 30:
            logger.warning(f"股票 {symbol} 数据不足")
            return None
        
        # 计算指标
        ti = TechnicalIndicators(df)
        df_with_indicators = ti.calculate_all()
        
        # 提取信号
        signals = ti.extract_signals()
        signals['symbol'] = symbol
        
        # 记录历史信号
        self.signal_history.append(signals)
        
        logger.info(f"{symbol} 分析完成，得分: {signals.get('score', 0)}")
        return signals
    
    def analyze_all(self) -> List[Dict]:
        """分析所有监控股票"""
        results = []
        
        for symbol in self.stock_pool:
            try:
                result = self.analyze_stock(symbol)
                if result:
                    results.append(result)
                # 避免请求过快
                time.sleep(1)
            except Exception as e:
                logger.error(f"分析 {symbol} 失败: {e}")
                continue
        
        return results
    
    def find_buy_signals(self, min_score: int = 2) -> List[Dict]:
        """寻找符合条件的买入信号"""
        results = self.analyze_all()
        
        # 筛选买入信号（得分 >= min_score）
        buy_signals = [
            r for r in results 
            if r.get('score', 0) >= min_score and r.get('score', 0) > 0
        ]
        
        # 按得分排序
        buy_signals.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        return buy_signals
    
    def notify_signals(self, signals: List[Dict]):
        """发送信号通知"""
        if not signals:
            logger.info("没有符合条件的信号")
            return
        
        for signal in signals:
            stock = signal.get('symbol', 'UNKNOWN')
            price = signal.get('price', 0)
            score = signal.get('score', 0)
            signal_list = signal.get('signals', [])
            
            # 信号类型汇总
            signal_types = [s['type'] for s in signal_list]
            details = "; ".join(signal_types)
            
            logger.info(f"发送信号通知: {stock} 得分 {score}")
            
            # 发送通知
            self.notifier.notify_signal(
                stock=stock,
                signal_type=details,
                price=price,
                details=details,
                score=score
            )
    
    def save_report(self, signals: List[Dict], report_type: str = "daily"):
        """保存分析报告"""
        os.makedirs('reports', exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"reports/{report_type}_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(signals, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"报告已保存: {filename}")
        
        # 同时保存CSV格式
        if signals:
            df = pd.DataFrame(signals)
            csv_file = f"reports/{report_type}_{timestamp}.csv"
            df.to_csv(csv_file, index=False, encoding='utf-8-sig')
            logger.info(f"CSV报告已保存: {csv_file}")


class TradingSimulator:
    """模拟交易系统"""
    
    def __init__(self, initial_capital: float = 100000.0):
        self.cash = initial_capital
        self.initial_capital = initial_capital
        self.positions = {}  # {symbol: {'shares': int, 'cost': float}}
        self.trade_history = []
        self.notifier = None
        
        logger.info(f"模拟交易系统初始化，资金: ¥{initial_capital:,.2f}")
    
    def set_notifier(self, notifier: NotificationManager):
        """设置通知器"""
        self.notifier = notifier
    
    def can_buy(self, price: float, position_size: float = 0.1) -> bool:
        """检查是否可以买入"""
        max_amount = self.cash * position_size
        return max_amount >= price * 100  # 至少买100股
    
    def buy(self, symbol: str, price: float, reason: str, position_size: float = 0.1) -> bool:
        """买入股票"""
        if not self.can_buy(price, position_size):
            logger.warning(f"资金不足，无法买入 {symbol}")
            return False
        
        max_amount = self.cash * position_size
        shares = int(max_amount / price / 100) * 100  # 整手
        
        if shares < 100:
            logger.warning(f"资金不足，无法买入 {symbol}")
            return False
        
        cost = shares * price
        self.cash -= cost
        
        if symbol not in self.positions:
            self.positions[symbol] = {'shares': 0, 'cost': 0}
        
        # 更新持仓
        old_shares = self.positions[symbol]['shares']
        old_cost = self.positions[symbol]['cost']
        new_shares = old_shares + shares
        new_cost = old_cost + cost
        
        self.positions[symbol] = {
            'shares': new_shares,
            'cost': new_cost,
            'avg_cost': new_cost / new_shares
        }
        
        # 记录交易
        trade = {
            'datetime': datetime.now().isoformat(),
            'action': 'BUY',
            'symbol': symbol,
            'price': price,
            'shares': shares,
            'amount': cost,
            'reason': reason,
            'cash_after': self.cash
        }
        self.trade_history.append(trade)
        
        logger.info(f"买入 {symbol} {shares}股 @ ¥{price:.2f}, 理由: {reason}")
        
        # 发送通知
        if self.notifier:
            self.notifier.notify_trade(
                stock=symbol,
                action='BUY',
                price=price,
                reason=reason,
                position_size=position_size
            )
        
        return True
    
    def sell(self, symbol: str, price: float, reason: str, ratio: float = 1.0) -> bool:
        """卖出股票"""
        if symbol not in self.positions or self.positions[symbol]['shares'] == 0:
            logger.warning(f"没有持仓 {symbol}")
            return False
        
        shares_to_sell = int(self.positions[symbol]['shares'] * ratio / 100) * 100
        if shares_to_sell < 100:
            shares_to_sell = self.positions[symbol]['shares']
        
        amount = shares_to_sell * price
        self.cash += amount
        
        # 更新持仓
        self.positions[symbol]['shares'] -= shares_to_sell
        
        if self.positions[symbol]['shares'] == 0:
            del self.positions[symbol]
        
        # 记录交易
        trade = {
            'datetime': datetime.now().isoformat(),
            'action': 'SELL',
            'symbol': symbol,
            'price': price,
            'shares': shares_to_sell,
            'amount': amount,
            'reason': reason,
            'cash_after': self.cash
        }
        self.trade_history.append(trade)
        
        logger.info(f"卖出 {symbol} {shares_to_sell}股 @ ¥{price:.2f}, 理由: {reason}")
        
        # 发送通知
        if self.notifier:
            self.notifier.notify_trade(
                stock=symbol,
                action='SELL',
                price=price,
                reason=reason,
                position_size=ratio
            )
        
        return True
    
    def get_portfolio_value(self, prices: Dict[str, float]) -> float:
        """计算组合市值"""
        position_value = 0
        for symbol, pos in self.positions.items():
            if symbol in prices:
                position_value += pos['shares'] * prices[symbol]
        
        return self.cash + position_value
    
    def get_status(self) -> Dict:
        """获取账户状态"""
        return {
            'cash': self.cash,
            'positions': self.positions,
            'total_value': None,  # 需要实时价格
            'initial_capital': self.initial_capital,
            'total_trades': len(self.trade_history)
        }
    
    def save_history(self):
        """保存交易记录"""
        os.makedirs('signals', exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d")
        filename = f"signals/trades_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'trades': self.trade_history,
                'positions': self.positions,
                'cash': self.cash
            }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"交易记录已保存: {filename}")


def run_daily_analysis():
    """运行每日分析"""
    logger.info("=" * 50)
    logger.info("开始每日股票分析")
    
    # 初始化
    analyzer = StockAnalyzer()
    simulator = TradingSimulator(initial_capital=100000)
    simulator.set_notifier(analyzer.notifier)
    
    # 分析所有股票
    signals = analyzer.find_buy_signals(min_score=2)
    
    # 发送信号通知
    analyzer.notify_signals(signals)
    
    # 保存报告
    analyzer.save_report(signals)
    
    # 输出结果
    if signals:
        logger.info(f"\n发现 {len(signals)} 只股票符合买入条件:")
        for s in signals:
            logger.info(f"  {s['symbol']}: 得分 {s['score']}, 价格 ¥{s['price']:.2f}")
            
            # 自动买入（模拟盘）
            # simulator.buy(s['symbol'], s['price'], str(s['signals']))
    else:
        logger.info("\n没有符合条件的买入信号")
    
    # 保存交易记录
    simulator.save_history()
    
    logger.info("每日分析完成")
    logger.info("=" * 50)


def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='股票分析器')
    parser.add_argument('--mode', choices=['daily', 'test'], default='daily',
                       help='运行模式')
    parser.add_argument('--config', default='config.json',
                       help='配置文件路径')
    
    args = parser.parse_args()
    
    if args.mode == 'daily':
        run_daily_analysis()
    elif args.mode == 'test':
        # 测试模式
        analyzer = StockAnalyzer(args.config)
        signals = analyzer.analyze_all()
        for s in signals:
            print(f"\n{s['symbol']}: 价格 ¥{s['price']:.2f}, 得分 {s.get('score', 0)}")
            print(f"信号: {s.get('signals', [])}")


if __name__ == "__main__":
    main()
