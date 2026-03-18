#!/usr/bin/env python3
# 每日收盘后自动补数据
# 在每天16:00执行

import requests
import sqlite3
import time
from datetime import datetime

DB_PATH = 'data/stocks.db'

def get_kline(code, days=3):
    if code.startswith('6'):
        secid = f"1.{code}"
    else:
        secid = f"0.{code}"
    
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        'secid': secid,
        'fields1': 'f1,f2,f3,f4,f5,f6',
        'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
        'klt': '101', 'fqt': '0', 'beg': '20250101', 
        'end': datetime.now().strftime('%Y%m%d'), 'lmt': days
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data.get('data') and data['data'].get('klines'):
            return data['data']['klines']
    except:
        pass
    return []

def main():
    print(f"📥 补数据: {datetime.now()}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT code FROM daily_data")
    codes = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    saved = 0
    for i, code in enumerate(codes):
        klines = get_kline(code, 3)
        if klines:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            for line in klines:
                parts = line.split(',')
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO daily_data 
                        (code, date, open, high, low, close, volume, amount, change_pct)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (code, parts[0], float(parts[1]), float(parts[2]), 
                          float(parts[3]), float(parts[4]), float(parts[5]),
                          float(parts[6]), float(parts[7]) if parts[7] != '-' else 0))
                    saved += 1
                except:
                    pass
            conn.commit()
            conn.close()
        time.sleep(0.1)
        if (i+1) % 500 == 0:
            print(f"  进度: {i+1}/{len(codes)}")
    
    print(f"✅ 补数据完成, 新增 {saved} 条")

if __name__ == '__main__':
    main()
