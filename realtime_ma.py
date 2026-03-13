"""
实时分钟均线模块
用于盘中实时计算均线
"""
import requests
import pandas as pd
import json

def get_realtime_ma(code, scale=5, periods=[5,10,20,30]):
    """获取实时分钟均线"""
    symbol = f"sh{code}" if code.startswith('6') else f"sz{code}"
    url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale={scale}&ma=5&datalen=80"
    
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if not data: return None
        
        df = pd.DataFrame(data)
        df['close'] = df['close'].astype(float)
        
        result = {'price': float(df['close'].iloc[-1])}
        for p in periods:
            result[f'ma{p}'] = float(df['close'].tail(p).mean())
        return result
    except:
        return None


def realtime_scan(codes=None):
    """实时分钟均线扫描"""
    if codes is None:
        with open('watch_pool.json') as f:
            pool = json.load(f)
        codes = []
        for c in pool.values():
            codes.extend(c)
    
    results = []
    for code in codes[:50]:
        ma = get_realtime_ma(code)
        if ma and ma.get('price', 0) > 0:
            bullish = ma.get('ma5', 0) > ma.get('ma10', 0) > ma.get('ma20', 0)
            results.append({
                'code': code,
                'price': ma['price'],
                'ma5': ma.get('ma5', 0),
                'ma10': ma.get('ma10', 0),
                'ma20': ma.get('ma20', 0),
                'bullish': bullish
            })
    
    results.sort(key=lambda x: x['price'], reverse=True)
    return results


def run_realtime_scan():
    """运行实时扫描"""
    results = realtime_scan()
    
    print("="*60)
    print("实时分钟均线扫描")
    print("="*60)
    
    bullish = [r for r in results if r['bullish']]
    
    print(f"\n多头排列 ({len(bullish)}只):")
    for r in bullish[:10]:
        print(f"  {r['code']}: ¥{r['price']:.2f} MA5={r['ma5']:.2f} MA10={r['ma10']:.2f}")
    
    return bullish


if __name__ == '__main__':
    run_realtime_scan()
