#!/usr/bin/env python3
"""
批量更新A股历史数据 - 并行版本
"""
import baostock as bs
import sqlite3
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

lock = threading.Lock()

def get_all_stocks():
    """获取所有A股股票代码"""
    conn = sqlite3.connect('data/stocks.db')
    cursor = conn.cursor()
    cursor.execute("SELECT code FROM stocks")
    stocks = [row[0] for row in cursor.fetchall()]
    conn.close()
    return stocks

def code_to_baostock(code):
    """转换股票代码"""
    if code.startswith('6'):
        return f"sh.{code}"
    elif code.startswith(('0', '3')):
        return f"sz.{code}"
    return None

def download_stock(code):
    """下载单只股票"""
    bs_code = code_to_baostock(code)
    if not bs_code:
        return code, []
    
    rs = bs.query_history_k_data_plus(
        bs_code,
        "date,code,open,high,low,close,volume,amount",
        start_date="2024-01-01",
        end_date=datetime.now().strftime('%Y-%m-%d'),
        frequency="d",
        adjustflag="2"
    )
    
    data = []
    while rs.error_code == '0' and rs.next():
        row = rs.get_row_data()
        row[1] = code
        data.append(row)
    
    return code, data

def save_to_db(data_list):
    """保存到数据库"""
    if not data_list:
        return
    
    conn = sqlite3.connect('data/stocks.db')
    cursor = conn.cursor()
    
    for data in data_list:
        if len(data) >= 8:
            try:
                cursor.execute("""INSERT OR REPLACE INTO daily_data 
                    (code, date, open, high, low, close, volume, amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (data[1], data[0], float(data[2]) if data[2] else 0,
                     float(data[3]) if data[3] else 0,
                     float(data[4]) if data[4] else 0,
                     float(data[5]) if data[5] else 0,
                     float(data[6]) if data[6] else 0,
                     float(data[7]) if data[7] else 0))
            except:
                pass
    
    conn.commit()
    conn.close()

def main():
    print(f"=== 批量更新A股历史数据 ===")
    print(f"开始: {datetime.now()}")
    
    lg = bs.login()
    if lg.error_code != '0':
        print(f"登录失败")
        return
    
    stocks = get_all_stocks()
    print(f"股票数: {len(stocks)}")
    
    total = len(stocks)
    done = 0
    
    # 并行下载
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(download_stock, code): code for code in stocks}
        
        for future in as_completed(futures):
            code, data = future.result()
            if data:
                save_to_db(data)
            
            done += 1
            if done % 200 == 0:
                print(f"进度: {done}/{total}")
    
    bs.logout()
    
    # 结果
    conn = sqlite3.connect('data/stocks.db')
    cursor = conn.cursor()
    cursor.execute('SELECT MAX(date) FROM daily_data')
    latest = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(DISTINCT code) FROM daily_data')
    count = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n完成!")
    print(f"最新: {latest}, 股票: {count}")
    print(f"结束: {datetime.now()}")

if __name__ == '__main__':
    main()
