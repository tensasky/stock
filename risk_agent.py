# 风控Agent - 仓位管理/止盈止损/风险控制
# 功能: 持仓管理、止盈止损检查、风险监控

import sqlite3
import json
import pandas as pd
from datetime import datetime, timedelta
import os

DB_PATH = 'data/stocks.db'
POSITION_FILE = 'data/positions.json'


class RiskAgent:
    """风控Agent - 风险管理"""
    
    def __init__(self, db_path=DB_PATH, position_file=POSITION_FILE):
        self.db_path = db_path
        self.position_file = position_file
        self.positions = self.load_positions()
        
        # 默认风控参数
        self.params = {
            'max_position': 0.25,      # 单只股票最大仓位25%
            'max_total_position': 1.0,  # 总仓位上限100%
            'stop_loss': 0.02,          # 止损2%
            'take_profit': 0.05,        # 止盈5%
            'trailing_stop': 0.03,       # 移动止损3%
            'max_stocks': 5,             # 最多持仓5只
            'max_loss_per_day': 0.05,   # 单日最大亏损5%
        }
    
    def load_positions(self):
        """加载持仓"""
        if os.path.exists(self.position_file):
            with open(self.position_file, 'r') as f:
                return json.load(f)
        return []
    
    def save_positions(self):
        """保存持仓"""
        with open(self.position_file, 'w') as f:
            json.dump(self.positions, f, indent=2, ensure_ascii=False)
    
    def get_realtime_price(self, code):
        """获取实时价格"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(
            f"SELECT close, change_pct FROM daily_data WHERE code = '{code}' ORDER BY date DESC LIMIT 1",
            conn
        )
        conn.close()
        if not df.empty:
            return {'price': df.iloc[0]['close'], 'change_pct': df.iloc[0]['change_pct']}
        return None
    
    def check_position_risk(self, position):
        """检查单只持仓风险"""
        code = position['code']
        price = self.get_realtime_price(code)
        
        if not price:
            return None
        
        current_price = price['price']
        entry_price = position['entry_price']
        
        # 计算盈亏
        pnl_pct = (current_price - entry_price) / entry_price
        pnl_value = (current_price - entry_price) * position['shares']
        
        # 检查止损
        if pnl_pct <= -self.params['stop_loss']:
            return {
                'action': 'STOP_LOSS',
                'reason': f'触发止损 {pnl_pct*100:.2f}%',
                'pnl': pnl_value,
                'pnl_pct': pnl_pct
            }
        
        # 检查止盈
        if pnl_pct >= self.params['take_profit']:
            # 检查是否需要移动止盈
            if position.get('peak_price') and current_price > position['peak_price']:
                # 更新移动止盈点
                new_stop = (current_price - entry_price) * 0.5 + entry_price
                position['stop_price'] = new_stop
                position['peak_price'] = current_price
                return {
                    'action': 'TRAILING_STOP',
                    'reason': f'移动止盈 {pnl_pct*100:.2f}%',
                    'pnl': pnl_value,
                    'pnl_pct': pnl_pct
                }
            else:
                return {
                    'action': 'TAKE_PROFIT',
                    'reason': f'触发止盈 {pnl_pct*100:.2f}%',
                    'pnl': pnl_value,
                    'pnl_pct': pnl_pct
                }
        
        return None
    
    def check_all_positions(self):
        """检查所有持仓"""
        print(f"\n🛡️ 风控检查...")
        
        alerts = []
        
        for pos in self.positions:
            risk = self.check_position_risk(pos)
            if risk:
                alerts.append({
                    'code': pos['code'],
                    'name': pos.get('name', pos['code']),
                    **risk
                })
        
        return alerts
    
    def get_portfolio_stats(self):
        """获取组合统计"""
        total_value = 0
        total_cost = 0
        positions_info = []
        
        for pos in self.positions:
            price = self.get_realtime_price(pos['code'])
            if price:
                current_value = price['price'] * pos['shares']
                cost = pos['entry_price'] * pos['shares']
                pnl = current_value - cost
                pnl_pct = pnl / cost * 100
                
                positions_info.append({
                    'code': pos['code'],
                    'name': pos.get('name', pos['code']),
                    'shares': pos['shares'],
                    'entry_price': pos['entry_price'],
                    'current_price': price['price'],
                    'value': current_value,
                    'cost': cost,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'position_pct': 0  # 待计算
                })
                
                total_value += current_value
                total_cost += cost
        
        # 计算仓位占比
        for p in positions_info:
            p['position_pct'] = p['value'] / total_value * 100 if total_value > 0 else 0
        
        return {
            'total_value': total_value,
            'total_cost': total_cost,
            'total_pnl': total_value - total_cost,
            'total_pnl_pct': (total_value - total_cost) / total_cost * 100 if total_cost > 0 else 0,
            'positions': positions_info,
            'position_count': len(self.positions)
        }
    
    def print_portfolio(self):
        """打印持仓报告"""
        stats = self.get_portfolio_stats()
        
        print("\n" + "="*70)
        print("📊 持仓报告")
        print("="*70)
        
        print(f"\n💰 总资产: ¥{stats['total_value']:,.2f}")
        print(f"💵 成本: ¥{stats['total_cost']:,.2f}")
        print(f"📈 总盈亏: ¥{stats['total_pnl']:+,.2f} ({stats['total_pnl_pct']:+.2f}%)")
        print(f"📦 持仓数: {stats['position_count']}只")
        
        if stats['positions']:
            print(f"\n{'代码':<8} {'名称':<10} {'股数':>8} {'成本':>10} {'现价':>10} {'盈亏':>12} {'占比':>8}")
            print("-" * 70)
            
            for p in stats['positions']:
                print(f"{p['code']:<8} {p['name']:<10} {p['shares']:>8} "
                      f"¥{p['entry_price']:>9.2f} ¥{p['current_price']:>9.2f} "
                      f"¥{p['pnl']:+>11.2f} {p['position_pct']:>7.1f}%")
        
        print("="*70)
        
        return stats
    
    def can_buy(self, code, price, cash):
        """检查是否可以买入"""
        # 检查持仓数
        if len(self.positions) >= self.params['max_stocks']:
            return False, f"已达最大持仓数 {self.params['max_stocks']}"
        
        # 检查单只仓位
        position_value = cash * self.params['max_position']
        
        # 检查总仓位
        current_value = sum(
            self.get_realtime_price(p['code'])['price'] * p['shares']
            for p in self.positions
            if self.get_realtime_price(p['code'])
        )
        
        if (current_value + position_value) / (current_value + cash) > self.params['max_total_position']:
            return False, "总仓位已满"
        
        return True, f"可买入 {int(position_value / price)} 股"
    
    def add_position(self, code, name, shares, price, reason=''):
        """添加持仓"""
        position = {
            'code': code,
            'name': name,
            'shares': shares,
            'entry_price': price,
            'entry_date': datetime.now().strftime('%Y-%m-%d'),
            'entry_time': datetime.now().strftime('%H:%M:%S'),
            'reason': reason,
            'stop_price': price * (1 - self.params['stop_loss']),
            'peak_price': price,
        }
        
        self.positions.append(position)
        self.save_positions()
        
        print(f"✅ 买入 {code} {name} {shares}股 @ ¥{price}")
        return position
    
    def close_position(self, code, reason=''):
        """平仓"""
        for i, pos in enumerate(self.positions):
            if pos['code'] == code:
                price = self.get_realtime_price(code)
                if price:
                    pnl = (price['price'] - pos['entry_price']) * pos['shares']
                    print(f"✅ 卖出 {code} {pos['shares']}股 @ ¥{price['price']}, "
                          f"盈亏 ¥{pnl:+,.2f} ({pnl/pos['entry_price']/pos['shares']*100:+.2f}%)")
                
                self.positions.pop(i)
                self.save_positions()
                return True
        
        return False
    
    def close_all(self, reason=''):
        """全部平仓"""
        print(f"\n🚪 全部平仓 ({len(self.positions)}只)...")
        
        for pos in list(self.positions):
            self.close_position(pos['code'], reason)
        
        return True
    
    def get_risk_alerts(self):
        """获取风险警报"""
        alerts = []
        stats = self.get_portfolio_stats()
        
        # 检查持仓数
        if stats['position_count'] >= self.params['max_stocks']:
            alerts.append({
                'level': 'warning',
                'message': f"持仓数已达上限 {self.params['max_stocks']}"
            })
        
        # 检查总盈亏
        if stats['total_pnl_pct'] <= -self.params['max_loss_per_day'] * 100:
            alerts.append({
                'level': 'danger',
                'message': f"单日亏损超过 {self.params['max_loss_per_day']*100}%"
            })
        
        # 检查个股风险
        for p in stats['positions']:
            if p['pnl_pct'] <= -self.params['stop_loss'] * 100:
                alerts.append({
                    'level': 'danger',
                    'message': f"{p['code']} 触发止损 {p['pnl_pct']:.1f}%"
                })
            elif p['pnl_pct'] >= self.params['take_profit'] * 100:
                alerts.append({
                    'level': 'info',
                    'message': f"{p['code']} 触发止盈 {p['pnl_pct']:.1f}%"
                })
        
        return alerts


# ==================== 主程序 ====================
if __name__ == '__main__':
    import argparse
    import pandas as pd
    
    parser = argparse.ArgumentParser(description='风控Agent - 风险管理')
    parser.add_argument('action', choices=['status', 'check', 'add', 'close', 'closeall', 'canbuy', 'alerts'],
                        help='操作')
    parser.add_argument('--code', help='股票代码')
    parser.add_argument('--shares', type=int, help='股数')
    parser.add_argument('--price', type=float, help='价格')
    parser.add_argument('--name', help='股票名称')
    parser.add_argument('--reason', help='原因')
    
    args = parser.parse_args()
    
    agent = RiskAgent()
    
    if args.action == 'status':
        agent.print_portfolio()
    
    elif args.action == 'check':
        alerts = agent.check_all_positions()
        if alerts:
            print("\n⚠️ 风险警报:")
            for a in alerts:
                print(f"   {a['code']}: {a['action']} - {a['reason']}")
        else:
            print("\n✅ 无风险警报")
    
    elif args.action == 'add':
        if args.code and args.shares and args.price:
            agent.add_position(args.code, args.name or args.code, 
                             args.shares, args.price, args.reason or '')
        else:
            print("请指定 --code --shares --price --name")
    
    elif args.action == 'close':
        if args.code:
            agent.close_position(args.code, args.reason or '')
        else:
            print("请指定 --code")
    
    elif args.action == 'closeall':
        agent.close_all(args.reason or '')
    
    elif args.action == 'canbuy':
        if args.code and args.price:
            can, msg = agent.can_buy(args.code, args.price, 100000)
            print(f"{msg}")
        else:
            print("请指定 --code --price")
    
    elif args.action == 'alerts':
        alerts = agent.get_risk_alerts()
        if alerts:
            print("\n⚠️ 风险警报:")
            for a in alerts:
                print(f"   [{a['level']}] {a['message']}")
        else:
            print("\n✅ 无风险警报")
