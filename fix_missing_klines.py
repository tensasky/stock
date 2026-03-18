#!/usr/bin/env python3
"""
补全市场A股历史K线数据
先补600/601沪市，再补000/002/300深市
"""
import baostock as bs
import sqlite3
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

DB_PATH = 'data/stocks.db'
lock = threading.Lock()

def code_to_baostock(code):
    if code.startswith('6'):
        return f"sh.{code}"
    elif code.startswith(('0', '3')):
        return f"sz.{code}"
    return None

def download_stock(code):
    """下载单只股票历史K线"""
    bs_code = code_to_baostock(code)
    if not bs_code:
        return code, []
    
    try:
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
            row[1] = code  # 替换为简码
            data.append(row)
    except Exception as e:
        return code, []
    
    return code, data

def save_to_db(data_list):
    if not data_list:
        return 0
    
    with lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        saved = 0
        
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
                    saved += 1
                except:
                    pass
        
        conn.commit()
        conn.close()
    return saved

def main():
    print(f"=== 补全市场A股历史K线 ===")
    print(f"开始: {datetime.now()}")
    
    # 登录
    lg = bs.login()
    if lg.error_code != '0':
        print(f"登录失败: {lg.error_msg}")
        return
    
    # 获取所有A股
    print("📥 获取股票列表...")
    rs = bs.query_stock_basic()
    all_stocks = []
    while rs.error_code == '0' and rs.next():
        row = rs.get_row_data()
        code = row[0].split('.')[1]
        # 过滤: 只要600/601/000/002/300/301开头的A股
        if code.startswith(('600', '601', '000', '002', '300', '301')):
            all_stocks.append(code)
    
    print(f"A股总数: {len(all_stocks)}")
    
    # 检查已有哪些
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT code FROM daily_data")
    existing = set(row[0] for row in cursor.fetchall())
    conn.close()
    
    # 过滤掉已有的
    to_download = [c for c in all_stocks if c not in existing]
    print(f"需要补: {len(to_download)} 只 (已有 {len(existing)} 只)")
    
    # 分类统计
    markets = {'600/601': 0, '000': 0, '002': 0, '300': 0, '301': 0}
    for c in to_download:
        if c.startswith(('600', '601')):
            markets['600/601'] += 1
        elif c.startswith('000'):
            markets['000'] += 1
        elif c.startswith('002'):
            markets['002'] += 1
        elif c.startswith('300'):
            markets['300'] += 1
        elif c.startswith('301'):
            markets['301'] += 1
    
    print(f"待补分布: {markets}")
    
    # 优先补600/601
    priority = [c for c in to_download if c.startswith(('600', '601'))]
    print(f"\n🔴 优先补600/601: {len(priority)} 只")
    
    total = len(priority)
    done = 0
    saved_total = 0
    
    # 并行下载
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(download_stock, code): code for code in priority}
        
        for future in as_completed(futures):
            code, data = future.result()
            if data:
                saved = save_to_db(data)
                saved_total += saved
            
            done += 1
            if done % 50 == 0:
                print(f"  进度: {done}/{total} (已存 {saved_total} 条)")
    
    bs.logout()
    
    # 结果
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT MAX(date) FROM daily_data')
    latest = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT code) FROM daily_data WHERE code LIKE '6%'")
    sh_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(DISTINCT code) FROM daily_data')
    total_count = cursor.fetchone()[0]
    conn.close()
    
    print(f"\n✅ 第一批完成!")
    print(f"最新日期: {latest}")
    print(f"沪市股票: {sh_count} 只")
    print(f"总计股票: {total_count} 只")
    print(f"结束: {datetime.now()}")
    
    print(f"\n📌 提示: 还需补 {len(all_stocks) - total_count} 只 (000/002/300/301)")

if __name__ == '__main__':
    main()
