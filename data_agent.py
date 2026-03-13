# 数据Agent - 股票数据抓取与存储
# 功能: 抓取、清洗、存储股票数据到本地SQLite

import requests
import sqlite3
import pandas as pd
import time
from datetime import datetime, timedelta
import os

# ==================== 配置 ====================
DB_PATH = 'data/stocks.db'
DATA_DIR = 'data'

# 观察池股票
WATCH_POOL = {
    '煤炭': ['600971', '600188', '600395', '600893'],
    '新能源车': ['002594', '300750', '002466'],
    'AI/半导体': ['688111', '688169', '688400', '688041'],
    '机器人': ['002410', '002230', '301029', '688395'],
    '光伏': ['601012', '600438'],
}

# 股票名称映射
STOCK_NAMES = {
    '600971': '恒源煤电', '600188': '兖矿能源', '600395': '盘江股份',
    '600893': '中航重机', '002594': '比亚迪', '300750': '宁德时代',
    '002466': '中际旭创', '688111': '华大九天', '688169': '芯原股份',
    '688400': '慧智微', '688041': '英杰电气', '002410': '广联达',
    '002230': '科大讯飞', '301029': '怡和嘉业', '688395': '埃斯顿',
    '601012': '隆基绿能', '600438': '通威股份',
}


