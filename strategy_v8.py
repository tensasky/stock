# 策略Agent V8 - 目标: 月收益5%+
# 选股策略: 强势趋势 + 资金流入 + 板块启动

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime

DB_PATH = 'data/stocks.db'

# V8策略参数
PARAMS_V8 = {
    'min_vol_ratio': 1.5,      # 量比>1.5 (更激进)
    'min_change': 3.0,          # 涨幅>3% (趋势确认)
    'stop_loss': 0.02,         # 止损2%
    'take_profit': 0.05,       # 止盈5%
    'hold_days': 3,            # 持有3天
}


def calculate_indicators(df):
    """计算技术指标"""
    df = df.copy()
    
    # 均线
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma10'] = df['close'].rolling(10).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma60'] = df['close'].rolling(60).mean()
    
    # 强势股: 股价在近期高点附近
    df['high_20'] = df['high'].rolling(20).max()
    df['near_high'] = (df['close'] / df['high_20'] - 1) * 100  # 距离20日高点的百分比
    
    # MACD
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['dif'] = ema12 - ema26
    df['dea'] = df['dif'].ewm(span=9, adjust=False).mean()
    df['macd'] = (df['dif'] - df['dea']) * 2
    
    # 成交量
    df['vol_ma5'] = df['volume'].rolling(5).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma5']
    
    # 资金流入 (价涨量升)
    df['price_up'] = df['close'] > df['close'].shift(1)
    df['vol_up'] = df['volume'] > df['volume'].shift(1)
    df['money_flow'] = (df['price_up'] & df['vol_up']).rolling(3).sum()
    
    return df


def analyze_v8(code, days=60):
    """V8策略分析"""
    conn = sqlite3.connect(DB_PATH)
    
    df = pd.read_sql_query(f'''
        SELECT date, open, high, low, close, volume, change_pct
        FROM daily_data 
        WHERE code = '{code}' 
        ORDER BY date DESC
        LIMIT {days}
    ''', conn)
    
    conn.close()
    
    if len(df) < 30:
        return None
    
    df = df.iloc[::-1].reset_index(drop=True)  # 正序
    df = calculate_indicators(df)
    
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    
    signals = []
    score = 0
    
    # 1. 涨幅>3% (趋势确认) - 新增
    change = latest.get('change_pct', 0) or 0
    if change > PARAMS_V8['min_change']:
        signals.append('涨3%+')
        score += 3
    
    # 2. 多头排列
    if latest['ma5'] > latest['ma10'] > latest['ma20']:
        signals.append('多头')
        score += 3
    
    # 3. 资金连续流入 (3日)
    if latest['money_flow'] >= 2:
        signals.append('资金流入')
        score += 3
    
    # 4. 接近20日高点 (强势股)
    if latest['near_high'] > -5:  # 距离高点不到5%
        signals.append('near_high')
        score += 2
    
    # 5. MACD金叉
    if prev['dif'] <= prev['dea'] and latest['dif'] > latest['dea']:
        signals.append('金叉')
        score += 2
    
    # 6. MACD红柱
    if latest['macd'] > 0:
        signals.append('红柱')
        score += 1
    
    # 7. 量比>1.5
    if latest['vol_ratio'] > PARAMS_V8['min_vol_ratio']:
        signals.append('放量')
        score += 2
    
    # 8. 突破60日新高
    if latest['close'] > latest['ma60']:
        signals.append('新高')
        score += 2
    
    return {
        'code': code,
        'price': latest['close'],
        'change_pct': change,
        'score': score,
        'signals': signals,
        'near_high': latest['near_high'],
    }


def scan_v8(min_score=8):
    """V8策略扫描"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT DISTINCT code FROM daily_data WHERE date >= '2025-01-01'",
        conn
    )
    codes = df['code'].tolist()
    conn.close()
    
    results = []
    print(f"🔍 V8策略扫描 {len(codes)} 只股票...")
    
    for i, code in enumerate(codes):
        if (i + 1) % 500 == 0:
            print(f"   进度: {i+1}/{len(codes)}")
        
        try:
            result = analyze_v8(code)
            if result and result['score'] >= min_score:
                results.append(result)
        except:
            pass
    
    results.sort(key=lambda x: x['score'], reverse=True)
    return results


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='V8策略扫描')
    parser.add_argument('--min-score', type=int, default=8, help='最低评分')
    parser.add_argument('--top', type=int, default=20, help='显示数量')
    
    args = parser.parse_args()
    
    results = scan_v8(min_score=args.min_score)
    
    print(f"\n🏆 V8策略信号 (评分≥{args.min_score}, 共{len(results)}只):\n")
    print(f"{'代码':<8} {'价格':>8} {'涨幅':>10} {'评分':>6} {'信号'}")
    print("-" * 70)
    
    for r in results[:args.top]:
        signals = ', '.join(r['signals'])[:30]
        print(f"{r['code']:<8} ¥{r['price']:>7.2f} {r['change_pct']:>+9.1f}% {r['score']:>5} {signals}")
