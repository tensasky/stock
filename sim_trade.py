#!/usr/bin/env python3
"""
V6.2 模拟操盘系统
- 实时价格 (腾讯API)
- 动态止盈止损
- 量化指标选股
"""

import sys, os, pickle, json, re, requests
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
import pandas as pd
import numpy as np

# 添加data_fetcher路径
sys.path.insert(0, '.')
from data_fetcher import DataFetcher
from smart_fetcher import SmartDataFetcher

# 配置
DATA_FILE = 'sim_trade.pkl'
MAIL_CONFIG = 'mail_config.json'
TRADING_HOURS = [('09:35', '11:30'), ('13:00', '14:57')]
NOTIFY_INTERVAL = 30

# 股票池
WATCH_LIST = [
    '600971','600188','600395','600893','002594',
    '600036','600900','601012','300750','688041','688111','300751'
]

# 初始化数据
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'wb') as f:
        pickle.dump({'positions': [], 'history': [], 'trades': [], 'last_notify': None}, f)

def load_data():
    with open(DATA_FILE, 'rb') as f:
        return pickle.load(f)

def save_data(data):
    with open(DATA_FILE, 'wb') as f:
        pickle.dump(data, f)

def get_name(code):
    names = {'600971':'恒源煤电','600188':'兖州煤业','600395':'平煤股份','600893':'航发动力','002594':'比亚迪','600036':'招商银行','600900':'长江电力','601012':'隆基绿能','300750':'宁德时代','688041':'海光信息','688111':'江苏北人','300751':'瑞泰科技'}
    return names.get(code, code)

def get_realtime_price(code):
    """腾讯实时行情"""
    symbol = f'sh{code}' if code.startswith('6') else f'sz{code}'
    try:
        url = f'https://qt.gtimg.cn/q={symbol}'
        resp = requests.get(url, timeout=5)
        match = re.search(r'v_[a-z]+\d+="([^"]+)"', resp.text)
        if match:
            p = match.group(1).split('~')
            return {'price': float(p[3]), 'open': float(p[4]), 'high': float(p[5]), 'low': float(p[6]), 'volume': int(p[7])}
    except: pass
    return None

def send_notify(subject, body):
    try:
        from email.header import Header
        with open(MAIL_CONFIG) as f:
            cfg = json.load(f)
        # 使用纯文本格式
        sender_name = cfg.get('sender_name', '洪福齐天')
        from_addr = cfg['from']
        msg = MIMEText(body, 'plain', 'utf-8')
        # 使用Header编码中文发件人名称
        msg['From'] = f"{Header(sender_name, 'utf-8').encode()} <{from_addr}>"
        msg['To'] = ', '.join(cfg['to'])
        msg['Subject'] = Header(f"白板红中喜讯 - {subject}", 'utf-8').encode()
        with smtplib.SMTP(cfg['smtp'], cfg['port']) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            s.login(cfg['user'], cfg['pass'])
            s.sendmail(from_addr, cfg['to'], msg.as_string())
        print(f"✅ 邮件已发送")
    except Exception as e:
        print(f"❌ 邮件失败: {e}")

def analyze_stock(code, df):
    """分析股票信号"""
    if df is None or len(df) < 20: return None
    
    close = df['close']
    ma5, ma10, ma20 = close.rolling(5).mean(), close.rolling(10).mean(), close.rolling(20).mean()
    v = df['volume'] / df['volume'].rolling(20).mean()
    
    ma5_val, ma10_val, ma20_val = ma5.iloc[-1], ma10.iloc[-1], ma20.iloc[-1]
    has_ma = ma5_val > ma10_val > ma20_val
    
    price_up = close > close.shift(1)
    vol_up = df['volume'] > df['volume'].shift(1)
    money_streak = (price_up & vol_up).rolling(2).sum().iloc[-1] >= 1
    
    price = close.iloc[-1]
    prev = close.shift(1).iloc[-1]
    change = (price - prev) / prev * 100
    
    score = 0
    if has_ma: score += 3
    if money_streak: score += 3
    if 1.2 < v.iloc[-1] < 3: score += 2
    
    can_buy = has_ma and money_streak and 1.2 < v.iloc[-1] < 3
    
    return {'code': code, 'name': get_name(code), 'price': price, 'change': change, 'vol_ratio': v.iloc[-1], 'score': score, 'can_buy': can_buy, 'ma': has_ma, 'money': money_streak}

