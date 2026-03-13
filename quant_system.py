# 多Agent量化交易系统
# 整合: 数据Agent + 策略Agent + 回测Agent + 风控Agent + 执行Agent + 报告Agent

import sys
import json
from datetime import datetime

# 导入各个Agent
from data_agent import DataAgent
from strategy_agent import StrategyAgent
from backtest_agent import BacktestAgent
from risk_agent import RiskAgent
from execution_agent import ExecutionAgent
from report_agent import ReportAgent


class QuantSystem:
    """量化交易系统 - 多Agent协调"""
    
    def __init__(self):
        self.data_agent = DataAgent()
        self.strategy_agent = StrategyAgent()
        self.backtest_agent = BacktestAgent()
        self.risk_agent = RiskAgent()
        self.execution_agent = ExecutionAgent()
        self.report_agent = ReportAgent()
        
        print("="*60)
        print("🎯 多Agent量化交易系统")
        print("="*60)
        print("1. 数据Agent    - 抓取/存储股票数据")
        print("2. 策略Agent   - 技术指标/信号筛选")
        print("3. 回测Agent   - 历史策略回测")
        print("4. 风控Agent   - 止盈止损管理")
        print("5. 执行Agent   - 模拟交易执行")
        print("6. 报告Agent   - 生成报告/邮件通知")
        print("="*60)
    
    def status(self):
        """系统状态"""
        stats = self.data_agent.get_data_stats()
        print(f"\n📊 系统状态:")
        print(f"   股票数: {stats['stock_count']}")
        print(f"   总记录: {stats['total_records']}")
        print(f"   日期范围: {stats['start_date']} ~ {stats['end_date']}")
    
    def fetch_data(self, days=250):
        """数据采集"""
        print(f"\n📥 数据采集中 (最近{days}天)...")
        self.data_agent.fetch_watch_pool(days=days)
        self.data_agent.fetch_index('000001', '上证指数', days=days)
        self.status()
    
    def scan(self, min_score=6, top=10):
        """选股扫描"""
        print(f"\n🔍 选股扫描 (评分≥{min_score})...")
        results = self.strategy_agent.scan_watch_pool()
        filtered = [r for r in results if r['score'] >= min_score]
        
        print(f"\n🏆 符合条件: {len(filtered)}只\n")
        print(f"{'代码':<8} {'名称':<12} {'价格':>8} {'涨跌幅':>10} {'评分':>6} {'信号'}")
        print("-" * 75)
        
        for r in filtered[:top]:
            name = self.strategy_agent.get_stock_name(r['code']) or r['code']
            signals = ', '.join(r['signals'].keys())[:20]
            print(f"{r['code']:<8} {name:<12} ¥{r['price']:>7.2f} {r['change_pct']:>+9.1f}% {r['score']:>5} {signals}")
        
        return filtered
    
    def analyze(self, code):
        """个股分析"""
        print(f"\n📈 个股分析: {code}")
        result = self.strategy_agent.analyze_signals(code)
        
        if result:
            name = self.strategy_agent.get_stock_name(code)
            print(f"   {code} {name}")
            print(f"   价格: ¥{result['price']:.2f}")
            print(f"   涨跌幅: {result['change_pct']:+.2f}%")
            print(f"   评分: {result['score']}分")
            print(f"   信号: {', '.join(result['signals'].keys())}")
            
            ind = result['indicators']
            print(f"\n   技术指标:")
            print(f"      MA5={ind['ma5']:.2f} MA10={ind['ma10']:.2f} MA20={ind['ma20']:.2f}")
            print(f"      DIF={ind['dif']:.3f} DEA={ind['dea']:.3f} MACD={ind['macd']:.3f}")
            print(f"      K={ind['k']:.1f} D={ind['d']:.1f} J={ind['j']:.1f}")
            print(f"      RSI6={ind['rsi6']:.1f} RSI12={ind['rsi12']:.1f}")
            print(f"      量比={ind['vol_ratio']:.2f}")
        
        return result
    
    def backtest(self, start='2025-01-01', end='2026-03-12', 
                 min_score=6, hold_days=2, stop_loss=0.02, take_profit=0.05):
        """策略回测"""
        print(f"\n🔄 策略回测...")
        result = self.backtest_agent.run_backtest(
            start_date=start, end_date=end,
            min_score=min_score, hold_days=hold_days,
            stop_loss=stop_loss, take_profit=take_profit
        )
        self.backtest_agent.print_results(result)
        return result
    
    def optimize(self, start='2025-01-01', end='2026-03-12'):
        """参数优化"""
        print(f"\n🔧 参数优化...")
        result = self.backtest_agent.optimize_params(start_date=start, end_date=end)
        return result
    
    def realtime_scan(self, min_change=2.0, top=10):
        """实时涨幅扫描"""
        print(f"\n⚡ 实时涨幅扫描 (涨幅≥{min_change}%)...")
        results = self.strategy_agent.scan_realtime(min_change=min_change, max_stocks=top)
        
        print(f"\n🏆 符合条件: {len(results)}只\n")
        print(f"{'代码':<8} {'价格':>8} {'涨跌幅':>10} {'评分':>6} {'信号'}")
        print("-" * 60)
        
        for r in results:
            signals = ', '.join(r['signals'].keys())[:25]
            print(f"{r['code']:<8} ¥{r['price']:>7.2f} {r['change_pct']:>+9.1f}% {r['score']:>5} {signals}")
        
        return results
    
    # ========== 风控 ==========
    def risk_status(self):
        """风控状态"""
        self.risk_agent.print_portfolio()
    
    def risk_check(self):
        """风控检查"""
        alerts = self.risk_agent.check_all_positions()
        if alerts:
            print("\n⚠️ 风险警报:")
            for a in alerts:
                print(f"   {a['code']}: {a['action']} - {a['reason']}")
        else:
            print("\n✅ 无需风控操作")
    
    def risk_alerts(self):
        """风险警报"""
        alerts = self.risk_agent.get_risk_alerts()
        if alerts:
            print("\n⚠️ 风险警报:")
            for a in alerts:
                print(f"   [{a['level']}] {a['message']}")
        else:
            print("\n✅ 无风险警报")
    
    # ========== 执行 ==========
    def exec_status(self):
        """执行状态"""
        self.execution_agent.print_portfolio()
    
    def exec_buy(self, code, shares, price=None, name='', reason=''):
        """买入"""
        name = name or code
        self.execution_agent.buy(code, name, shares, price, reason)
    
    def exec_sell(self, code, shares=None, price=None, reason=''):
        """卖出"""
        self.execution_agent.sell(code, shares, price, reason)
    
    def exec_closeall(self):
        """全部平仓"""
        self.execution_agent.close_all()
    
    def exec_log(self, limit=20):
        """交易日志"""
        self.execution_agent.print_trade_log(limit=limit)
    
    def exec_signals(self, min_score=6, top=5):
        """执行信号"""
        print(f"\n🎯 执行信号 (评分≥{min_score}, 最多{top}只)...")
        
        # 先扫描信号
        signals = self.strategy_agent.scan_watch_pool()
        filtered = [s for s in signals if s['score'] >= min_score][:top]
        
        if not filtered:
            print("  无符合条件信号")
            return []
        
        # 执行买入
        results = self.execution_agent.execute_signals(filtered)
        
        for r in results:
            print(f"  {r['code']}: {r['message']}")
        
        return results
    
    # ========== 报告 ==========
    def report_daily(self, send_mail=True):
        """日报"""
        self.report_agent.daily_report(send_mail=send_mail)
    
    def report_signals(self, signals, send_mail=True):
        """信号报告"""
        self.report_agent.signal_report(signals, send_mail=send_mail)


