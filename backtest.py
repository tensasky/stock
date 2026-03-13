#!/usr/bin/env python3
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

print('开始回测...')

for s in stocks:
    try:
        df = f.get_stock_data(s, days=60)
        if df is None or len(df) < 35: continue
        
        # 模拟最近30天
        for i in range(30, len(df)-2):
            w = df.iloc[:i]
            
            ma5 = w['close'].rolling(5).mean().iloc[-1]
            ma10 = w['close'].rolling(10).mean().iloc[-1]
            ma20 = w['close'].rolling(20).mean().iloc[-1]
            v = w['volume'].iloc[-1] / w['volume'].rolling(20).mean().iloc[-1]
            
            m = (w['close'] > w['close'].shift(1)) & (w['volume'] > w['volume'].shift(1))
            ms = m.rolling(2).sum().iloc[-1] >= 1
            
            score = 0
            if ma5 > ma10 > ma20: score += 3
            if ms: score += 3
            if v > 2: score += 2
            
            if v > 2 and score >= 5:
                buy = w['close'].iloc[-1]
                sell = df.iloc[i+1]['close']
                profit = (sell - buy) / buy * 100
                results.append({'s': s, 'sc': score, 'pf': profit})
    except:
        continue

# 统计
if results:
    profits = [r['pf'] for r in results]
    wins = len([p for p in profits if p > 0])
    n = len(results)
    print(f'=== 30天回测结果 ===')
    print(f'总信号: {n}')
    print(f'盈利: {wins} ({wins/n*100:.1f}%)')
    print(f'亏损: {n-wins} ({(n-wins)/n*100:.1f}%)')
    print(f'平均: {sum(profits)/n:.2f}%')
    print(f'止损-3%: {len([p for p in profits if p<=-3])} ({len([p for p in profits if p<=-3])/n*100:.1f}%)')
    print(f'止盈+3%: {len([p for p in profits if p>=3])} ({len([p for p in profits if p>=3])/n*100:.1f}%)')
    print(f'')
    print(f'=== 最佳案例 ===')
    for r in sorted(results, key=lambda x: x['pf'], reverse=True)[:10]:
        print(f'{r["s"]}: 得分{r["sc"]} 收益{r["pf"]:+.2f}%')
