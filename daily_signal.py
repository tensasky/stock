#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票分析器 - 每日推送版
V4策略：买入分≥6 + 板块联动 + 止盈止损提醒
"""

import sys
import os
import time
import json

# 设置路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import DataFetcher
from notifier import DiscordNotifier, load_config

# 板块映射
SECTOR_MAP = {
    '600519': '白酒', '600036': '银行', '601318': '保险', '600900': '电力',
    '600188': '煤炭', '600971': '煤炭', '600395': '煤炭', '601012': '光伏',
    '002594': '新能源车', '300750': '锂电池', '688041': 'AI芯片', '688111': 'AI芯片',
    '300751': 'AI应用', '600893': '军工', '600879': '军工', '002410': '机器人',
}


def calculate_indicators(df):
    """简化指标计算"""
    import pandas as pd
    import numpy as np
    
    # 均线
    ma5 = df['close'].rolling(5).mean()
    ma10 = df['close'].rolling(10).mean()
    ma20 = df['close'].rolling(20).mean()
    multi_align = (ma5 > ma10) & (ma10 > ma20)
    
    # MACD
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    macd_hist = (dif - dea) * 2
    macd_red = macd_hist > 0
    
    # 资金流向
    price_up = df['close'] > df['close'].shift(1)
    vol_up = df['volume'] > df['volume'].shift(1)
    money_in = price_up & vol_up
    money_streak = money_in.rolling(2).sum() >= 1
    
    vol_ma20 = df['volume'].rolling(20).mean()
    big_order = (df['volume'] > vol_ma20 * 1.3) & price_up
    
    latest = df.iloc[-1]
    
    return {
        'price': latest['close'],
        'multi_alignment': multi_align.iloc[-1],
        'money_streak': money_streak.iloc[-1],
        'big_order': big_order.iloc[-1],
        'macd_red': macd_red.iloc[-1],
    }


def analyze_stock(symbol, fetcher):
    """分析单只股票"""
    df = fetcher.get_stock_data(symbol, days=60)
    if df is None or len(df) < 30:
        return None
    
    ind = calculate_indicators(df)
    
    score = 0
    signals = []
    
    # 核心信号
    if ind['multi_alignment']:
        score += 3
        signals.append('多头排列')
    
    if ind['money_streak']:
        score += 3
        signals.append('资金连续流入')
    
    if ind['big_order']:
        score += 2
        signals.append('大单流入')
    
    if ind['macd_red']:
        score += 1
        signals.append('MACD翻红')
    
    return {
        'symbol': symbol,
        'sector': SECTOR_MAP.get(symbol, '其他'),
        'price': ind['price'],
        'score': score,
        'signals': signals,
    }


def run_daily_analysis():
    """每日分析并推送"""
    print("=" * 60)
    print("📊 股票信号分析 V4")
    print("=" * 60)
    
    stocks = [
        '600519', '600036', '601318', '600900', '600188',
        '600971', '600395', '601012', '002594', '300750',
        '688041', '688111', '300751', '600893', '600879', '002410'
    ]
    
    fetcher = DataFetcher()
    results = []
    
    print("\n分析中...")
    for symbol in stocks:
        try:
            result = analyze_stock(symbol, fetcher)
            if result:
                results.append(result)
                time.sleep(0.5)
        except Exception as e:
            print(f"  {symbol}: 错误")
            continue
    
    # 板块统计
    sector_counts = {}
    for r in results:
        sector = r['sector']
        if r['score'] >= 4:  # 板块强势门槛
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
    
    # 找出强势板块
    strong_sectors = [s for s, c in sector_counts.items() if c >= 2]
    
    # 筛选强势信号
    strong_signals = [r for r in results if r['score'] >= 6]
    
    # 输出结果
    print(f"\n📈 强势信号 (买入≥6分): {len(strong_signals)} 只")
    
    if strong_signals:
        for s in strong_signals:
            sector_flag = '🔥' if s['sector'] in strong_sectors else ''
            print(f"  {s['symbol']} ({s['sector']}) {sector_flag}: {s['score']}分 - {', '.join(s['signals'])}")
    
    print(f"\n🔥 强势板块: {strong_sectors if strong_sectors else '无'}")
    
    # 发送到Discord
    config = load_config()
    notifier = DiscordNotifier(webhook_url=config.discord_webhook)
    
    if strong_signals:
        # 构建消息
        title = f"📈 股票信号 V4 ({len(strong_signals)}只)"
        
        fields = []
        for s in strong_signals[:5]:
            sector_flag = '🔥' if s['sector'] in strong_sectors else ''
            fields.append({
                'name': f"{s['symbol']} ({s['sector']}) {sector_flag}",
                'value': f"得分: {s['score']}\n{', '.join(s['signals'])}",
                'inline': True
            })
        
        embed = {
            'title': title,
            'color': 0x00FF00,
            'fields': fields,
            'footer': {'text': f'强势板块: {", ".join(strong_sectors) if strong_sectors else "无"}'},
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        
        notifier.send("📊 每日股票信号推送", embed)
        print("\n✅ 已发送到Discord")
    else:
        notifier.send("📊 今日无强势信号")
        print("\n📊 已发送无信号通知")


if __name__ == "__main__":
    run_daily_analysis()
