# 实时数据Agent - 交易时段实时数据获取
# 功能: 获取实时价格、实时选股

import requests
import sqlite3
import pandas as pd
from datetime import datetime
import time

DB_PATH = 'data/stocks.db'


def get_realtime_price_tencent(code):
    """腾讯实时行情"""
    if code.startswith('6'):
        market = 'sh'
    else:
        market = 'sz'
    
    url = f"https://qt.gtimg.cn/q={market}{code}"
    try:
        resp = requests.get(url, timeout=3)
        data = resp.text
        
        if '~' in data:
            parts = data.split('~')
            return {
                'code': code,
                'name': parts[1],
                'price': float(parts[3]) if parts[3] else 0,
                'prev_close': float(parts[4]) if parts[4] else 0,
                'open': float(parts[5]) if parts[5] else 0,
                'high': float(parts[6]) if parts[6] else 0,
                'low': float(parts[7]) if parts[7] else 0,
                'volume': float(parts[8]) if parts[8] else 0,
                'amount': float(parts[9]) if parts[9] else 0,
                'time': parts[30] if len(parts) > 30 else '',
            }
    except:
        pass
    return None


def get_realtime_batch(codes):
    """批量获取实时行情"""
    results = []
    for code in codes:
        rt = get_realtime_price_tencent(code)
        if rt:
            results.append(rt)
        time.sleep(0.1)  # 避免请求过快
    return results


def get_realtime_for_watchpool():
    """获取观察池实时数据"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT DISTINCT code FROM daily_data", conn)
    conn.close()
    codes = df['code'].tolist()
    return get_realtime_batch(codes)


class RealtimeAgent:
    """实时数据Agent"""
    
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
    
    def get_prev_close(self, code):
        """获取昨日收盘价"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query(
            f"SELECT close FROM daily_data WHERE code='{code}' ORDER BY date DESC LIMIT 1",
            conn
        )
        conn.close()
        return df.iloc[0]['close'] if not df.empty else 0
    
    def scan_realtime(self, min_change=2.0, min_score=8, top=20):
        """实时选股扫描"""
        print(f"\n⚡ 实时选股扫描...")
        
        # 获取实时数据
        print("   获取实时数据...")
        rt_data = get_realtime_for_watchpool()
        
        if not rt_data:
            print("   ❌ 无法获取实时数据")
            return []
        
        print(f"   获取到 {len(rt_data)} 只实时数据")
        
        # 连接数据库获取技术指标
        conn = sqlite3.connect(self.db_path)
        
        results = []
        
        for rt in rt_data:
            code = rt['code']
            
            # 获取昨日收盘和涨跌幅
            prev_close = self.get_prev_close(code)
            if prev_close > 0:
                change_pct = (rt['price'] - prev_close) / prev_close * 100
            else:
                change_pct = 0
            
            # 过滤涨幅
            if change_pct < min_change:
                continue
            
            # 获取技术指标
            df = pd.read_sql_query(f'''
                SELECT ma5, ma10, ma20, dif, dea, macd, k, d, j, rsi6, rsi12, vol_ratio
                FROM indicators WHERE code='{code}' ORDER BY date DESC LIMIT 1
            ''', conn)
            
            if df.empty:
                continue
            
            ind = df.iloc[0]
            
            # 计算评分
            score = 0
            signals = []
            
            # 多头排列
            if ind['ma5'] > ind['ma10'] > ind['ma20']:
                score += 3
                signals.append('bullish_ma')
            
            # MACD金叉
            if ind['dif'] > ind['dea']:
                score += 2
                signals.append('macd_golden')
            
            # MACD红柱
            if ind['macd'] > 0:
                score += 1
                signals.append('macd_red')
            
            # 量比
            vol_ratio = ind['vol_ratio'] if pd.notna(ind['vol_ratio']) else 1
            if 1.2 <= vol_ratio <= 3.0:
                score += 2
                signals.append('vol_ratio')
            
            # 过滤评分
            if score < min_score:
                continue
            
            results.append({
                'code': code,
                'name': rt['name'],
                'price': rt['price'],
                'prev_close': prev_close,
                'change_pct': change_pct,
                'score': score,
                'signals': signals,
                'indicators': {
                    'ma5': ind['ma5'],
                    'ma10': ind['ma10'],
                    'ma20': ind['ma20'],
                    'vol_ratio': vol_ratio,
                }
            })
        
        conn.close()
        
        # 按评分排序
        results.sort(key=lambda x: x['score'], reverse=True)
        
        return results[:top]
    
    def print_realtime_results(self, results):
        """打印实时选股结果"""
        if not results:
            print("   无符合条件的股票")
            return
        
        now = datetime.now().strftime('%H:%M:%S')
        print(f"\n📊 实时选股结果 ({now})")
        print("="*85)
        print(f"{'代码':<8} {'名称':<12} {'昨日收盘':>10} {'当前价格':>10} {'实时涨幅':>10} {'评分':>6} {'信号'}")
        print("-"*85)
        
        for r in results:
            signals = ', '.join(r['signals'])[:20]
            print(f"{r['code']:<8} {r['name']:<12} ¥{r['prev_close']:>9.2f} ¥{r['price']:>9.2f} "
                  f"{r['change_pct']:>+9.1f}% {r['score']:>5} {signals}")
        
        print("="*85)
        
        return results


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='实时选股')
    parser.add_argument('--min-score', type=int, default=8, help='最低评分')
    parser.add_argument('--min-change', type=float, default=2.0, help='最低涨幅%')
    parser.add_argument('--top', type=int, default=20, help='显示数量')
    
    args = parser.parse_args()
    
    agent = RealtimeAgent()
    results = agent.scan_realtime(min_change=args.min_change, min_score=args.min_score, top=args.top)
    agent.print_realtime_results(results)
