#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票信号 - V6 动态股票池系统
- 根据量比和技术信号动态选入
- 自动标记止盈/止损移除
- 10个交易日无信号移除
"""

import sys
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pickle

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_fetcher import DataFetcher

# 股票池数据文件
POOL_FILE = 'stock_pool_data.pkl'

# 默认观察池 (大盘蓝筹)
DEFAULT_WATCH = [
    '600519', '600036', '601318', '600900', '600188', '600971', '600395',
    '601012', '002594', '300750', '688041', '688111', '300751',
    '600893', '600879', '002410', '000001', '000858', '600276',
    '601888', '600309', '000333', '000651', '600104', '600050',
]


def load_pool():
    """加载股票池数据"""
    if os.path.exists(POOL_FILE):
        with open(POOL_FILE, 'rb') as f:
            return pickle.load(f)
    return {
        'active': [],      # 当前活跃股票
        'removed': [],     # 已移除股票
        'history': []      # 历史记录
    }


def save_pool(pool):
    """保存股票池数据"""
    with open(POOL_FILE, 'wb') as f:
        pickle.dump(pool, f)


def calculate_indicators(df):
    """计算技术指标"""
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']
    
    ma5 = close.rolling(5).mean()
    ma10 = close.rolling(10).mean()
    ma20 = close.rolling(20).mean()
    
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    macd_hist = (dif - dea) * 2
    
    low9 = low.rolling(9).min()
    high9 = high.rolling(9).max()
    rsv = (close - low9) / (high9 - low9) * 100
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    j = 3 * k - 2 * d
    
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(span=14, adjust=False).mean()
    avg_loss = loss.ewm(span=14, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    vol_ma20 = volume.rolling(20).mean()
    
    price_up = close > close.shift(1)
    vol_up = volume > volume.shift(1)
    money_in = price_up & vol_up
    
    latest = df.iloc[-1]
    
    return {
        'close': latest['close'],
        'prev_close': df.iloc[-2]['close'] if len(df) > 1 else latest['close'],
        'high': latest['high'],
        'low': latest['low'],
        'volume': latest['volume'],
        'ma5': ma5.iloc[-1],
        'ma10': ma10.iloc[-1],
        'ma20': ma20.iloc[-1],
        'dif': dif.iloc[-1],
        'dea': dea.iloc[-1],
        'macd_hist': macd_hist.iloc[-1],
        'k': k.iloc[-1],
        'd': d.iloc[-1],
        'j': j.iloc[-1],
        'rsi': rsi.iloc[-1],
        'vol_ma20': vol_ma20.iloc[-1],
        'vol_ratio': latest['volume'] / vol_ma20.iloc[-1] if vol_ma20.iloc[-1] > 0 else 1,
        'money_streak': money_in.rolling(2).sum().iloc[-1] >= 1,
        'price_change': (latest['close'] - df.iloc[-2]['close']) / df.iloc[-2]['close'] * 100 if len(df) > 1 else 0
    }


def analyze_stock(symbol, fetcher):
    """分析单只股票"""
    df = fetcher.get_stock_data(symbol, days=60)
    if df is None or len(df) < 30:
        return None
    
    ind = calculate_indicators(df)
    
    score = 0
    buy_signals = []
    
    # V6 策略评分
    if ind['ma5'] > ind['ma10'] > ind['ma20']:
        score += 3
        buy_signals.append('多头排列')
    
    if ind['money_streak']:
        score += 3
        buy_signals.append('资金流入')
    
    if ind['dif'] > ind['dea']:
        score += 2
        buy_signals.append('MACD金叉')
    
    if ind['macd_hist'] > 0:
        score += 1
        buy_signals.append('MACD红柱')
    
    if ind['k'] < 20 or ind['j'] < 0:
        score += 2
        buy_signals.append('KDJ超卖')
    
    if ind['rsi'] < 35:
        score += 2
        buy_signals.append('RSI超卖')
    
    # 放量
    if ind['vol_ratio'] > 2:
        score += 2
        buy_signals.append('量比>2')
    
    # 放量突破
    if ind['vol_ratio'] > 1.5 and ind['close'] > ind['ma20']:
        score += 2
        buy_signals.append('放量突破')
    
    return {
        'symbol': symbol,
        'price': ind['close'],
        'change': ind['price_change'],
        'score': score,
        'signals': buy_signals,
        'vol_ratio': ind['vol_ratio'],
        'rsi': ind['rsi'],
        'indicators': {
            'MA5': round(ind['ma5'], 2),
            'MA10': round(ind['ma10'], 2),
            'MA20': round(ind['ma20'], 2),
            'RSI': round(ind['rsi'], 1),
            '量比': round(ind['vol_ratio'], 1),
        }
    }


def update_pool(fetcher):
    """更新股票池"""
    pool = load_pool()
    today = datetime.now().strftime('%Y-%m-%d')
    today_date = datetime.now().date()
    
    print("📊 分析默认观察池...")
    
    # 检查现有活跃股票
    for stock in pool['active'][:]:
        try:
            result = analyze_stock(stock['symbol'], fetcher)
            if result is None:
                continue
            
            # 检查是否触发止盈/止损
            remove_reason = None
            if result['price'] >= stock.get('take_profit', float('inf')):
                remove_reason = '达到止盈价'
            elif result['price'] <= stock.get('stop_loss', 0):
                remove_reason = '跌破止损价'
            
            # 检查是否持仓达到10天
            entry_date = datetime.strptime(stock['entry_date'], '%Y-%m-%d').date()
            days_held = (today_date - entry_date).days
            
            if days_held >= 10 and result['score'] < 4:
                remove_reason = '10个交易日无强势信号'
            
            if remove_reason:
                stock['remove_date'] = today
                stock['remove_reason'] = remove_reason
                stock['current_price'] = result['price']
                stock['pnl'] = (result['price'] - stock['entry_price']) / stock['entry_price'] * 100
                pool['removed'].append(stock)
                pool['active'].remove(stock)
                print(f"  移除 {stock['symbol']}: {remove_reason}")
            else:
                # 更新当前价格和信号
                stock['current_price'] = result['price']
                stock['current_change'] = result['change']
                stock['current_signals'] = result['signals']
                stock['days_held'] = days_held
        except Exception as e:
            print(f"  {stock['symbol']}: 错误")
    
    # 检查默认观察池，添加新的符合条件的股票
    for symbol in DEFAULT_WATCH:
        # 跳过已存在的
        if any(s['symbol'] == symbol for s in pool['active']):
            continue
        
        try:
            result = analyze_stock(symbol, fetcher)
            if result is None:
                continue
            
            # 选入条件: 量比1.5-3 + 多头+资金 (V6.1更稳健)
            if 1.5 < result['vol_ratio'] < 3 and result['score'] >= 5:
                entry_price = result['price']
                
                new_stock = {
                    'symbol': symbol,
                    'entry_date': today,
                    'entry_price': entry_price,
                    'entry_reason': f"量比>{result['vol_ratio']:.1f}, 信号:{', '.join(result['signals'])}",
                    'current_price': entry_price,
                    'current_signals': result['signals'],
                    'score': result['score'],
                    'stop_loss': entry_price * 0.98,  # -2%
                    'take_profit': entry_price * 1.05,  # +5%
                    'days_held': 0,
                    'signals_history': [today]  # 记录出现信号的日子
                }
                pool['active'].append(new_stock)
                print(f"  新增 {symbol}: {result['signals']}")
        except:
            continue
    
    save_pool(pool)
    return pool


def generate_report(pool):
    """生成报告"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    active = pool.get('active', [])
    removed = pool.get('removed', [])
    
    # 分类
    strong = [s for s in active if s.get('score', 0) >= 6]
    moderate = [s for s in active if 4 <= s.get('score', 0) < 6]
    watch = [s for s in active if s.get('score', 0) < 4]
    
    html = f'''
<html><head><meta charset="utf-8"></head><body style="font-family: Arial; max-width: 900px; margin: 0 auto;">
<h1 style="color: #1a73e8;">📈 股票信号日报 V6 - 动态股票池</h1>
<p style="color: #666;">📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>

<h2 style="color: #34a853;">🔥 强势持仓 (≥6分): {len(strong)}只</h2>
'''
    
    if strong:
        for s in strong:
            days = s.get('days_held', 0)
            pnl = (s.get('current_price', 0) - s.get('entry_price', 0)) / s.get('entry_price', 0) * 100
            html += f'''
<div style="background: #e6f4ea; padding: 12px; margin: 8px 0; border-radius: 8px; border-left: 4px solid #34a853;">
<b>{s['symbol']}</b> | 得分: {s.get('score', 0)} | 当前: ¥{s.get('current_price', 0):.2f} ({s.get('current_change', 0):+.2f}%)
<br>📅 选入: {s['entry_date']} | 持有: {days}天 | PnL: <b style="color: {'green' if pnl > 0 else 'red'}">{pnl:+.2f}%</b>
<br>📝 选入原因: {s['entry_reason']}
<br>📊 当前信号: {', '.join(s.get('current_signals', []))}
</div>
'''
    
    html += f'''
<h2 style="color: #fbbc04;">⚠️ 适中持仓 (4-5分): {len(moderate)}只</h2>
'''
    
    if moderate:
        html += '<table border="1" cellpadding="4" style="border-collapse: collapse; width: 100%;">'
        html += '<tr><th>代码</th><th>得分</th><th>价格</th><th>选入日期</th><th>持有天数</th><th>选入原因</th></tr>'
        for s in moderate:
            html += f'<tr><td>{s["symbol"]}</td><td>{s.get("score", 0)}</td><td>¥{s.get("current_price", 0):.2f}</td><td>{s["entry_date"]}</td><td>{s.get("days_held", 0)}</td><td>{s["entry_reason"][:30]}...</td></tr>'
        html += '</table>'
    
    html += f'''
<h2>👀 观察中 (4分以下): {len(watch)}只</h2>
'''
    
    if watch:
        html += '<table border="1" cellpadding="4" style="border-collapse: collapse; width: 100%;">'
        html += '<tr><th>代码</th><th>得分</th><th>价格</th><th>选入日期</th><th>持有天数</th><th>选入原因</th></tr>'
        for s in watch:
            html += f'<tr><td>{s["symbol"]}</td><td>{s.get("score", 0)}</td><td>¥{s.get("current_price", 0):.2f}</td><td>{s["entry_date"]}</td><td>{s.get("days_held", 0)}</td><td>{s["entry_reason"][:30]}...</td></tr>'
        html += '</table>'
    
    # 移除记录
    recent_removed = [r for r in removed if r.get('remove_date') == today]
    
    if recent_removed:
        html += f'''
<h2 style="color: #ea4335;">❌ 今日移除: {len(recent_removed)}只</h2>
'''
        html += '<table border="1" cellpadding="4" style="border-collapse: collapse; width: 100%;">'
        html += '<tr><th>代码</th><th>选入日期</th><th>移除日期</th><th>选入价</th><th>移除价</th><th>收益率</th><th>移除原因</th></tr>'
        for r in recent_removed:
            html += f'<tr><td>{r["symbol"]}</td><td>{r["entry_date"]}</td><td>{r.get("remove_date", "")}</td><td>¥{r["entry_price"]:.2f}</td><td>¥{r.get("current_price", 0):.2f}</td><td style="color: {"green" if r.get("pnl", 0) > 0 else "red"}">{r.get("pnl", 0):+.2f}%</td><td>{r.get("remove_reason", "")}</td></tr>'
        html += '</table>'
    
    # 策略说明
    html += '''
<h2>📖 V6 策略说明</h2>
<ul>
<li><b>选入条件:</b> 量比>2 + 至少2个技术信号</li>
<li><b>强势信号:</b> ≥6分 - 可加仓</li>
<li><b>适中信号:</b> 4-5分 - 持有观望</li>
<li><b>移除条件:</b></li>
<ul>
<li>达到止盈价 (+5%)</li>
<li>跌破止损价 (-3%)</li>
<li>10个交易日无强势信号</li>
</ul>
</ul>

<h2>📊 分数计算</h2>
<table border="1" cellpadding="4" style="border-collapse: collapse;">
<tr><td>多头排列</td><td>+3</td></tr>
<tr><td>资金流入</td><td>+3</td></tr>
<tr><td>MACD金叉</td><td>+2</td></tr>
<tr><td>MACD红柱</td><td>+1</td></tr>
<tr><td>KDJ超卖</td><td>+2</td></tr>
<tr><td>RSI超卖</td><td>+2</td></tr>
<tr><td>量比>2</td><td>+2</td></tr>
<tr><td>放量突破</td><td>+2</td></tr>
</table>

<hr>
<p style="color: #888; font-size: 12px;">由自动交易系统发送 | 仅供参考，不构成投资建议</p>
</body></html>
'''
    
    return html


