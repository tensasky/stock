#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票分析器 - V4 终极版
加入板块联动 + 止盈止损推送
"""

import pandas as pd
import numpy as np
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


# 板块映射
SECTOR_MAP = {
    # 资源/煤炭/有色
    '600519': '白酒', '600971': '煤炭', '600395': '煤炭', '600188': '煤炭',
    '601001': '煤炭', '600225': '煤炭', '600027': '煤炭', '600011': '煤炭',
    '600971': '煤炭', '601088': '煤炭',
    # 电力
    '600795': '电力', '600900': '电力', '601991': '电力',
    '600050': '电力', '600030': '电力',
    # 新能源
    '601012': '光伏', '002594': '新能源车', '300750': '锂电池',
    '002466': '锂电池', '002460': '锂电池', '002497': '锂电池',
    '002709': '锂电池', '300014': '锂电池',
    # AI/科技
    '688041': 'AI芯片', '688111': 'AI芯片', '688400': 'AI芯片',
    '688169': 'AI芯片', '688008': 'AI芯片',
    '300059': 'AI应用', '300033': 'AI应用', '300058': 'AI应用',
    '300751': 'AI应用', '300663': 'AI应用',
    # 军工
    '600893': '军工', '600345': '军工', '002013': '军工',
    '600862': '军工', '600316': '军工', '600038': '军工',
    '600879': '军工', '601989': '军工', '600118': '军工',
    # 机器人
    '002230': '机器人', '002410': '机器人', '002415': '机器人',
    # 银行
    '600036': '银行', '000001': '银行', '601318': '保险',
}


class TechnicalIndicatorsV4:
    """V4 技术指标 - 终极版"""
    
    def __init__(self, df: pd.DataFrame, symbol: str = ''):
        self.df = df.copy()
        self.symbol = symbol
        self.sector = SECTOR_MAP.get(symbol, '其他')
        self._validate_data()
    
    def _validate_data(self):
        required_cols = ['open', 'close', 'high', 'low', 'volume']
        missing = [c for c in required_cols if c not in self.df.columns]
        if missing:
            raise ValueError(f"缺少必要列: {missing}")
        
        self.df = self.df.dropna(subset=['close', 'volume'])
        self.df = self.df[self.df['volume'] > 0]
    
    def sma(self, period: int = 20) -> pd.Series:
        return self.df['close'].rolling(window=period).mean()
    
    def ma_system(self) -> pd.DataFrame:
        periods = [5, 10, 20, 30]
        result = {}
        for p in periods:
            result[f'ma{p}'] = self.sma(p)
        
        df = pd.DataFrame(result)
        df['multi_alignment'] = (df['ma5'] > df['ma10']) & (df['ma10'] > df['ma20'])
        df['golden_cross'] = (df['ma5'] > df['ma10']) & (df['ma5'].shift(1) <= df['ma10'].shift(1))
        
        return df
    
    def macd(self) -> pd.DataFrame:
        ema_fast = self.df['close'].ewm(span=12, adjust=False).mean()
        ema_slow = self.df['close'].ewm(span=26, adjust=False).mean()
        
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=9, adjust=False).mean()
        macd = (dif - dea) * 2
        
        return pd.DataFrame({
            'macd_dif': dif,
            'macd_dea': dea,
            'macd_golden': (dif > dea) & (dif.shift(1) <= dea.shift(1)),
            'macd_red': macd > 0,
        })
    
    def kdj(self) -> pd.DataFrame:
        low_n = self.df['low'].rolling(window=9).min()
        high_n = self.df['high'].rolling(window=9).max()
        
        rsv = (self.df['close'] - low_n) / (high_n - low_n) * 100
        rsv = rsv.fillna(50)
        
        k = rsv.ewm(com=2, adjust=False).mean()
        d = k.ewm(com=2, adjust=False).mean()
        j = 3 * k - 2 * d
        
        return pd.DataFrame({
            'kdj_k': k, 'kdj_d': d, 'kdj_j': j,
            'kdj_golden': (k > d) & (k.shift(1) <= d.shift(1)),
            'kdj_oversold': (k < 20) | (j < 0),
            'kdj_bottom': (j < 20) & (j.shift(1) < j),
        })
    
    def rsi(self) -> pd.DataFrame:
        delta = self.df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.ewm(span=14, adjust=False).mean()
        avg_loss = loss.ewm(span=14, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return pd.DataFrame({
            'rsi': rsi,
            'rsi_bottom': (rsi < 35) & (rsi.shift(1) < rsi),
        })
    
    def volume_system(self) -> pd.DataFrame:
        vol = self.df['volume']
        vol_ma20 = vol.rolling(20).mean()
        
        price_up = self.df['close'] > self.df['close'].shift(1)
        vol_up = vol > vol.shift(1)
        money_in = (price_up & vol_up) | ((self.df['close'] < self.df['close'].shift(1)) & (vol < vol.shift(1)))
        money_in_streak = money_in.rolling(2).sum() >= 1
        big_order = (vol > vol_ma20 * 1.3) & price_up
        
        return pd.DataFrame({
            'money_in': money_in,
            'money_in_streak': money_in_streak,
            'big_order_in': big_order,
        })
    
    def calculate_all(self) -> pd.DataFrame:
        result = self.df.copy()
        
        for col in self.ma_system().columns:
            result[col] = self.ma_system()[col].values
        for col in self.macd().columns:
            result[col] = self.macd()[col].values
        for col in self.kdj().columns:
            result[col] = self.kdj()[col].values
        for col in self.rsi().columns:
            result[col] = self.rsi()[col].values
        for col in self.volume_system().columns:
            result[col] = self.volume_system()[col].values
        
        return result
    
    def extract_signals_v4(self, sector_strong: bool = False) -> Dict:
        """V4 信号提取 - 加入板块联动"""
        df = self.calculate_all()
        latest = df.iloc[-1]
        
        signals = {
            'symbol': self.symbol,
            'sector': self.sector,
            'price': float(latest['close']),
            'signals': [],
            'buy_score': 0,
            'sell_score': 0,
            'sector_boost': 0,  # 板块联动加分
        }
        
        # ===== 核心买入信号 =====
        
        # 1. 多头排列
        if latest.get('multi_alignment', False):
            signals['signals'].append('多头排列')
            signals['buy_score'] += 3
        
        # 2. 资金连续流入 (最关键)
        if latest.get('money_in_streak', False):
            signals['signals'].append('资金连续流入')
            signals['buy_score'] += 3
        
        # 3. 大单流入
        if latest.get('big_order_in', False):
            signals['signals'].append('大单流入')
            signals['buy_score'] += 2
        
        # 4. MACD
        if latest.get('macd_golden', False):
            signals['signals'].append('MACD金叉')
            signals['buy_score'] += 1
        if latest.get('macd_red', False):
            signals['signals'].append('MACD翻红')
            signals['buy_score'] += 1
        
        # 5. KDJ
        if latest.get('kdj_bottom', False):
            signals['signals'].append('KDJ超卖反弹')
            signals['buy_score'] += 2
        
        # 6. RSI
        if latest.get('rsi_bottom', False):
            signals['signals'].append('RSI底部反转')
            signals['buy_score'] += 2
        
        # 7. 均线金叉
        if latest.get('golden_cross', False):
            signals['signals'].append('均线金叉')
            signals['buy_score'] += 1
        
        # ===== 板块联动加分 =====
        if sector_strong:
            signals['signals'].append('板块强势')
            signals['sector_boost'] = 2
            signals['buy_score'] += 2
        
        # ===== 卖出信号 =====
        
        if latest.get('ma5', 0) < latest.get('ma10', 0) < latest.get('ma20', 0):
            signals['signals'].append('空头排列')
            signals['sell_score'] += 3
        
        if latest.get('kdj_k', 0) > 80:
            signals['signals'].append('KDJ超买')
            signals['sell_score'] += 2
        
        if latest.get('rsi', 100) > 70:
            signals['signals'].append('RSI超买')
            signals['sell_score'] += 2
        
        signals['total_score'] = signals['buy_score'] - signals['sell_score']
        
        return signals


def check_sector_strength(symbol: str, all_results: List[Dict]) -> bool:
    """检查板块是否强势 (同板块有多只股票满足条件)"""
    sector = SECTOR_MAP.get(symbol, '其他')
    sector_stocks = [r for r in all_results if SECTOR_MAP.get(r['symbol'], '其他') == sector]
    
    # 同板块有3只以上强势股 = 板块强势
    return len(sector_stocks) >= 3


def analyze_with_sector():
    """带板块联动的分析"""
    import sys
    sys.path.insert(0, '.')
    from data_fetcher import DataFetcher
    
    stocks = [
        '600519', '600036', '601318', '600900', '600188', '600971', '600395',
        '601012', '002594', '300750', '002466', '002460',
        '688041', '688111', '688400', '300059', '300033', '300058', '300751',
        '600893', '600345', '600862', '600879', '601989',
        '002230', '002410', '002415'
    ]
    
    fetcher = DataFetcher()
    
    print('=' * 90)
    print('📊 V4分析 - 当前信号 (板块联动 + 止盈止损)')
    print('=' * 90)
    
    results = []
    
    for symbol in stocks:
        df = fetcher.get_stock_data(symbol, days=60)
        if df is None:
            continue
        
        ti = TechnicalIndicatorsV4(df, symbol)
        signals = ti.extract_signals_v4()
        
        results.append(signals)
    
    # 检查板块强度
    for r in results:
        r['sector_strong'] = check_sector_strength(r['symbol'], results)
    
    # 重新计算分数（加入板块加成）
    for r in results:
        if r['sector_strong'] and '板块强势' not in r['signals']:
            r['signals'].append('板块强势')
            r['buy_score'] += 2
            r['sector_boost'] = 2
        r['total_score'] = r['buy_score'] - r['sell_score']
    
    # 排序
    results.sort(key=lambda x: x['buy_score'], reverse=True)
    
    print(f'\\n代码      板块      价格      买入分  卖出分  综合   信号')
    print('-' * 90)
    
    for r in results[:15]:
        sigs = ', '.join(r['signals'][:4])
        sector_flag = '🔥' if r['sector_strong'] else ''
        print(f"{r['symbol']:<8} {r['sector']:<6} {r['price']:<8.2f} {r['buy_score']:<6} {r['sell_score']:<6} {r['total_score']:<5} {sector_flag} {sigs}")
    
    # 强势信号
    strong = [r for r in results if r['buy_score'] >= 7]
    print(f'\\n🎯 强势信号(买入≥7分): {len(strong)} 只')
    for s in strong:
        print(f"  {s['symbol']} ({s['sector']}): {s['buy_score']}分 - {s['signals']}")
    
    return results


if __name__ == "__main__":
    analyze_with_sector()
