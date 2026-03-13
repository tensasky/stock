#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from data_fetcher import DataFetcher

stocks = ['600519','600036','601318','600900','600188','600971','600395','601012']
fetcher = DataFetcher()

results = []
for symbol in stocks:
    try:
        df = fetcher.get_stock_data(symbol, days=25)
        if df is None or len(df) < 20:
            continue
        
        ma5, ma10, ma20 = df['close'].rolling(5).mean().iloc[-1], df['close'].rolling(10).mean().iloc[-1], df['close'].rolling(20).mean().iloc[-1]
        price_up = df['close'] > df['close'].shift(1)
        vol_up = df['volume'] > df['volume'].shift(1)
        money_streak = (price_up & vol_up).rolling(2).sum().iloc[-1] >= 1
        
        score = 0
        signals = []
        if ma5 > ma10 > ma20:
            score += 3
            signals.append('多头')
        if money_streak:
            score += 3
            signals.append('资金')
        if df['close'].iloc[-1] > df['close'].shift(1).iloc[-1]:
            score += 1
            signals.append('阳')
        
        if score >= 4:
            results.append({'s': symbol, 'sc': score, 'p': df['close'].iloc[-1], 'si': signals})
    except:
        continue

results.sort(key=lambda x: x['sc'], reverse=True)
print('V4信号')
for r in results:
    print(f"{r['s']} {r['sc']} {r['p']:.2f} {r['si']}")