# ==================== CLI ====================
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='多Agent量化系统')
    parser.add_argument('action', 
                        choices=['status', 'fetch', 'scan', 'analyze', 'backtest', 
                                'optimize', 'realtime', 'risk', 'exec', 'report'],
                        help='操作类型')
    
    # 子命令
    parser.add_argument('--sub', help='子操作')
    
    # 通用参数
    parser.add_argument('--code', help='股票代码')
    parser.add_argument('--name', help='股票名称')
    parser.add_argument('--shares', type=int, help='股数')
    parser.add_argument('--price', type=float, help='价格')
    parser.add_argument('--reason', help='原因')
    parser.add_argument('--start', default='2025-01-01', help='开始日期')
    parser.add_argument('--end', default='2026-03-12', help='结束日期')
    parser.add_argument('--min-score', type=int, default=6, help='最低评分')
    parser.add_argument('--hold-days', type=int, default=2, help='持有天数')
    parser.add_argument('--stop-loss', type=float, default=0.02, help='止损')
    parser.add_argument('--take-profit', type=float, default=0.05, help='止盈')
    parser.add_argument('--top', type=int, default=10, help='显示数量')
    parser.add_argument('--days', type=int, default=250, help='抓取天数')
    parser.add_argument('--limit', type=int, default=20, help='显示数量')
    parser.add_argument('--send', action='store_true', help='发送邮件')
    
    args = parser.parse_args()
    
    system = QuantSystem()
    
    # 主命令分发
    if args.action == 'status':
        system.status()
    
    elif args.action == 'fetch':
        system.fetch_data(days=args.days)
    
    elif args.action == 'scan':
        system.scan(min_score=args.min_score, top=args.top)
    
    elif args.action == 'analyze':
        if not args.code:
            print("请指定 --code")
        else:
            system.analyze(args.code)
    
    elif args.action == 'backtest':
        system.backtest(
            start=args.start, end=args.end,
            min_score=args.min_score, hold_days=args.hold_days,
            stop_loss=args.stop_loss, take_profit=args.take_profit
        )
    
    elif args.action == 'optimize':
        system.optimize(start=args.start, end=args.end)
    
    elif args.action == 'realtime':
        system.realtime_scan(top=args.top)
    
    # 风控
    elif args.action == 'risk':
        sub = args.sub or 'status'
        if sub == 'status':
            system.risk_status()
        elif sub == 'check':
            system.risk_check()
        elif sub == 'alerts':
            system.risk_alerts()
    
    # 执行
    elif args.action == 'exec':
        sub = args.sub or 'status'
        if sub == 'status':
            system.exec_status()
        elif sub == 'buy':
            if args.code and args.shares:
                system.exec_buy(args.code, args.shares, args.price, args.name, args.reason or '')
            else:
                print("请指定 --code --shares")
        elif sub == 'sell':
            if args.code:
                system.exec_sell(args.code, args.shares, args.price, args.reason or '')
            else:
                print("请指定 --code")
        elif sub == 'closeall':
            system.exec_closeall()
        elif sub == 'log':
            system.exec_log(args.limit)
        elif sub == 'signals':
            system.exec_signals(min_score=args.min_score, top=args.top)
    
    # 报告
    elif args.action == 'report':
        sub = args.sub or 'daily'
        if sub == 'daily':
            system.report_daily(send_mail=args.send)
        elif sub == 'signals':
            signals = system.scan(min_score=args.min_score, top=args.top)
            system.report_signals(signals, send_mail=args.send)
