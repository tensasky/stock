#!/usr/bin/env python3
"""
量化交易系统 - 核心引擎
统一入口，自主运行
"""

import os
import sys
import json
import sqlite3
import requests
from datetime import datetime, timedelta
from pathlib import Path

# 配置
DB_PATH = 'data/stocks.db'
DATA_DIR = 'data'
CONFIG_FILE = 'config.json'

class QuantEngine:
    """量化交易引擎"""

    def __init__(self):
        self.db_path = DB_PATH
        self.init_db()
        self.load_config()

    def init_db(self):
        """初始化数据库"""
        os.makedirs(DATA_DIR, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 核心表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_data (
                code TEXT, date TEXT, open REAL, high REAL, low REAL,
                close REAL, volume REAL, change_pct REAL,
                PRIMARY KEY (code, date)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_info (
                code TEXT PRIMARY KEY, name TEXT, industry TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                code TEXT PRIMARY KEY, shares INTEGER, cost REAL, entry_date TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT, date TEXT, score REAL, reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT, action TEXT, price REAL, shares INTEGER,
                date TEXT, reason TEXT
            )
        ''')

        conn.commit()
        conn.close()
        print("✅ 数据库初始化完成")

    def load_config(self):
        """加载配置"""
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                self.config = json.load(f)
        else:
            self.config = {
                'strategy': 'v8',
                'min_score': 10,
                'max_positions': 5,
                'stop_loss': 0.07,
                'take_profit': 0.15
            }
            self.save_config()

    def save_config(self):
        """保存配置"""
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)

    # ========== 数据层 ==========

    def fetch_realtime(self, code):
        """获取实时价格"""
        import subprocess
        market = 'sh' + code if code.startswith('6') else 'sz' + code

        try:
            result = subprocess.run(
                ['curl', '-s', f'https://qt.gtimg.cn/q={market}'],
                capture_output=True, timeout=3
            )
            text = result.stdout.decode('gbk', errors='ignore')

            if 'no permission' not in text and len(text) > 10:
                d = text.split('~')
                # 腾讯API: ~0=代码,1=名称,2=代码,3=现价,4=涨跌,5=买入,6=卖出,7=成交量
                if len(d) > 7:
                    return {
                        'name': d[1],
                        'price': float(d[3]) if d[3] else 0,
                        'change': float(d[4]) if d[4] else 0,
                        'volume': int(float(d[7])) if d[7] else 0
                    }
        except Exception as e:
            print(f"Error: {e}")

        return None

    def update_data(self, days=30):
        """更新日线数据"""
        import baostock as bs
        lg = bs.login()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 获取所有股票
        cursor.execute("SELECT code FROM stock_info")
        codes = [r[0] for r in cursor.fetchall()]

        updated = 0
        for code in codes[:100]:  # 每次更新100只
            try:
                bs_code = 'sh.' + code if code.startswith('6') else 'sz.' + code
                rs = bs.query_history_k_data_plus(
                    bs_code, "date,open,high,low,close,volume",
                    start_date=(datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d'),
                    frequency='d', adjustflag='2'
                )

                while rs.next():
                    data = rs.get_row_data()
                    cursor.execute('''
                        INSERT OR REPLACE INTO daily_data
                        (code, date, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (code, data[0], float(data[1]), float(data[2]),
                          float(data[3]), float(data[4]), int(data[5])))
                    updated += 1
            except:
                pass

        conn.commit()
        conn.close()
        bs.logout()
        print(f"✅ 更新 {updated} 条数据")
        return updated

    # ========== 策略层 ==========

    def get_signals(self, limit=10):
        """获取选股信号 - 使用实时价格+昨日收盘计算今日涨幅"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        signals = []

        # 获取有最多股票数据的日期
        cursor.execute('''
            SELECT date FROM daily_data
            GROUP BY date
            ORDER BY COUNT(*) DESC
            LIMIT 1
        ''')
        result = cursor.fetchone()
        if not result:
            return []
        max_date = result[0]

        # 获取该日期的股票 (排除指数)
        cursor.execute(f'''
            SELECT DISTINCT code FROM daily_data
            WHERE date = "{max_date}"
            AND (code LIKE "6%" OR code LIKE "00%" OR code LIKE "30%")
            AND code NOT IN ('000001', '000002', '399001', '399006', '399300')
            LIMIT 100
        ''')

        codes = [r[0] for r in cursor.fetchall()]

        checked = 0
        for code in codes:
            # 获取最近20天数据
            cursor.execute(f'''
                SELECT close, volume FROM daily_data
                WHERE code=? AND date <= "{max_date}"
                ORDER BY date DESC LIMIT 20
            ''', (code,))

            rows = cursor.fetchall()
            if len(rows) < 20:
                continue

            checked += 1
            prices = [r[0] for r in rows][::-1]  # 正序
            yesterday_close = prices[-1]  # 昨日收盘价

            ma5 = sum(prices[-5:]) / 5
            ma10 = sum(prices[-10:]) / 10
            ma20 = sum(prices[-20:]) / 20

            # 多头排列 (MA5 > MA10)
            if ma5 > ma10:
                rt = self.fetch_realtime(code)

                if rt is None:
                    continue

                change_pct = (rt['price'] - yesterday_close) / yesterday_close * 100
                score = (ma5 / ma20 - 1) * 100 + change_pct if ma20 > 0 else change_pct

                signals.append({
                        'code': code,
                        'name': rt['name'],
                        'price': rt['price'],
                        'yesterday_close': yesterday_close,
                        'change': change_pct,
                        'score': score,
                        'reason': '多头排列+实时涨幅'
                    })

        print(f"Checked {checked} codes, found {len(signals)} signals")
        conn.close()

        # 按分数排序
        signals.sort(key=lambda x: x['score'], reverse=True)
        return signals[:limit]

        conn.close()

        # 按分数排序
        signals.sort(key=lambda x: x['score'], reverse=True)
        return signals[:limit]

    # ========== 交易层 ==========
    
    # 交易费用
    SLIPPAGE = 0.002  # 滑点 0.2%
    SELL_FEE = 0.0003  # 卖出手续费 万分之三
    
    def buy(self, code, price, reason=''):
        """买入 (考虑滑点)"""
        # 买入价格 = 实时价格 × (1 + 滑点)
        buy_price = price * (1 + self.SLIPPAGE)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 检查是否已有持仓
        cursor.execute('SELECT shares, cost FROM positions WHERE code=?', (code,))
        row = cursor.fetchone()

        if row:
            # 补仓
            shares, cost = row
            new_cost = (cost * shares + buy_price * 100) / (shares + 100)
            cursor.execute('UPDATE positions SET shares=?, cost=? WHERE code=?',
                         (shares + 100, new_cost, code))
        else:
            # 新买入
            cursor.execute('INSERT INTO positions VALUES (?, ?, ?, ?)',
                         (code, 100, buy_price, datetime.now().strftime('%Y-%m-%d')))
        
        # 记录交易 (记录实际成交价格)
        cursor.execute('INSERT INTO trades (code, action, price, shares, date, reason) VALUES (?, ?, ?, ?, ?, ?)',
                     (code, 'BUY', buy_price, 100, datetime.now().strftime('%Y-%m-%d'), reason))
        
        conn.commit()
        conn.close()
        print(f"✅ 买入 {code} @ ¥{buy_price:.2f} (滑点{self.SLIPPAGE*100:.1f}%)")
    
    def sell(self, code, price, reason=''):
        """卖出 (考虑滑点+手续费)"""
        # 卖出价格 = 实时价格 × (1 - 滑点 - 手续费)
        sell_price = price * (1 - self.SLIPPAGE - self.SELL_FEE)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM positions WHERE code=?', (code,))
        cursor.execute('INSERT INTO trades (code, action, price, shares, date, reason) VALUES (?, ?, ?, ?, ?, ?)',
                     (code, 'SELL', sell_price, 100, datetime.now().strftime('%Y-%m-%d'), reason))
        
        conn.commit()
        conn.close()
        print(f"✅ 卖出 {code} @ ¥{sell_price:.2f} (扣滑点{self.SLIPPAGE*100:.1f}%+手续费{self.SELL_FEE*10000:.0f}‰)")
    
    def check_positions(self):
        """检查持仓 (考虑滑点+手续费)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT code, shares, cost FROM positions')
        positions = cursor.fetchall()
        
        print("\n📊 当前持仓:")
        print(f"{'代码':<8} {'数量':>6} {'成本':>8} {'现价':>8} {'盈亏(扣费)':>14}")
        print("-"*60)
        
        total_pnl = 0
        for code, shares, cost in positions:
            rt = self.fetch_realtime(code)
            if rt:
                # 卖出时净收入
                net_price = rt['price'] * (1 - self.SLIPPAGE - self.SELL_FEE)
                pnl = (net_price - cost) / cost * 100
                total_pnl += pnl
                print(f"{code:<8} {shares:>6} ¥{cost:>7.2f} ¥{rt['price']:>7.2f} {pnl:>+13.2f}%")
        
        print(f"  总盈亏(扣费): {total_pnl:+.2f}%")
        print(f"  (已扣除滑点0.2% + 卖出手续费0.03‰)")
        
        conn.close()
        return positions

    # ========== 主循环 ==========

    def run(self, mode='scan'):
        """运行系统"""
        print(f"\n{'='*50}")
        print(f"🎯 量化系统 v1.0 - {mode}")
        print(f"{'='*50}")

        if mode == 'scan':
            # 选股
            signals = self.get_signals()
            print(f"\n📈 选股信号 ({len(signals)}只):")
            for s in signals:
                print(f"  {s['code']} {s['name']}: {s['change']:+.2f}% ({s['reason']})")

        elif mode == 'trade':
            # 交易
            self.check_positions()
            signals = self.get_signals(3)
            if signals:
                print("\n🛒 推荐买入:")
                for s in signals[:3]:
                    print(f"  {s['code']} {s['name']} ¥{s['price']:.2f}")

        elif mode == 'update':
            # 更新数据
            self.update_data()

        elif mode == 'status':
            # 状态
            self.check_positions()


# 入口
if __name__ == '__main__':
    engine = QuantEngine()

    if len(sys.argv) > 1:
        mode = sys.argv[1]
    else:
        mode = 'status'

    engine.run(mode)