def run_scan():
    """扫描选股"""
    fetcher = SmartDataFetcher()
    print("🔍 扫描候选股票 (实时)...")
    candidates = []
    
    for code in WATCH_LIST:
        try:
            df = fetcher.get_stock_data(code, days=25)
            result = analyze_stock(code, df)
            
            # 更新实时价格
            rt = get_realtime_price(code)
            if rt and rt['price'] > 0:
                result['price'] = rt['price']
                result['change'] = (rt['price'] - rt['open']) / rt['open'] * 100
            
            if result and result['can_buy']:
                candidates.append(result)
                print(f"  ✅ {code}: {result['name']} {result['price']:.2f} ({result['change']:+.1f}%)")
        except Exception as e:
            print(f"  ❌ {code}: {e}")
    
    print(f"共{len(candidates)}只符合")
    return candidates

def check_positions():
    """检查持仓"""
    if not ('09:35' <= datetime.now().strftime('%H:%M') <= '11:30' or '13:00' <= datetime.now().strftime('%H:%M') <= '14:57'):
        print("⏰ 非交易时段")
        return []
    
    data = load_data()
    fetcher = SmartDataFetcher()
    alerts = []
    now = datetime.now()
    
    for p in list(data['positions']):
        try:
            df = fetcher.get_stock_data(p['code'], days=10)
            if df is None: continue
            
            price = df['close'].iloc[-1]
            p['last_price'] = price
            
            # 实时价格更新
            rt = get_realtime_price(p['code'])
            if rt: price = rt['price']
            
            # 止损
            if price <= p['stop_loss']:
                alerts.append(('SELL', p['code'], price, f"止损"))
                data['positions'].remove(p)
                continue
            
            # 持有2天卖出
            entry = datetime.strptime(p['entry_time'], '%Y-%m-%d %H:%M')
            if (now - entry).days >= 2:
                alerts.append(('SELL', p['code'], price, f"持有2天"))
                data['positions'].remove(p)
                continue
            
        except: continue
    
    save_data(data)
    return alerts

def get_advanced_indicators(code):
    """获取高级技术指标"""
    try:
        df = DataFetcher().get_stock_data(code, days=60)
        if df is None: return None
        
        close = df['close']
        
        # MACD
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9).mean()
        
        # KDJ
        low_9 = df['low'].rolling(9).min()
        high_9 = df['high'].rolling(9).max()
        rsv = (close - low_9) / (high_9 - low_9) * 100
        k = rsv.ewm(span=3).mean()
        
        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + gain / loss))
        
        return {
            'macd': '🔴金叉' if dif.iloc[-1] > dea.iloc[-1] else '🔵死叉',
            'kdj': '⚠️超买' if k.iloc[-1] > 80 else '✅超卖' if k.iloc[-1] < 20 else '正常',
            'rsi': '⚠️超买' if rsi.iloc[-1] > 70 else '✅超卖' if rsi.iloc[-1] < 30 else '正常',
            'rsi_val': rsi.iloc[-1],
            'k_val': k.iloc[-1]
        }
    except:
        return None

