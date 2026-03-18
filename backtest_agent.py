# 回测Agent - 历史策略回测分析
# 功能: 基于历史数据回测策略表现

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import json

DB_PATH = 'data/stocks.db'


class BacktestAgent:
    """回测Agent - 策略回测"""
    
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.results = []
    
    def get_daily_data(self, code, start_date=None, end_date=None):
        """获取历史数据"""
        conn = sqlite3.connect(self.db_path)
        
        query = "SELECT date, open, high, low, close, volume, change_pct FROM daily_data WHERE code = ?"
        params = [code]
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " ORDER BY date"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    
    def calculate_indicators(self, df):
        """计算技术指标"""
        df = df.copy()
        
        # 均线
        df['ma5'] = df['close'].rolling(5).mean()
        df['ma10'] = df['close'].rolling(10).mean()
        df['ma20'] = df['close'].rolling(20).mean()
        
        # MACD
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['dif'] = ema12 - ema26
        df['dea'] = df['dif'].ewm(span=9, adjust=False).mean()
        df['macd'] = (df['dif'] - df['dea']) * 2
        
        # 量比
        df['vol_ma5'] = df['volume'].rolling(5).mean()
        df['vol_ratio'] = df['volume'] / df['vol_ma5']
        
        return df
    
    def check_signals(self, row, prev_row):
        """检查买入信号"""
        signals = []
        score = 0
        
        # 1. 多头排列
        if row['ma5'] > row['ma10'] > row['ma20']:
            signals.append('bullish_ma')
            score += 3
        
        # 2. 资金流入
        if row['close'] > prev_row['close'] and row['volume'] > prev_row['volume']:
            signals.append('money_flow')
            score += 3
        
        # 3. MACD金叉
        if prev_row['dif'] <= prev_row['dea'] and row['dif'] > row['dea']:
            signals.append('macd_golden')
            score += 2
        
        # 4. MACD红柱
        if row['macd'] > 0:
            signals.append('macd_red')
            score += 1
        
        # 5. 量比适中
        if 1.2 <= row['vol_ratio'] <= 3.0:
            signals.append('vol_ratio')
            score += 2
        
        return signals, score
    
    def run_backtest(self, codes=None, start_date='2025-01-01', end_date='2026-03-12',
                     min_score=6, stop_loss=0.02, take_profit=0.05, hold_days=2):
        """
        运行回测
        
        参数:
        - codes: 股票列表，None表示全部
        - start_date/end_date: 回测区间
        - min_score: 最低买入评分
        - stop_loss: 止损比例
        - take_profit: 止盈比例
        - hold_days: 持有天数
        """
        print(f"🔄 回测区间: {start_date} ~ {end_date}")
        
        # 获取股票列表
        if codes is None:
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql_query(
                f"SELECT DISTINCT code FROM daily_data WHERE date >= '{start_date}'",
                conn
            )
            codes = df['code'].tolist()
            conn.close()
        
        print(f"📊 回测股票数: {len(codes)}")
        
        trades = []  # 交易记录
        wins = 0
        losses = 0
        total_return = 0
        
        for i, code in enumerate(codes):
            if (i + 1) % 200 == 0:
                print(f"   进度: {i+1}/{len(codes)}")
            
            # 获取历史数据
            df = self.get_daily_data(code, start_date, end_date)
            if len(df) < 30:
                continue
            
            df = self.calculate_indicators(df)
            
            # 逐日检查信号
            for j in range(20, len(df) - hold_days):
                row = df.iloc[j]
                prev_row = df.iloc[j-1]
                
                signals, score = self.check_signals(row, prev_row)
                
                if score >= min_score:
                    # 买入
                    buy_price = row['close']
                    buy_date = row['date']
                    
                    # 持有N天后卖出
                    sell_idx = min(j + hold_days, len(df) - 1)
                    sell_row = df.iloc[sell_idx]
                    sell_price = sell_row['close']
                    sell_date = sell_row['date']
                    
                    # 计算收益
                    ret = (sell_price - buy_price) / buy_price
                    
                    # 检查是否触发止盈止损
                    if ret >= take_profit:
                        # 止盈
                        ret = take_profit
                        exit_type = '止盈'
                    elif ret <= -stop_loss:
                        # 止损
                        ret = -stop_loss
                        exit_type = '止损'
                    else:
                        exit_type = '持有到期'
                    
                    trades.append({
                        'code': code,
                        'buy_date': buy_date,
                        'buy_price': buy_price,
                        'sell_date': sell_date,
                        'sell_price': sell_price,
                        'return': ret,
                        'exit_type': exit_type,
                        'signals': signals,
                        'score': score
                    })
                    
                    if ret > 0:
                        wins += 1
                    else:
                        losses += 1
                    total_return += ret
        
        # 统计结果
        total_trades = wins + losses
        win_rate = wins / total_trades * 100 if total_trades > 0 else 0
        avg_return = total_return / total_trades * 100 if total_trades > 0 else 0
        
        # 统计各退出类型
        exit_stats = defaultdict(int)
        for t in trades:
            exit_stats[t['exit_type']] += 1
        
        # 最佳/最差交易
        trades_sorted = sorted(trades, key=lambda x: x['return'], reverse=True)
        
        results = {
            'params': {
                'start_date': start_date,
                'end_date': end_date,
                'min_score': min_score,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'hold_days': hold_days,
            },
            'stats': {
                'total_trades': total_trades,
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate,
                'total_return': total_return * 100,
                'avg_return': avg_return,
            },
            'exit_stats': dict(exit_stats),
            'best_trades': trades_sorted[:5],
            'worst_trades': trades_sorted[-5:],
        }
        
        return results
    
    def print_results(self, results):
        """打印回测结果"""
        print("\n" + "="*60)
        print("📊 回测结果")
        print("="*60)
        
        p = results['params']
        print(f"📅 区间: {p['start_date']} ~ {p['end_date']}")
        print(f"🎯 策略: 评分≥{p['min_score']}, 止盈{p['take_profit']*100}%, 止损{p['stop_loss']*100}%, 持有{p['hold_days']}天")
        
        s = results['stats']
        print(f"\n📈 总体表现:")
        print(f"   总交易次数: {s['total_trades']}")
        print(f"   盈利次数: {s['wins']} | 亏损次数: {s['losses']}")
        print(f"   胜率: {s['win_rate']:.1f}%")
        print(f"   总收益: {s['total_return']:+.2f}%")
        print(f"   平均收益: {s['avg_return']:+.2f}%")
        
        print(f"\n📋 退出统计:")
        for exit_type, count in results['exit_stats'].items():
            pct = count / s['total_trades'] * 100
            print(f"   {exit_type}: {count}次 ({pct:.1f}%)")
        
        print(f"\n🏆 最佳5笔:")
        for t in results['best_trades']:
            print(f"   {t['code']} {t['buy_date']}: {t['return']*100:+.2f}% ({t['exit_type']})")
        
        print(f"\n⚠️ 最差5笔:")
        for t in results['worst_trades']:
            print(f"   {t['code']} {t['buy_date']}: {t['return']*100:+.2f}% ({t['exit_type']})")
        
        print("="*60)
    
    def optimize_params(self, codes=None, start_date='2025-01-01', end_date='2026-03-12'):
        """参数优化"""
        print("🔧 参数优化中...")
        
        best_result = None
        best_score = -999
        
        # 参数组合
        param_grid = []
        for min_score in [5, 6, 7, 8]:
            for hold_days in [1, 2, 3]:
                for stop_loss in [0.015, 0.02, 0.025]:
                    for take_profit in [0.03, 0.05, 0.08]:
                        param_grid.append({
                            'min_score': min_score,
                            'hold_days': hold_days,
                            'stop_loss': stop_loss,
                            'take_profit': take_profit,
                        })
        
        print(f"   共 {len(param_grid)} 种参数组合")
        
        results_list = []
        for i, params in enumerate(param_grid):
            result = self.run_backtest(
                codes=codes,
                start_date=start_date,
                end_date=end_date,
                **params
            )
            
            # 综合评分 (胜率*0.6 + 平均收益*0.4)
            score = result['stats']['win_rate'] * 0.6 + result['stats']['avg_return'] * 0.4 * 10
            result['score'] = score
            
            if score > best_score:
                best_score = score
                best_result = result
            
            if (i + 1) % 20 == 0:
                print(f"   进度: {i+1}/{len(param_grid)}, 当前最佳胜率: {best_result['stats']['win_rate']:.1f}%")
        
        print(f"\n✅ 优化完成!")
        self.print_results(best_result)
        
        return best_result


# ==================== 主程序 ====================
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='回测Agent - 策略回测')
    parser.add_argument('--start', default='2025-01-01', help='开始日期')
    parser.add_argument('--end', default='2026-03-12', help='结束日期')
    parser.add_argument('--min-score', type=int, default=6, help='最低评分')
    parser.add_argument('--hold-days', type=int, default=2, help='持有天数')
    parser.add_argument('--stop-loss', type=float, default=0.02, help='止损比例')
    parser.add_argument('--take-profit', type=float, default=0.05, help='止盈比例')
    parser.add_argument('--optimize', action='store_true', help='参数优化')
    
    args = parser.parse_args()
    
    agent = BacktestAgent()
    
    if args.optimize:
        agent.optimize_params(start_date=args.start, end_date=args.end)
    else:
        result = agent.run_backtest(
            start_date=args.start,
            end_date=args.end,
            min_score=args.min_score,
            hold_days=args.hold_days,
            stop_loss=args.stop_loss,
            take_profit=args.take_profit
        )
        agent.print_results(result)
