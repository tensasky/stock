# 实时价格获取器 - 多数据源 + 容错

import requests
import time
from datetime import datetime
import json

# 缓存
PRICE_CACHE = {}
CACHE_TIMEOUT = 300  # 5分钟


def get_price_tencent(code):
    """腾讯API"""
    if code.startswith('6'):
        market = 'sh'
    else:
        market = 'sz'
    
    url = f"https://qt.gtimg.cn/q={market}{code}"
    try:
        resp = requests.get(url, timeout=2)
        if '~' in resp.text:
            parts = resp.text.split('~')
            return {
                'source': 'tencent',
                'price': float(parts[3]),
                'name': parts[1],
                'time': datetime.now().strftime('%H:%M:%S')
            }
    except:
        pass
    return None


def get_price_sina(code):
    """新浪API"""
    if code.startswith('6'):
        market = 'sh'
    else:
        market = 'sz'
    
    url = f"https://hq.sinajs.cn/list={market}{code}"
    try:
        resp = requests.get(url, timeout=2)
        text = resp.text
        if '=' in text:
            parts = text.split('=')[1].split(',')
            return {
                'source': 'sina',
                'price': float(parts[0]),
                'name': parts[1],
                'time': datetime.now().strftime('%H:%M:%S')
            }
    except:
        pass
    return None


def get_price_eastmoney(code):
    """东方财富API"""
    secid = f"1.{code}" if code.startswith('6') else f"0.{code}"
    url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f2,f3,f4,f14"
    try:
        resp = requests.get(url, timeout=2)
        data = resp.json()
        if data.get('data'):
            return {
                'source': 'eastmoney',
                'price': data['data'].get('f2', 0),
                'name': data['data'].get('f14', ''),
                'time': datetime.now().strftime('%H:%M:%S')
            }
    except:
        pass
    return None


def get_realtime_price(code, use_cache=True):
    """
    多数据源获取实时价格
    
    优先级: 腾讯 → 新浪 → 东方财富 → 缓存 → 昨日收盘
    """
    # 1. 检查缓存
    cache_key = code
    if use_cache and cache_key in PRICE_CACHE:
        cached = PRICE_CACHE[cache_key]
        if time.time() - cached['timestamp'] < CACHE_TIMEOUT:
            cached['from_cache'] = True
            return cached
    
    # 2. 多数据源尝试
    for get_func in [get_price_tencent, get_price_sina, get_price_eastmoney]:
        for retry in range(3):  # 重试3次
            try:
                result = get_func(code)
                if result and result.get('price', 0) > 0:
                    result['timestamp'] = time.time()
                    result['from_cache'] = False
                    PRICE_CACHE[cache_key] = result
                    return result
            except:
                time.sleep(0.3)  # 等待后重试
    
    # 3. 返回缓存(即使过期)
    if cache_key in PRICE_CACHE:
        cached = PRICE_CACHE[cache_key]
        cached['expired'] = True
        cached['from_cache'] = True
        return cached
    
    # 4. 返回None
    return None


def get_batch_prices(codes):
    """批量获取实时价格"""
    results = []
    for code in codes:
        price = get_realtime_price(code)
        if price:
            results.append({
                'code': code,
                **price
            })
        time.sleep(0.1)  # 避免请求过快
    return results


# 测试
if __name__ == '__main__':
    import sys
    
    codes = ['600188', '000507', '000001']
    
    print("测试多数据源实时价格获取:\n")
    
    for code in codes:
        result = get_realtime_price(code)
        if result:
            print(f"{code}: ¥{result['price']:.2f} (来源:{result['source']}, 缓存:{result.get('from_cache', False)})")
        else:
            print(f"{code}: 获取失败")
