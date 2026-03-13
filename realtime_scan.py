#!/usr/bin/env python3
# 实时选股脚本 - 供cron调用
import requests
import sqlite3
import pandas as pd
from datetime import datetime
import json

def get_rt(code):
    if code.startswith('6'): market='sh'
    else: market='sz'
    try:
        r = requests.get(f"https://qt.gtimg.cn/q={market}{code}", timeout=2)
        if '~' in r.text:
            p = r.text.split('~')
            return {'code':code,'name':p[1],'price':float(p[3])}
    except: pass
    return None

# 获取候选股票
conn = sqlite3.connect('data/stocks.db')
df = pd.read_sql_query('''
    SELECT DISTINCT code, ma5, ma10, ma20, dif, dea, macd, vol_ratio
    FROM indicators 
    WHERE ma5 > ma10 AND ma10 > ma20 AND dif > dea AND macd > 0
    AND vol_ratio BETWEEN 1.2 AND 3.0
    LIMIT 150
''', conn)
conn.close()
codes = df.to_dict('records')

# 获取实时数据
seen = set()
results = []
for c in codes:
    code = c['code']
    if code in seen: continue
    seen.add(code)
    
    rt = get_rt(code)
    if rt and rt['price'] > 0:
        conn = sqlite3.connect('data/stocks.db')
        df = pd.read_sql_query(f"SELECT close FROM daily_data WHERE code='{code}' ORDER BY date DESC LIMIT 1", conn)
        conn.close()
        prev = df.iloc[0]['close'] if not df.empty else 0
        
        if prev > 0:
            change = (rt['price'] - prev) / prev * 100
            rt['prev'] = prev
            rt['change'] = change
            
            score = 0
            signals = []
            if c['ma5'] > c['ma10'] > c['ma20']: score += 3; signals.append('多头')
            if c['dif'] > c['dea']: score += 2; signals.append('金叉')
            if c['macd'] > 0: score += 1; signals.append('红柱')
            if 1.2 <= c['vol_ratio'] <= 3.0: score += 2; signals.append('量比')
            
            rt['score'] = score
            rt['signals'] = signals
            
            if change >= 2 and score >= 8:
                results.append(rt)

results.sort(key=lambda x: (x['score'], x['change']), reverse=True)

now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
print(f"\n📊 实时选股结果 ({now})")
print("="*85)
print(f"{'代码':<8} {'名称':<12} {'昨日':>8} {'当前':>8} {'涨幅':>10} {'评分':>6} {'信号'}")
print("-"*85)
for r in results[:10]:
    sig = ','.join(r['signals'])
    print(f"{r['code']:<8} {r['name']:<12} ¥{r['prev']:>7.2f} ¥{r['price']:>7.2f} {r['change']:>+9.1f}% {r['score']:>5} {sig}")
print("="*85)
print(f"共 {len(results)} 只符合条件")

# 保存结果
with open('data/realtime_signals.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