class DataAgent:
    """数据Agent - 负责数据抓取与存储"""
    
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 股票基本信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stocks (
                code TEXT PRIMARY KEY,
                name TEXT,
                sector TEXT,
                list_date TEXT,
                updated_at TEXT
            )
        ''')
        
        # 日线数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                change_pct REAL,
                UNIQUE(code, date)
            )
        ''')
        
        # 技术指标表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS indicators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                date TEXT NOT NULL,
                ma5 REAL, ma10 REAL, ma20 REAL, ma60 REAL,
                ema12 REAL, ema26 REAL,
                dif REAL, dea REAL, macd REAL,
                k REAL, d REAL, j REAL,
                rsi6 REAL, rsi12 REAL, rsi24,
                vol_ratio REAL,
                updated_at TEXT,
                UNIQUE(code, date)
            )
        ''')
        
        # 指数表 (大盘数据)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS indices (
                code TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL, high REAL, low REAL, close REAL,
                volume REAL, amount REAL, change_pct REAL,
                PRIMARY KEY (code, date)
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_code_date ON daily_data(code, date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ind_code_date ON indicators(code, date)')
        
        conn.commit()
        conn.close()
        print(f"✅ 数据库初始化完成: {self.db_path}")
    
    def get_secid(self, code):
        """获取东方财富的secid"""
        if code.startswith('6'):
            return f"1.{code}"  # 上海
        else:
            return f"0.{code}"  # 深圳
    
    def fetch_kline(self, code, days=250):
        """获取K线数据"""
        secid = self.get_secid(code)
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days+30)).strftime('%Y%m%d')
        
        url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            'secid': secid,
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
            'klt': '101',  # 日线
            'fqt': '0',    # 不复权
            'beg': start_date,
            'end': end_date,
            'lmt': days
        }
        
        try:
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            
            if data.get('data') and data['data'].get('klines'):
                klines = data['data']['klines']
                records = []
                for line in klines:
                    parts = line.split(',')
                    record = {
                        'date': parts[0],
                        'open': float(parts[1]),
                        'high': float(parts[2]),
                        'low': float(parts[3]),
                        'close': float(parts[4]),
                        'volume': float(parts[5]),
                        'amount': float(parts[6]),
                    }
                    # 计算涨跌幅
                    if len(parts) > 7:
                        record['change_pct'] = float(parts[7]) if parts[7] != '-' else 0
                    records.append(record)
                return records
        except Exception as e:
            print(f"❌ 获取{code}失败: {e}")
        return []
    
    def save_daily_data(self, code, records):
        """保存日线数据"""
        if not records:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        saved = 0
        for r in records:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO daily_data 
                    (code, date, open, high, low, close, volume, amount, change_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (code, r['date'], r['open'], r['high'], r['low'], 
                      r['close'], r['volume'], r['amount'], r.get('change_pct', 0)))
                saved += 1
            except Exception as e:
                pass
        
        conn.commit()
        conn.close()
        return saved
    
    def save_stock_info(self, code, name, sector):
        """保存股票基本信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO stocks (code, name, sector, updated_at)
            VALUES (?, ?, ?, ?)
        ''', (code, name, sector, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    
    def fetch_and_save(self, code, name='', sector='', days=250):
        """抓取并保存单只股票数据"""
        print(f"📥 抓取 {code} {name}...")
        records = self.fetch_kline(code, days)
        
        if records:
            saved = self.save_daily_data(code, records)
            print(f"   ✅ 保存 {saved} 条日线数据")
            
            # 保存股票信息
            if name:
                self.save_stock_info(code, name, sector)
            
            return len(records)
        return 0
    
    def fetch_watch_pool(self, days=250):
        """抓取整个观察池"""
        total = 0
        for sector, codes in WATCH_POOL.items():
            print(f"\n🏭 抓取板块: {sector}")
            for code in codes:
                name = STOCK_NAMES.get(code, code)
                count = self.fetch_and_save(code, name, sector, days)
                total += count
                time.sleep(0.5)  # 避免请求过快
        print(f"\n✅ 观察池抓取完成, 共 {total} 条数据")
        return total
    
    def fetch_index(self, code='000001', name='上证指数', days=250):
        """抓取指数数据"""
        print(f"📥 抓取指数 {code} {name}...")
        secid = self.get_secid(code)
        
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days+30)).strftime('%Y%m%d')
        
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            'secid': secid,
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
            'klt': '101',
            'fqt': '0',
            'beg': start_date,
            'end': end_date,
            'lmt': days
        }
        
        try:
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            
            if data.get('data') and data['data'].get('klines'):
                klines = data['data']['klines']
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                saved = 0
                for line in klines:
                    parts = line.split(',')
                    cursor.execute('''
                        INSERT OR REPLACE INTO indices
                        (code, date, open, high, low, close, volume, amount, change_pct)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (code, parts[0], float(parts[1]), float(parts[2]), 
                          float(parts[3]), float(parts[4]), float(parts[5]),
                          float(parts[6]), float(parts[7]) if parts[7] != '-' else 0))
                    saved += 1
                
                conn.commit()
                conn.close()
                print(f"   ✅ 保存 {saved} 条指数数据")
                return saved
        except Exception as e:
            print(f"❌ 获取指数失败: {e}")
        return 0
    
    def get_daily_data(self, code, start_date=None, end_date=None):
        """查询日线数据"""
        conn = sqlite3.connect(self.db_path)
        
        query = "SELECT date, open, high, low, close, volume, amount, change_pct FROM daily_data WHERE code = ?"
        params = [code]
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " ORDER BY date"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    
    def get_latest_price(self, code):
        """获取最新价格"""
        df = self.get_daily_data(code, limit=1)
        if not df.empty:
            return df.iloc[-1]['close']
        return None
    
    def get_stock_count(self):
        """获取股票数量"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT code) FROM daily_data")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def get_data_stats(self):
        """获取数据统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM daily_data")
        total_days = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT code) FROM daily_data")
        stock_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT MIN(date), MAX(date) FROM daily_data")
        date_range = cursor.fetchone()
        
        conn.close()
        
        return {
            'total_records': total_days,
            'stock_count': stock_count,
            'start_date': date_range[0],
            'end_date': date_range[1]
        }


# ==================== 主程序 ====================
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='数据Agent - 股票数据抓取')
    parser.add_argument('action', choices=['fetch', 'stats', 'query'], 
                        help='操作: fetch=抓取数据, stats=查看统计, query=查询')
    parser.add_argument('--code', help='股票代码')
    parser.add_argument('--days', type=int, default=250, help='抓取天数')
    
    args = parser.parse_args()
    
    agent = DataAgent()
    
    if args.action == 'fetch':
        # 抓取观察池
        agent.fetch_watch_pool(days=args.days)
        
        # 抓取上证指数
        agent.fetch_index('000001', '上证指数', args.days)
        
        # 统计
        stats = agent.get_data_stats()
        print(f"\n📊 数据统计:")
        print(f"   股票数: {stats['stock_count']}")
        print(f"   总记录: {stats['total_records']}")
        print(f"   日期范围: {stats['start_date']} ~ {stats['end_date']}")
    
    elif args.action == 'stats':
        stats = agent.get_data_stats()
        print(f"📊 数据统计:")
        print(f"   股票数: {stats['stock_count']}")
        print(f"   总记录: {stats['total_records']}")
        print(f"   日期范围: {stats['start_date']} ~ {stats['end_date']}")
    
    elif args.action == 'query':
        if args.code:
            df = agent.get_daily_data(args.code)
            print(f"📈 {args.code} 最近10条数据:")
            print(df.tail(10))
        else:
            print("请指定 --code 参数")