def send_email(html, subject):
    """发送邮件"""
    with open('mail_config.json') as f:
        config = json.load(f)
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = config['sender']
    msg.attach(MIMEText(html, 'html', 'utf-8'))
    
    s = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
    s.ehlo()
    s.starttls()
    s.ehlo()
    s.login(config['sender'], config['password'])
    
    for receiver in config['receivers']:
        msg['To'] = receiver
        s.send_message(msg)
    
    s.quit()


def run_daily():
    """运行每日分析"""
    print("📊 V6 动态股票池分析...")
    
    fetcher = DataFetcher()
    
    # 更新股票池
    pool = update_pool(fetcher)
    
    # 生成报告
    html = generate_report(pool)
    
    active = pool.get('active', [])
    strong = len([s for s in active if s.get('score', 0) >= 6])
    moderate = len([s for s in active if 4 <= s.get('score', 0) < 6])
    
    removed_today = len([r for r in pool.get('removed', []) if r.get('remove_date') == datetime.now().strftime('%Y-%m-%d')])
    
    subject = f"📈 股票日报 V6 - 持仓{len(active)}只 | 强势{strong}只 | 今日移除{removed_today}只"
    
    send_email(html, subject)
    
    print(f"✅ V6 报告已发送! 持仓: {len(active)}只, 强势: {strong}只")


if __name__ == "__main__":
    run_daily()
