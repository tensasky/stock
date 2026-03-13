#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票分析器 - V3 优化版
重点：资金流向 + 多头排列 + 避免集合竞价失真
"""

import pandas as pd
import numpy as np
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class TechnicalIndicatorsV3:
    """V3 技术指标 - 优化版"""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
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
        periods = [5, 10, 20, 30, 60]
        result = {}
        for p in periods:
            result[f'ma{p}'] = self.sma(p)
        
        df = pd.DataFrame(result)
        
        # 多头排列 (5>10>20)
        df['multi_alignment'] = (df['ma5'] > df['ma10']) & (df['ma10'] > df['ma20'])
        
        # 均线金叉
        df['golden_cross'] = (df['ma5'] > df['ma10']) & (df['ma5'].shift(1) <= df['ma10'].shift(1))
        
        return df
    
    def macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        ema_fast = self.df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = self.df['close'].ewm(span=slow, adjust=False).mean()
        
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, adjust=False).mean()
        macd = (dif - dea) * 2
        
        return pd.DataFrame({
            'macd_dif': dif,
            'macd_dea': dea,
            'macd_hist': macd,
            'macd_golden': (dif > dea) & (dif.shift(1) <= dea.shift(1)),
            'macd_red': macd > 0,  # MACD翻红
        })
    
    def kdj(self, n: int = 9) -> pd.DataFrame:
        low_n = self.df['low'].rolling(window=n).min()
        high_n = self.df['high'].rolling(window=n).max()
        
        rsv = (self.df['close'] - low_n) / (high_n - low_n) * 100
        rsv = rsv.fillna(50)
        
        k = rsv.ewm(com=2, adjust=False).mean()
        d = k.ewm(com=2, adjust=False).mean()
        j = 3 * k - 2 * d
        
        return pd.DataFrame({
            'kdj_k': k,
            'kdj_d': d,
            'kdj_j': j,
            'kdj_golden': (k > d) & (k.shift(1) <= d.shift(1)),
            'kdj_oversold': (k < 20) | (j < 0),  # KDJ超卖
            'kdj_bottom': (j < 20) & (j.shift(1) < j),  # J值底部反转
        })
    
    def rsi(self, period: int = 14) -> pd.DataFrame:
        delta = self.df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.ewm(span=period, adjust=False).mean()
        avg_loss = loss.ewm(span=period, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return pd.DataFrame({
            'rsi': rsi,
            'rsi_bottom': (rsi < 35) & (rsi.shift(1) < rsi),  # RSI底部反转
        })
    
    def volume_system(self) -> pd.DataFrame:
        """量能系统"""
        vol = self.df['volume']
        vol_ma5 = vol.rolling(5).mean()
        vol_ma20 = vol.rolling(20).mean()
        
        # 资金流入判断
        price_up = self.df['close'] > self.df['close'].shift(1)
        vol_up = vol > vol.shift(1)
        money_in = (price_up & vol_up) | ((self.df['close'] < self.df['close'].shift(1)) & (vol < vol.shift(1)))
        
        # 连续资金流入 (2天内)
        money_in_streak = money_in.rolling(2).sum() >= 1
        
        # 大单流入 (放量 + 上涨)
        big_order = (vol > vol_ma20 * 1.3) & price_up
        
        return pd.DataFrame({
            'money_in': money_in,
            'money_in_streak': money_in_streak,
            'big_order_in': big_order,
            'vol_ratio': vol / vol_ma20,
        })
    
    def calculate_all(self) -> pd.DataFrame:
        result = self.df.copy()
        
        # 均线
        for col in self.ma_system().columns:
            result[col] = self.ma_system()[col].values
        
        # MACD
        for col in self.macd().columns:
            result[col] = self.macd()[col].values
        
        # KDJ
        for col in self.kdj().columns:
            result[col] = self.kdj()[col].values
        
        # RSI
        for col in self.rsi().columns:
            result[col] = self.rsi()[col].values
        
        # 量能
        for col in self.volume_system().columns:
            result[col] = self.volume_system()[col].values
        
        return result
    
    def extract_signals_v3(self) -> Dict:
        """V3 信号提取"""
        df = self.calculate_all()
        latest = df.iloc[-1]
        
        signals = {
            'price': float(latest['close']),
            'signals': [],
            'buy_score': 0,
            'sell_score': 0,
        }
        
        # ===== 买入信号 (加分) =====
        
        # 1. 多头排列 (核心信号)
        if latest.get('multi_alignment', False):
            signals['signals'].append('多头排列')
            signals['buy_score'] += 3
        
        # 2. 资金连续流入 (核心信号)
        if latest.get('money_in_streak', False):
            signals['signals'].append('资金连续流入')
            signals['buy_score'] += 3
        
        # 3. 大单流入
        if latest.get('big_order_in', False):
            signals['signals'].append('大单流入')
            signals['buy_score'] += 2
        
        # 4. MACD金叉/翻红
        if latest.get('macd_golden', False):
            signals['signals'].append('MACD金叉')
            signals['buy_score'] += 1
        if latest.get('macd_red', False):
            signals['signals'].append('MACD翻红')
            signals['buy_score'] += 1
        
        # 5. KDJ超卖反弹
        if latest.get('kdj_bottom', False):
            signals['signals'].append('KDJ超卖反弹')
            signals['buy_score'] += 2
        
        # 6. RSI底部反转
        if latest.get('rsi_bottom', False):
            signals['signals'].append('RSI底部反转')
            signals['buy_score'] += 2
        
        # 7. 均线金叉
        if latest.get('golden_cross', False):
            signals['signals'].append('均线金叉')
            signals['buy_score'] += 1
        
        # ===== 卖出信号 (减分) =====
        
        # 1. 空头排列
        if latest.get('ma5', 0) < latest.get('ma10', 0) < latest.get('ma20', 0):
            signals['signals'].append('空头排列')
            signals['sell_score'] += 3
        
        # 2. MACD死叉
        if latest.get('macd_golden', False) == False and latest.get('macd_red', False) == False:
            if df.iloc[-2].get('macd_red', True) == True:
                signals['signals'].append('MACD翻绿')
                signals['sell_score'] += 2
        
        # 3. KDJ超买
        if latest.get('kdj_k', 0) > 80:
            signals['signals'].append('KDJ超买')
            signals['sell_score'] += 2
        
        # 4. RSI超买
        if latest.get('rsi', 100) > 70:
            signals['signals'].append('RSI超买')
            signals['sell_score'] += 2
        
        # 综合评分
        signals['total_score'] = signals['buy_score'] - signals['sell_score']
        
        return signals


def test_v3():
    """测试 V3"""
    import sys
    sys.path.insert(0, '.')
    from data_fetcher import DataFetcher
    
    fetcher = DataFetcher()
    df = fetcher.get_stock_data('600519', days=60)
    
    if df:
        ti = TechnicalIndicatorsV3(df)
        signals = ti.extract_signals_v3()
        
        print(f"\n股票: 600519")
        print(f"当前价格: ¥{signals['price']}")
        print(f"买入评分: {signals['buy_score']}")
        print(f"卖出评分: {signals['sell_score']}")
        print(f"综合评分: {signals['total_score']}")
        print(f"信号: {signals['signals']}")


if __name__ == "__main__":
    test_v3()
