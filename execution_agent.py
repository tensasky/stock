# 执行Agent - 交易执行/模拟下单
# 功能: 根据策略信号执行交易、记录流水

import sqlite3
import json
import pandas as pd
from datetime import datetime
import os

DB_PATH = 'data/stocks.db'
POSITION_FILE = 'data/positions.json'
TRADE_LOG_FILE = 'data/trade_log.json'


class ExecutionAgent:
    """执行Agent - 交易执行"""
    
    def __init__(self, db_path=DB_PATH, position_file=POSITION_FILE, 
                 trade_log_file=TRADE_LOG_FILE):
        self.db_path = db_path
        self.position_file = position_file
        self.trade_log_file = trade_log_file
        
        # 加载持仓
        if os.path.exists(position_file):
            with open(position_file, 'r') as f:
                self.positions = json.load(f)
        else:
            self.positions = []
        
        # 加载交易日志
        if os.path.exists(trade_log_file):
            with open(trade_log_file, 'r') as f:
                self.trade_log = json.load(f)
        else:
            self.trade_log = []
        
        # 初始资金
        self.initial_cash = 1000000  # 100万模拟资金
        self.cash = self.initial_cash
        
        # 计算当前资金
        self.update_cash()
    
    def update_cash(self):
        """更新可用资金"""
        self.cash = self.initial_cash
        for pos in self.positions:
            self.cash -= pos['entry_price'] * pos['shares']
    
    def save_positions(self):
        """保存持仓"""
        with open(self.position_file, 'w') as f:
            json.dump(self.positions, f, indent=2, ensure_ascii=False)
    
    def save_trade_log(self):
        """保存交易日志"""
        with open(self.trade_log_file, 'w') as f:
            json.dump(self.trade_log, f, indent=2, ensure_ascii=False)
    
    def get_price(self, code):
        """获取最新价格"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(
            f"SELECT close FROM daily_data WHERE code = '{code}' ORDER BY date DESC LIMIT 1",
            conn
        )
        conn.close()
        return df.iloc[0]['close'] if not df.empty else None
    
    def buy(self, code, name, shares, price=None, reason=''):
        """买入"""
        if price is None:
            price = self.get_price(code)
            if price is None:
                return False, "无法获取价格"
        
        cost = price * shares
        if cost > self.cash:
            return False, f"资金不足 (需要¥{cost:,.0f}, 可用¥{self.cash:,.0f})"
        
        # 检查是否已持仓
        for pos in self.positions:
            if pos['code'] == code:
                return False, f"已持有 {code}"
        
        # 执行买入
        position = {
            'code': code,
            'name': name,
            'shares': shares,
            'entry_price': price,
            'entry_date': datetime.now().strftime('%Y-%m-%d'),
            'entry_time': datetime.now().strftime('%H:%M:%S'),
            'reason': reason,
            'stop_loss': price * 0.98,
            'take_profit': price * 1.05,
        }
        
        self.positions.append(position)
        self.cash -= cost
        
        # 记录交易
        self.trade_log.append({
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'action': 'BUY',
            'code': code,
            'name': name,
            'shares': shares,
            'price': price,
            'amount': cost,
            'reason': reason,
            'cash_after': self.cash
        })
        
        self.save_positions()
        self.save_trade_log()
        
        return True, f"买入 {code} {name} {shares}股 @ ¥{price}, 耗资¥{cost:,.0f}, 余资¥{self.cash:,.0f}"
    
    def sell(self, code, shares=None, price=None, reason=''):
        """卖出"""
        position = None
        for pos in self.positions:
            if pos['code'] == code:
                position = pos
                break
        
        if not position:
            return False, f"未持有 {code}"
        
        if price is None:
            price = self.get_price(code)
            if price is None:
                return False, "无法获取价格"
        
        sell_shares = shares or position['shares']
        if sell_shares > position['shares']:
            sell_shares = position['shares']
        
        proceeds = price * sell_shares
        cost = position['entry_price'] * sell_shares
        pnl = proceeds - cost
        pnl_pct = pnl / cost * 100
        
        # 更新或删除持仓
        if sell_shares == position['shares']:
            self.positions.remove(position)
        else:
            position['shares'] -= sell_shares
        
        self.cash += proceeds
        
        # 记录交易
        self.trade_log.append({
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'action': 'SELL',
            'code': code,
            'name': position['name'],
            'shares': sell_shares,
            'price': price,
            'amount': proceeds,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'reason': reason,
            'cash_after': self.cash
        })
        
        self.save_positions()
        self.save_trade_log()
        
        return True, f"卖出 {code} {sell_shares}股 @ ¥{price}, 盈亏¥{pnl:+,.0f} ({pnl_pct:+.2f}%)"
    
    def get_portfolio_value(self):
        """获取组合市值"""
        total = self.cash
        for pos in self.positions:
            price = self.get_price(pos['code'])
            if price:
                total += price * pos['shares']
        return total
    
    def get_position_value(self):
        """获取持仓市值"""
        total = 0
        for pos in self.positions:
            price = self.get_price(pos['code'])
            if price:
                total += price * pos['shares']
        return total
    
    def print_portfolio(self):
        """打印持仓报告"""
        total_value = self.get_portfolio_value()
        position_value = self.get_position_value()
        
        print("\n" + "="*70)
        print("📊 模拟交易组合")
        print("="*70)
        
        print(f"\n💰 现金: ¥{self.cash:,.2f}")
        print(f"📦 持仓: ¥{position_value:,.2f}")
        print(f"📈 总资产: ¥{total_value:,.2f}")
        print(f"📊 收益率: {(total_value - self.initial_cash) / self.initial_cash * 100:+.2f}%")
        
        if self.positions:
            print(f"\n{'代码':<8} {'名称':<10} {'股数':>8} {'成本':>10} {'现价':>10} {'盈亏':>12} {'盈亏%':>10}")
            print("-" * 70)
            
            for pos in self.positions:
                price = self.get_price(pos['code'])
                if price:
                    cost = pos['entry_price'] * pos['shares']
                    value = price * pos['shares']
                    pnl = value - cost
                    pnl_pct = pnl / cost * 100
                    
                    print(f"{pos['code']:<8} {pos['name']:<10} {pos['shares']:>8} "
                          f"¥{pos['entry_price']:>9.2f} ¥{price:>9.2f} "
                          f"¥{pnl:>+11.2f} {pnl_pct:>+9.2f}%")
        
        print("="*70)
    
    def print_trade_log(self, limit=20):
        """打印交易日志"""
        print("\n" + "="*70)
        print("📜 交易记录")
        print("="*70)
        
        for log in self.trade_log[-limit:]:
            if log['action'] == 'BUY':
                print(f"{log['time']} 🟢 买入 {log['code']} {log['name']} "
                      f"{log['shares']}股 @ ¥{log['price']:.2f}")
            else:
                print(f"{log['time']} 🔴 卖出 {log['code']} {log['shares']}股 @ ¥{log['price']:.2f}, "
                      f"盈亏¥{log.get('pnl', 0):+,.0f} ({log.get('pnl_pct', 0):+.2f}%)")
        
        print("="*70)
    
    def execute_signals(self, signals):
        """执行信号"""
        results = []
        
        for signal in signals:
            code = signal['code']
            name = signal.get('name', code)
            score = signal['score']
            
            # 检查是否已持仓
            already_held = any(p['code'] == code for p in self.positions)
            if already_held:
                continue
            
            # 计算买入数量 (每只股票最多用20%资金)
            max_amount = self.initial_cash * 0.2
            price = self.get_price(code)
            if price:
                shares = int(max_amount / price / 100) * 100  # 整手
                if shares > 0:
                    success, msg = self.buy(code, name, shares, price, 
                                            f"策略评分{score}分")
                    results.append({'code': code, 'success': success, 'message': msg})
        
        return results
    
    def close_all(self, reason=''):
        """全部平仓"""
        print(f"\n🚪 全部平仓 ({len(self.positions)}只)...")
        
        for pos in list(self.positions):
            self.sell(pos['code'], reason=reason or '全部平仓')
        
        return True


# ==================== 主程序 ====================
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='执行Agent - 交易执行')
    parser.add_argument('action', choices=['status', 'buy', 'sell', 'log', 'closeall', 'execute'],
                        help='操作')
    parser.add_argument('--code', help='股票代码')
    parser.add_argument('--shares', type=int, help='股数')
    parser.add_argument('--price', type=float, help='价格')
    parser.add_argument('--name', help='股票名称')
    parser.add_argument('--reason', help='原因')
    parser.add_argument('--limit', type=int, default=20, help='显示数量')
    
    args = parser.parse_args()
    
    agent = ExecutionAgent()
    
    if args.action == 'status':
        agent.print_portfolio()
    
    elif args.action == 'buy':
        if args.code and args.shares:
            agent.buy(args.code, args.name or args.code, args.shares, args.price, args.reason or '')
        else:
            print("请指定 --code --shares --price --name")
    
    elif args.action == 'sell':
        if args.code:
            agent.sell(args.code, args.shares, args.price, args.reason or '')
        else:
            print("请指定 --code")
    
    elif args.action == 'log':
        agent.print_trade_log(limit=args.limit)
    
    elif args.action == 'closeall':
        agent.close_all(args.reason or '')
    
    elif args.action == 'execute':
        print("请通过 quant_system.py 调用")