def generate_report():
    """生成报告 - 洪福齐天模板"""
    import numpy as np
    
    data = load_data()
    now = datetime.now()
    
    # 股票名称映射
    name_map = {
        '600971': '恒源煤电', '600188': '兖矿能源', '600395': '盘江股份',
        '600893': '中航重机', '002594': '比亚迪', '300750': '宁德时代',
        '002466': '中际旭创', '688111': '华大九天', '688169': '芯原股份',
        '688400': '慧智微', '688041': '英杰电气', '002410': '广联达',
        '002230': '科大讯飞', '301029': '怡和嘉业', '688395': '埃斯顿',
        '601012': '隆基绿能', '600438': '通威股份', '600900': '长江电力'
    }
    
    alerts = []
    alert_num = 1
    
    # 获取候选股票数据
    candidates = data.get('positions', [])
    
    for p in candidates:
        code = p.get('symbol', p.get('code', ''))
        name = name_map.get(code, code)
        
        # 计算各项指标
        entry_price = float(p.get('entry_price', 0))
        current_price = float(p.get('current_price', entry_price))
        change_pct = float(p.get('current_change', 0))
        score = p.get('score', 0)
        signals = p.get('current_signals', [])
        
        # 计算评分
        trend_score = min(score * 4, 40)
        momentum_score = min(score * 3.5, 35)
        volume_score = 5 if '放量' in str(signals) else 2
        quality_score = 5 if '资金流入' in str(signals) else 2
        
        # 止损和目标价
        stop_loss = float(p.get('stop_loss', entry_price * 0.98))
        take_profit = float(p.get('take_profit', entry_price * 1.05))
        
        # 生成买入信号描述
        buy_signals = []
        if '多头排列' in str(signals): buy_signals.append('多头排列')
        if '资金流入' in str(signals): buy_signals.append('资金流入')
        if 'MACD金叉' in str(signals): buy_signals.append('MACD金叉')
        if '放量突破' in str(signals): buy_signals.append('放量突破')
        
        # 风险提示
        risks = []
        if abs(change_pct) > 7: risks.append(f'涨幅较大({change_pct:.1f}%)')
        if len(signals) < 3: risks.append('信号较少')
        
        # 生成预警
        alert = f"""🚨 [洪福齐天量化预警] #{alert_num}/{len(candidates)}

📈 sh{code} ({name}) 
⭐ 综合评分: {score*10}/10 | 置信度: {min(70 + score*2, 95)}%
🎯 策略: 趋势跟踪 | 风险等级: {'高' if change_pct > 5 else '中等'}

📊 得分构成:
 ├─ 趋势: {trend_score:.1f}分
 ├─ 动量: {momentum_score:.1f}分
 ├─ 成交量: {volume_score:.1f}分
 └─ 质量: {quality_score:.1f}分

✅ 买入信号:
{' | '.join(buy_signals) if buy_signals else '待观察'}

⚠️ 风险提示:
{', '.join(risks) if risks else '无明显风险'}

💰 价格信息:
 当前: ¥{current_price:.2f} | 止损: ¥{stop_loss:.2f}
 目标: ¥{take_profit:.2f} (+{((take_profit/current_price)-1)*100:.0f}%)

📈 技术指标:
 涨跌幅: {change_pct:+.2f}% | 持仓天数: {p.get('days_held', 0)}天

💡 交易建议:
 📅 持有周期: 3-7天
 ⏰ 入场时机: 开盘30分钟或收盘前30分钟
 🚪 出场策略: 移动止盈，跌破止损离场
 💼 最大仓位: 25%
"""
        alerts.append(alert)
        alert_num += 1
    
    # 如果没有候选，生成观察池报告
    if not alerts:
        alerts.append("📊 洪福齐天量化系统\n\n当前无触发买入信号的股票，观察池保持监控。\n\n⏰ 运行时间: " + now.strftime('%Y-%m-%d %H:%M'))
    
    # 合并所有预警
    full_report = '\n\n---\n\n'.join(alerts)
    full_report += f"\n\n⏰ {now.strftime('%H:%M')} | 红中🀄 | 策略:V6.2"
    
    # 返回纯文本格式（用于邮件）
    return full_report

# CLI
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['scan','check','status','report'])
    args = parser.parse_args()
    
    if args.action == 'scan':
        run_scan()
    elif args.action == 'check':
        alerts = check_positions()
        for a in alerts:
            print(f"{a[0]}: {a[1]} {a[3]}")
    elif args.action == 'status':
        data = load_data()
        print(f"持仓: {len(data['positions'])}只")
        for p in data['positions']:
            print(f"  {p['code']}: {p['entry_price']} -> {p['last_price']}")
    elif args.action == 'report':
        send_notify("白板V6.2", generate_report())


# === 快速筛选模块 ===
EXPANDED_POOL = [
    '600188','600971','600395','601001','600225','600121','600483',
    '600900','600795','600011','601991','600025','600027',
    '600036','601398','601988','601318','601166',
    '600519','000858','000568','600809',
    '601012','600438','002129','300750','002594','002460','002311',
    '688041','688111','688400','688169','300059','300033',
    '600893','600879','600862','600038','600316',
    '002410','002230','301029','300024','300567',
]

def quick_filter(min_change=2.0, max_stocks=10):
    """快速筛选活跃股票"""
    active = []
    for code in EXPANDED_POOL:
        rt = get_realtime_price(code)
        if rt and rt['price'] > 0:
            change = (rt['price'] - rt['open']) / rt['open'] * 100
            if abs(change) >= min_change:
                active.append({'code': code, 'price': rt['price'], 'change': change})
    
    active.sort(key=lambda x: abs(x['change']), reverse=True)
    return active[:max_stocks]

def run_quick_scan():
    """快速扫描 - 收盘前35分钟用"""
    print("⚡ 快速筛选活跃股票...")
    
    # 1. 快速获取涨跌幅排行
    active = quick_filter(min_change=1.5, max_stocks=15)
    
    if not active:
        print("  没有符合条件的活跃股票")
        return []
    
    print(f"  筛选出{len(active)}只活跃股票: {[s['code'] for s in active]}")
    
    # 2. 只对活跃股票进行技术分析
    fetcher = SmartDataFetcher()
    candidates = []
    
    for s in active:
        try:
            df = fetcher.get_stock_data(s['code'], days=25)
            result = analyze_stock(s['code'], df)
            
            # 更新为实时价格
            rt = get_realtime_price(s['code'])
            if rt:
                result['price'] = rt['price']
                result['change'] = (rt['price'] - rt['open']) / rt['open'] * 100
            
            if result and result['can_buy']:
                candidates.append(result)
                print(f"  ✅ {s['code']}: {result['name']} 符合买入")
        except Exception as e:
            print(f"  ❌ {s['code']}: {e}")
    
    return candidates

