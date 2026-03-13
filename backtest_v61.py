#!/usr/bin/env python3
"""
股票信号 V6.1 优化版
- 止损: -2% (原-3%)
- 止盈: +5% (原+3%)
- 选入: 量比1.5-3 + 多头+资金 (更稳健)
"""

import sys; sys.path.insert(0, '.')
from data_fetcher import DataFetcher

stocks = [
    '600188','600971','600395','601001','600225','600900','600011','601991','600050',
    '600036','601398','601988','601318','600519','000858','601012','600438',
    '300750','002594','002460','002466','688041','688111','300751',
    '600893','600879','600862','002410','002230'
]

f = DataFetcher()
results = []

print('V6.1 优化版回测...')

for s in stocks:
    try:
        df = f.get_stock_data(s, days=60)
        if df is None or len(df) < 35: continue
        
        for i in range(30, len(df)-2):
            w = df.iloc[:i]
            
            ma5 = w['close'].rolling(5).mean().iloc[-1]
            ma10 = w['close'].rolling(10).mean().iloc[-1]
            ma20 = w['close'].rolling(20).mean().iloc[-1]
            v = w['volume'].iloc[-1] / w['volume'].rolling(20).mean().iloc[-1]
            
            m = (w['close'] > w['close'].shift(1)) & (w['volume'] > w['volume'].shift(1))
            ms = m.rolling(2).sum().iloc[-1] >= 1
            
            # 评分
            score = 0
            has_ma = ma5 > ma10 > ma20
            if has_ma: score += 3
            if ms: score += 3
            if 1.5 < v < 3: score += 2  # 优化: 量比1.5-3
            
            # V6.1选入: 量比1.5-3 + 多头+资金 (更稳健)
            if 1.5 < v < 3 and has_ma and ms:
                buy = w['close'].iloc[-1]
                sell = df.iloc[i+1]['close']
                profit = (sell - buy) / buy * 100
                
                # 新的止盈止损
                stop_loss = profit <= -2
                take_profit = profit >= 5
                
                results.append({
                    's': s, 'sc': score, 'pf': profit,
                    'sl': stop_loss, 'tp': take_profit
                })
    except:
        continue

# 统计
if results:
    profits = [r['pf'] for r in results]
    wins = len([p for p in profits if p > 0])
    n = len(results)
    sl = len([r for r in results if r['sl']])
    tp = len([r for r in results if r['tp']])
    
    print(f'=== V6.1 优化版 30天回测 ===')
    print(f'总信号: {n}')
    print(f'盈利: {wins} ({wins/n*100:.1f}%)')
    print(f'亏损: {n-wins} ({(n-wins)/n*100:.1f}%)')
    print(f'平均: {sum(profits)/n:.2f}%')
    print(f'止损-2%: {sl} ({sl/n*100:.1f}%)')
    print(f'止盈+5%: {tp} ({tp/n*100:.1f}%)')
    print(f'')
    print(f'=== 最佳案例 ===')
    for r in sorted(results, key=lambda x: x['pf'], reverse=True)[:10]:
        print(f'{r["s"]}: 得分{r["sc"]} 收益{r["pf"]:+.2f}%')
