#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票分析器 - 技术指标计算模块
支持: MACD, KDJ, BOLL, RSI, 均线, 量能, 量比
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """技术指标计算"""
    
    def __init__(self, df: pd.DataFrame):
        """
        初始化
        
        Args:
            df: 必须包含 columns: open, close, high, low, volume
        """
        self.df = df.copy()
        self._validate_data()
    
    def _validate_data(self):
        """验证数据完整性"""
        required_cols = ['open', 'close', 'high', 'low', 'volume']
        missing = [c for c in required_cols if c not in self.df.columns]
        if missing:
            raise ValueError(f"缺少必要列: {missing}")
        
        # 删除无效行
        self.df = self.df.dropna(subset=['close', 'volume'])
        self.df = self.df[self.df['volume'] > 0]
    
    # ==================== 均线 ====================
    
    def sma(self, period: int = 20) -> pd.Series:
        """简单移动平均线 SMA"""
        return self.df['close'].rolling(window=period).mean()
    
    def ema(self, period: int = 12) -> pd.Series:
        """指数移动平均线 EMA"""
        return self.df['close'].ewm(span=period, adjust=False).mean()
    
    def ma_system(self) -> pd.DataFrame:
        """均线系统 (5, 10, 20, 30, 60, 120, 250)"""
        periods = [5, 10, 20, 30, 60, 120, 250]
        result = {}
        for p in periods:
            result[f'ma{p}'] = self.sma(p)
        
        df = pd.DataFrame(result)
        
        # 均线方向 (1=上升, -1=下降, 0=持平)
        for p in periods:
            col = f'ma{p}'
            df[f'{col}_dir'] = np.where(df[col] > df[col].shift(1), 1,
                                       np.where(df[col] < df[col].shift(1), -1, 0))
        
        # 金叉/死叉信号
        df['golden_cross'] = (df['ma5'] > df['ma10']) & (df['ma5'].shift(1) <= df['ma10'].shift(1))
        df['death_cross'] = (df['ma5'] < df['ma10']) & (df['ma5'].shift(1) >= df['ma10'].shift(1))
        
        return df
    
    # ==================== MACD ====================
    
    def macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """
        MACD 指标
        
        Returns:
            dif: DIF线 (EMA12 - EMA26)
            dea: DEA线 (DIF的9日EMA)
            macd: 柱状图 (DIF - DEA) * 2
        """
        ema_fast = self.df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = self.df['close'].ewm(span=slow, adjust=False).mean()
        
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, adjust=False).mean()
        macd = (dif - dea) * 2
        
        return pd.DataFrame({
            'macd_dif': dif,
            'macd_dea': dea,
            'macd_hist': macd,
            'macd_golden': (dif > dea) & (dif.shift(1) <= dea.shift(1)),  # 金叉
            'macd_death': (dif < dea) & (dif.shift(1) >= dea.shift(1))     # 死叉
        })
    
    # ==================== KDJ ====================
    
    def kdj(self, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
        """
        KDJ 指标
        
        Args:
            n: RSV周期
            m1: K平滑
            m2: D平滑
        """
        low_n = self.df['low'].rolling(window=n).min()
        high_n = self.df['high'].rolling(window=n).max()
        
        rsv = (self.df['close'] - low_n) / (high_n - low_n) * 100
        rsv = rsv.fillna(50)
        
        k = rsv.ewm(com=m1-1, adjust=False).mean()
        d = k.ewm(com=m2-1, adjust=False).mean()
        j = 3 * k - 2 * d
        
        return pd.DataFrame({
            'kdj_k': k,
            'kdj_d': d,
            'kdj_j': j,
            'kdj_golden': (k > d) & (k.shift(1) <= d.shift(1)),   # 金叉
            'kdj_death': (k < d) & (k.shift(1) >= d.shift(1)),     # 死叉
            'kdj_oversold': k < 20,    # 超卖
            'kdj_overbought': k > 80   # 超买
        })
    
    # ==================== RSI ====================
    
    def rsi(self, period: int = 14) -> pd.DataFrame:
        """RSI 相对强弱指标"""
        delta = self.df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        # 使用EMA方式更准确
        avg_gain = gain.ewm(span=period, adjust=False).mean()
        avg_loss = loss.ewm(span=period, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return pd.DataFrame({
            'rsi': rsi,
            'rsi_oversold': rsi < 30,
            'rsi_overbought': rsi > 70,
            'rsi_rising': rsi > rsi.shift(1),
            'rsi_falling': rsi < rsi.shift(1)
        })
    
    # ==================== BOLL ====================
    
    def boll(self, period: int = 20, std_dev: int = 2) -> pd.DataFrame:
        """BOLL 布林带指标"""
        sma = self.df['close'].rolling(window=period).mean()
        std = self.df['close'].rolling(window=period).std()
        
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        bandwidth = (upper - lower) / sma
        bbi = (self.df['close'] - lower) / (upper - lower)  # %B
        
        return pd.DataFrame({
            'boll_upper': upper,
            'boll_mid': sma,
            'boll_lower': lower,
            'boll_bandwidth': bandwidth,
            'boll_bb': bbi,
            'boll_breakup': self.df['close'] > upper,   # 突破上轨
            'boll_breakdown': self.df['close'] < lower  # 突破下轨
        })
    
    # ==================== 量能 ====================
    
    def volume_indicators(self) -> pd.DataFrame:
        """量能指标"""
        vol = self.df['volume']
        
        # 成交量均线
        vol_ma5 = vol.rolling(window=5).mean()
        vol_ma10 = vol.rolling(window=10).mean()
        vol_ma20 = vol.rolling(window=20).mean()
        
        # 量比
        vol_ave = vol.rolling(window=5).mean()
        volume_ratio = vol / vol_ave
        
        # 量价齐升
        price_up = self.df['close'] > self.df['close'].shift(1)
        vol_up = vol > vol.shift(1)
        
        # 放量/缩量
        vol_ma20_ratio = vol / vol_ma20
        
        return pd.DataFrame({
            'vol': vol,
            'vol_ma5': vol_ma5,
            'vol_ma10': vol_ma10,
            'vol_ma20': vol_ma20,
            'vol_ratio': volume_ratio,
            'vol_ma20_ratio': vol_ma20_ratio,
            'vol_price_up': price_up & vol_up,  # 量价齐升
            'vol_increase': vol > vol.shift(1),  # 放量
            'vol_decrease': vol < vol.shift(1)  # 缩量
        })
    
    # ==================== 综合分析 ====================
    
    def calculate_all(self) -> pd.DataFrame:
        """计算所有指标"""
        logger.info("开始计算技术指标...")
        
        # 基础数据
        result = self.df.copy()
        
        # 均线系统
        ma_df = self.ma_system()
        for col in ma_df.columns:
            result[col] = ma_df[col].values
        
        # MACD
        macd_df = self.macd()
        for col in macd_df.columns:
            result[col] = macd_df[col].values
        
        # KDJ
        kdj_df = self.kdj()
        for col in kdj_df.columns:
            result[col] = kdj_df[col].values
        
        # RSI
        rsi_df = self.rsi()
        for col in rsi_df.columns:
            result[col] = rsi_df[col].values
        
        # BOLL
        boll_df = self.boll()
        for col in boll_df.columns:
            result[col] = boll_df[col].values
        
        # 量能
        vol_df = self.volume_indicators()
        for col in vol_df.columns:
            result[col] = vol_df[col].values
        
        logger.info(f"技术指标计算完成，共 {len(result)} 条记录")
        return result
    
    # ==================== 信号提取 ====================
    
    def extract_signals(self) -> Dict:
        """提取当前信号"""
        df = self.calculate_all()
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else None
        
        signals = {
            'datetime': str(latest['date']),
            'price': float(latest['close']),
            'signals': []
        }
        
        # MACD信号
        if latest.get('macd_golden', False):
            signals['signals'].append({'type': 'MACD金叉', 'strength': 1})
        if latest.get('macd_death', False):
            signals['signals'].append({'type': 'MACD死叉', 'strength': -1})
        
        # KDJ信号
        if latest.get('kdj_golden', False):
            signals['signals'].append({'type': 'KDJ金叉', 'strength': 1})
        if latest.get('kdj_death', False):
            signals['signals'].append({'type': 'KDJ死叉', 'strength': -1})
        if latest.get('kdj_oversold', False):
            signals['signals'].append({'type': 'KDJ超卖', 'strength': 1})
        if latest.get('kdj_overbought', False):
            signals['signals'].append({'type': 'KDJ超买', 'strength': -1})
        
        # RSI信号
        if latest.get('rsi_oversold', False):
            signals['signals'].append({'type': 'RSI超卖', 'strength': 1})
        if latest.get('rsi_overbought', False):
            signals['signals'].append({'type': 'RSI超买', 'strength': -1})
        
        # BOLL信号
        if latest.get('boll_breakup', False):
            signals['signals'].append({'type': 'BOLL突破上轨', 'strength': 1})
        if latest.get('boll_breakdown', False):
            signals['signals'].append({'type': 'BOLL突破下轨', 'strength': -1})
        
        # 均线信号
        if latest.get('golden_cross', False):
            signals['signals'].append({'type': '均线金叉', 'strength': 1})
        if latest.get('death_cross', False):
            signals['signals'].append({'type': '均线死叉', 'strength': -1})
        
        # 量能信号
        if latest.get('vol_price_up', False):
            signals['signals'].append({'type': '量价齐升', 'strength': 1})
        if latest.get('vol_increase', False) and latest.get('rsi_rising', False):
            signals['signals'].append({'type': '放量上涨', 'strength': 1})
        
        # 计算综合得分
        if signals['signals']:
            signals['score'] = sum(s['strength'] for s in signals['signals'])
        else:
            signals['score'] = 0
        
        return signals


def test_indicators():
    """测试指标计算"""
    from data_fetcher import DataFetcher
    
    fetcher = DataFetcher()
    df = fetcher.get_stock_data('600519', days=60)  # 茅台
    
    if df is not None:
        ti = TechnicalIndicators(df)
        signals = ti.extract_signals()
        
        print("\n" + "="*50)
        print(f"股票: 600519 (茅台)")
        print(f"当前价格: {signals['price']}")
        print(f"信号数量: {len(signals['signals'])}")
        print(f"综合得分: {signals['score']}")
        print("\n信号列表:")
        for s in signals['signals']:
            print(f"  - {s['type']}: {s['strength']}")
    else:
        print("获取数据失败")


if __name__ == "__main__":
    test_indicators()
