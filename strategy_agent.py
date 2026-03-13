# 策略Agent - 从本地数据库读取指标选股
# 功能: 计算技术指标 -> 信号筛选 -> 候选股票

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

DB_PATH = 'data/stocks.db'

# 策略参数
PARAMS = {
    'min_vol_ratio': 1.2,    # 量比下限
    'max_vol_ratio': 3.0,    # 量比上限
    'stop_loss': 0.02,       # 止损2%
    'take_profit': 0.05,     # 止盈5%
    'hold_days': 2,          # 持有天数
    'min_score': 6,          # 最低评分
}


class StrategyAgent:
    """策略Agent - 本地选股"""
    
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.params = PARAMS
    
    def get_daily_data(self, code, days=60):
        """获取日线数据"""
        conn = sqlite3.connect(self.db_path)
        
        df = pd.read_sql_query(f'''
            SELECT date, open, high, low, close, volume, amount, change_pct 
            FROM daily_data 
            WHERE code = ? 
            ORDER BY date DESC
            LIMIT ?
        ''', conn, params=(code, days))
        
        conn.close()
        return df.iloc[::-1].reset_index(drop=True)  # 正序
    
    def calculate_ma(self, df):
        """计算均线"""
        df['ma5'] = df['close'].rolling(5).mean()
        df['ma10'] = df['close'].rolling(10).mean()
        df['ma20'] = df['close'].rolling(20).mean()
        df['ma60'] = df['close'].rolling(60).mean()
        return df
    
    def calculate_macd(self, df):
        """计算MACD"""
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['dif'] = ema12 - ema26
        df['dea'] = df['dif'].ewm(span=9, adjust=False).mean()
        df['macd'] = (df['dif'] - df['dea']) * 2
        return df
    
    def calculate_kdj(self, df):
        """计算KDJ"""
        low_min = df['low'].rolling(9).min()
        high_max = df['high'].rolling(9).max()
        
        rsv = (df['close'] - low_min) / (high_max - low_min) * 100
        rsv = rsv.fillna(50)
        
        df['k'] = rsv.ewm(com=2, adjust=False).mean()
        df['d'] = df['k'].ewm(com=2, adjust=False).mean()
        df['j'] = 3 * df['k'] - 2 * df['d']
        return df
    
    def calculate_rsi(self, df, periods=[6, 12, 24]):
        """计算RSI"""
        for p in periods:
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(p).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(p).mean()
            rs = gain / loss
            df[f'rsi{p}'] = 100 - (100 / (1 + rs))
        return df
    
    def calculate_vol_ratio(self, df):
        """计算量比"""
        df['vol_ma5'] = df['volume'].rolling(5).mean()
        df['vol_ratio'] = df['volume'] / df['vol_ma5']
        return df
    
    def calculate_indicators(self, code, days=60):
        """计算完整技术指标"""
        df = self.get_daily_data(code, days)
        
        if len(df) < 30:
            return None
        
        df = self.calculate_ma(df)
        df = self.calculate_macd(df)
        df = self.calculate_kdj(df)
        df = self.calculate_rsi(df)
        df = self.calculate_vol_ratio(df)
        
        return df
    
    def analyze_signals(self, code):
        """分析股票信号"""
        df = self.calculate_indicators(code)
        
        if df is None or len(df) < 20:
            return None
        
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        signals = {}
        scores = 0
        
        # 1. 多头排列: MA5 > MA10 > MA20
        if latest['ma5'] > latest['ma10'] > latest['ma20']:
            signals['bullish_ma'] = True
            scores += 3
        
        # 2. 资金流入: 价涨量升
        if latest['close'] > prev['close'] and latest['volume'] > prev['volume']:
            signals['money_flow'] = True
            scores += 3
        
        # 3. MACD金叉
        if prev['dif'] <= prev['dea'] and latest['dif'] > latest['dea']:
            signals['macd_golden'] = True
            scores += 2
        
        # 4. MACD红柱
        if latest['macd'] > 0:
            signals['macd_red'] = True
            scores += 1
        
        # 5. KDJ超卖反弹
        if latest['k'] < 20 or latest['j'] < 0:
            signals['kdj_oversold'] = True
            scores += 2
        
        # 6. RSI超卖
        if latest.get('rsi6', 50) < 35:
            signals['rsi_oversold'] = True
            scores += 2
        
        # 7. 量比适中
        vol_ratio = latest.get('vol_ratio', 1)
        if self.params['min_vol_ratio'] <= vol_ratio <= self.params['max_vol_ratio']:
            signals['vol_ratio'] = True
            scores += 2
        
        # 8. 放量突破
        if vol_ratio > 1.5 and latest['close'] > latest['ma20']:
            signals['breakout'] = True
            scores += 2
        
        # 计算涨跌幅
        change_pct = latest.get('change_pct', 0) or 0
        
        return {
            'code': code,
            'name': '',  # 需单独查询
            'price': latest['close'],
            'change_pct': change_pct,
            'signals': signals,
            'score': scores,
            'indicators': {
                'ma5': latest['ma5'],
                'ma10': latest['ma10'],
                'ma20': latest['ma20'],
                'dif': latest['dif'],
                'dea': latest['dea'],
                'macd': latest['macd'],
                'k': latest['k'],
                'd': latest['d'],
                'j': latest['j'],
                'rsi6': latest.get('rsi6', 50),
                'rsi12': latest.get('rsi12', 50),
                'vol_ratio': vol_ratio,
            }
        }
    
    def scan_watch_pool(self, watch_codes=None):
        """扫描观察池"""
        if watch_codes is None:
            # 从数据库获取所有股票
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql_query('SELECT DISTINCT code FROM daily_data', conn)
            codes = df['code'].tolist()
            conn.close()
        else:
            codes = watch_codes
        
        results = []
        
        print(f"🔍 扫描 {len(codes)} 只股票...")
        
        for i, code in enumerate(codes):
            if (i + 1) % 100 == 0:
                print(f"   进度: {i+1}/{len(codes)}")
            
            try:
                result = self.analyze_signals(code)
                if result and result['score'] >= self.params['min_score']:
                    results.append(result)
            except Exception as e:
                pass
        
        # 按评分排序
        results.sort(key=lambda x: x['score'], reverse=True)
        
        return results
    
    def scan_realtime(self, min_change=2.0, max_stocks=20):
        """快速扫描涨幅榜"""
        conn = sqlite3.connect(self.db_path)
        
        # 获取当日涨幅前N
        df = pd.read_sql_query(f'''
            SELECT code, MAX(date) as latest_date, 
                   MAX(change_pct) as change_pct,
                   MAX(close) as price
            FROM daily_data 
            WHERE change_pct >= ?
            GROUP BY code
            ORDER BY change_pct DESC
            LIMIT ?
        ''', conn, params=(min_change, max_stocks * 3))
        
        conn.close()
        
        results = []
        for _, row in df.iterrows():
            try:
                result = self.analyze_signals(row['code'])
                if result and result['score'] >= 4:
                    result['change_pct'] = row['change_pct']
                    result['price'] = row['price']
                    results.append(result)
            except:
                pass
        
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:max_stocks]
    
    def get_stock_name(self, code):
        """获取股票名称"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(
            'SELECT name FROM stocks WHERE code = ?', 
            conn, 
            params=(code,)
        )
        conn.close()
        if not df.empty:
            return df.iloc[0]['name']
        return code


# ==================== 主程序 ====================
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='策略Agent - 本地选股')
    parser.add_argument('action', choices=['scan', 'realtime', 'analyze'],
                        help='scan=全量扫描, realtime=实时涨幅扫描, analyze=分析单只')
    parser.add_argument('--code', help='股票代码')
    parser.add_argument('--min-score', type=int, default=6, help='最低评分')
    parser.add_argument('--top', type=int, default=10, help='显示前N只')
    
    args = parser.parse_args()
    
    agent = StrategyAgent()
    agent.params['min_score'] = args.min_score
    
    if args.action == 'analyze':
        if not args.code:
            print("请指定 --code")
        else:
            result = agent.analyze_signals(args.code)
            if result:
                name = agent.get_stock_name(args.code)
                print(f"\n📈 {args.code} {name}")
                print(f"   价格: ¥{result['price']:.2f}")
                print(f"   涨跌幅: {result['change_pct']:+.2f}%")
                print(f"   评分: {result['score']}分")
                print(f"   信号: {', '.join(result['signals'].keys())}")
                print(f"\n   指标:")
                ind = result['indicators']
                print(f"      MA5={ind['ma5']:.2f} MA10={ind['ma10']:.2f} MA20={ind['ma20']:.2f}")
                print(f"      DIF={ind['dif']:.3f} DEA={ind['dea']:.3f} MACD={ind['macd']:.3f}")
                print(f"      K={ind['k']:.1f} D={ind['d']:.1f} J={ind['j']:.1f}")
                print(f"      RSI6={ind['rsi6']:.1f} RSI12={ind['rsi12']:.1f}")
                print(f"      量比={ind['vol_ratio']:.2f}")
    
    elif args.action == 'scan':
        results = agent.scan_watch_pool()
        print(f"\n🏆 评分 >= {args.min_score} 的股票 (共{len(results)}只):\n")
        print(f"{'代码':<8} {'名称':<12} {'价格':>8} {'涨跌幅':>10} {'评分':>6} {'信号'}")
        print("-" * 85)
        for r in results[:args.top]:
            name = agent.get_stock_name(r['code']) or r['code']
            signals = ', '.join(r['signals'].keys())[:25]
            print(f"{r['code']:<8} {name:<12} ¥{r['price']:>7.2f} {r['change_pct']:>+9.1f}% {r['score']:>5} {signals}")
    
    elif args.action == 'realtime':
        results = agent.scan_realtime(min_change=2.0, max_stocks=args.top)
        print(f"\n⚡ 实时扫描涨幅榜 (共{len(results)}只符合条件):\n")
        print(f"{'代码':<8} {'名称':<10} {'价格':>8} {'涨跌幅':>10} {'评分':>6} {'信号'}")
        print("-" * 80)
        for r in results:
            name = agent.get_stock_name(r['code']) or r['code']
            signals = ', '.join(r['signals'].keys())[:30]
            print(f"{r['code']:<8} {name:<10} ¥{r['price']:>7.2f} {r['change_pct']:>+9.1f}% {r['score']:>5} {signals}")
