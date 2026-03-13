#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票分析器 - 技术指标计算模块 V2
优化版：增加涨停基因、资金流向、板块强度等信号
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional, List
import logging

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """技术指标计算 V2"""
    
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
    
    # ==================== 均线 ====================
    
    def sma(self, period: int = 20) -> pd.Series:
        return self.df['close'].rolling(window=period).mean()
    
    def ema(self, period: int = 12) -> pd.Series:
        return self.df['close'].ewm(span=period, adjust=False).mean()
    
    def ma_system(self) -> pd.DataFrame:
        periods = [5, 10, 20, 30, 60]
        result = {}
        for p in periods:
            result[f'ma{p}'] = self.sma(p)
        
        df = pd.DataFrame(result)
        
        # 均线方向
        for p in periods:
            col = f'ma{p}'
            df[f'{col}_dir'] = np.where(df[col] > df[col].shift(1), 1,
                                       np.where(df[col] < df[col].shift(1), -1, 0))
        
        # 金叉/死叉
        df['golden_cross'] = (df['ma5'] > df['ma10']) & (df['ma5'].shift(1) <= df['ma10'].shift(1))
        df['death_cross'] = (df['ma5'] < df['ma10']) & (df['ma5'].shift(1) >= df['ma10'].shift(1))
        
        # 多头排列 (5>10>20>30)
        df['multi_alignment'] = (df['ma5'] > df['ma10']) & (df['ma10'] > df['ma20']) & (df['ma20'] > df['ma30'])
        
        return df
    
    # ==================== MACD ====================
    
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
            'macd_death': (dif < dea) & (dif.shift(1) >= dea.shift(1)),
            'macd_turn_up': (macd > 0) & (macd.shift(1) < 0),  # MACD翻红
            'macd_turn_down': (macd < 0) & (macd.shift(1) > 0),  # MACD翻绿
        })
    
    # ==================== KDJ ====================
    
    def kdj(self, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
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
            'kdj_golden': (k > d) & (k.shift(1) <= d.shift(1)),
            'kdj_death': (k < d) & (k.shift(1) >= d.shift(1)),
            'kdj_oversold': k < 20,
            'kdj_overbought': k > 80,
            'kdj_bottom_flip': (j < 20) & (j.shift(1) < j),  # J值底部反转
        })
    
    # ==================== RSI ====================
    
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
            'rsi_oversold': rsi < 30,
            'rsi_overbought': rsi > 70,
            'rsi_rising': rsi > rsi.shift(1),
            'rsi_bottom': (rsi < 35) & (rsi.shift(1) < rsi),  # RSI底部反转
        })
    
    # ==================== BOLL ====================
    
    def boll(self, period: int = 20, std_dev: int = 2) -> pd.DataFrame:
        sma = self.df['close'].rolling(window=period).mean()
        std = self.df['close'].rolling(window=period).std()
        
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        bandwidth = (upper - lower) / sma
        bbi = (self.df['close'] - lower) / (upper - lower)
        
        return pd.DataFrame({
            'boll_upper': upper,
            'boll_mid': sma,
            'boll_lower': lower,
            'boll_bandwidth': bandwidth,
            'boll_bb': bbi,
            'boll_breakup': self.df['close'] > upper,
            'boll_breakdown': self.df['close'] < lower,
            'boll_squeeze': bandwidth < bandwidth.rolling(20).mean() * 0.8,  # 布林带收口
        })
    
    # ==================== 量能 ====================
    
    def volume_indicators(self) -> pd.DataFrame:
        vol = self.df['volume']
        
        vol_ma5 = vol.rolling(window=5).mean()
        vol_ma10 = vol.rolling(window=10).mean()
        vol_ma20 = vol.rolling(window=20).mean()
        
        volume_ratio = vol / vol_ma5
        vol_ma20_ratio = vol / vol_ma20
        
        price_up = self.df['close'] > self.df['close'].shift(1)
        vol_up = vol > vol.shift(1)
        
        # 量能突破 (放量突破20日均量)
        vol_breakout = (vol > vol_ma20 * 1.5) & (self.df['close'] > self.df['close'].rolling(20).mean())
        
        return pd.DataFrame({
            'vol': vol,
            'vol_ma5': vol_ma5,
            'vol_ma10': vol_ma10,
            'vol_ma20': vol_ma20,
            'vol_ratio': volume_ratio,
            'vol_ma20_ratio': vol_ma20_ratio,
            'vol_price_up': price_up & vol_up,
            'vol_increase': vol > vol.shift(1),
            'vol_decrease': vol < vol.shift(1),
            'vol_breakout': vol_breakout,
        })
    
    # ==================== 涨停基因 (新增) ====================
    
    def limit_up_gene(self, days: int = 20) -> pd.DataFrame:
        """涨停基因：过去N天内有涨停的股票更容易再涨停"""
        # 假设涨停是当日涨幅 > 9.5%
        daily_change = (self.df['close'] - self.df['open']) / self.df['open'] * 100
        
        # 过去N天内的涨停次数
        limit_up_count = (daily_change > 9.5).rolling(window=days).sum()
        
        # 近期有过涨停
        recent_limit_up = (daily_change > 9.5).rolling(window=5).sum() > 0
        
        # 涨停后回调企稳 (涨停后连续调整2-3天)
        was_limit_up = daily_change > 9.5
        after_consolidation = was_limit_up.shift(1) | was_limit_up.shift(2)
        
        return pd.DataFrame({
            'limit_up_count': limit_up_count,
            'recent_limit_up': recent_limit_up,
            'limit_up_after_consolidation': after_consolidation & (daily_change > 0),
        })
    
    # ==================== 资金流向 (新增) ====================
    
    def money_flow(self) -> pd.DataFrame:
        """资金流向：判断资金是流入还是流出"""
        # 简单判断：收阳且放量 = 资金流入，收阴且放量 = 资金流出
        price_change = self.df['close'] - self.df['open']
        vol_change = self.df['volume'] - self.df['volume'].shift(1)
        
        # 主力资金流入 (收阳+放量 或 收跌但量能萎缩)
        money_in = ((price_change > 0) & (vol_change > 0)) | ((price_change < 0) & (vol_change < 0))
        
        # 连续资金流入
        money_in_streak = money_in.rolling(window=3).sum() >= 2
        
        # 大单净流入 (量比 > 1.5)
        vol_ratio = self.df['volume'] / self.df['volume'].rolling(5).mean()
        big_order_in = (vol_ratio > 1.5) & (price_change > 0)
        
        return pd.DataFrame({
            'money_in': money_in,
            'money_in_streak': money_in_streak,
            'big_order_in': big_order_in,
            'vol_ratio_5': vol_ratio,
        })
    
    # ==================== 形态信号 (新增) ====================
    
    def patterns(self) -> pd.DataFrame:
        """形态分析"""
        # 早晨之星 (见底信号)
        yesterday = self.df['close'].shift(1) < self.df['open'].shift(1)  # 昨天收阴
        today_open = self.df['open'] < self.df['close']  # 今天收阳
        yesterday_shadow = (self.df['high'].shift(1) - self.df['close'].shift(1)) > (self.df['close'].shift(1) - self.df['low'].shift(1))  # 上影线
        
        # 突破新高
        new_high = self.df['close'] > self.df['high'].rolling(20).max().shift(1)
        
        # 均线支撑
        ma10 = self.df['close'].rolling(10).mean()
        near_ma10 = abs(self.df['close'] - ma10) / ma10 < 0.02
        
        return pd.DataFrame({
            'morning_star': yesterday & today_open,
            'new_high': new_high,
            'near_ma10': near_ma10,
        })
    
    # ==================== 综合分析 ====================
    
    def calculate_all(self) -> pd.DataFrame:
        logger.info("开始计算技术指标 V2...")
        
        result = self.df.copy()
        
        # 均线
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
        
        # 涨停基因
        limit_df = self.limit_up_gene()
        for col in limit_df.columns:
            result[col] = limit_df[col].values
        
        # 资金流向
        flow_df = self.money_flow()
        for col in flow_df.columns:
            result[col] = flow_df[col].values
        
        # 形态
        pattern_df = self.patterns()
        for col in pattern_df.columns:
            result[col] = pattern_df[col].values
        
        logger.info(f"技术指标计算完成，共 {len(result)} 条记录")
        return result
    
    # ==================== 信号提取 (优化版) ====================
    
    def extract_signals_v2(self) -> Dict:
        """提取优化版信号"""
        df = self.calculate_all()
        latest = df.iloc[-1]
        
        signals = {
            'datetime': str(latest['date']),
            'price': float(latest['close']),
            'signals': [],
            'signal_details': []
        }
        
        # ===== 核心信号 (权重高) =====
        
        # MACD
        if latest.get('macd_golden', False):
            signals['signals'].append({'type': 'MACD金叉', 'strength': 2})
            signals['signal_details'].append('MACD金叉')
        if latest.get('macd_turn_up', False):
            signals['signals'].append({'type': 'MACD翻红', 'strength': 2})
            signals['signal_details'].append('MACD翻红')
        
        # KDJ
        if latest.get('kdj_golden', False):
            signals['signals'].append({'type': 'KDJ金叉', 'strength': 1})
            signals['signal_details'].append('KDJ金叉')
        if latest.get('kdj_oversold', False) and latest.get('kdj_bottom_flip', False):
            signals['signals'].append({'type': 'KDJ超卖反弹', 'strength': 2})
            signals['signal_details'].append('KDJ超卖反弹')
        
        # RSI
        if latest.get('rsi_bottom', False):
            signals['signals'].append({'type': 'RSI底部反转', 'strength': 2})
            signals['signal_details'].append('RSI底部反转')
        
        # 均线
        if latest.get('golden_cross', False):
            signals['signals'].append({'type': '均线金叉', 'strength': 1})
            signals['signal_details'].append('均线金叉')
        if latest.get('multi_alignment', False):
            signals['signals'].append({'type': '多头排列', 'strength': 2})
            signals['signal_details'].append('多头排列')
        
        # ===== 强势信号 =====
        
        # 涨停基因
        if latest.get('recent_limit_up', False):
            signals['signals'].append({'type': '近期涨停过', 'strength': 1})
            signals['signal_details'].append('近期涨停过')
        if latest.get('limit_up_count', 0) >= 2:
            signals['signals'].append({'type': '多次涨停基因', 'strength': 2})
            signals['signal_details'].append('多次涨停基因')
        
        # 资金流向
        if latest.get('money_in_streak', False):
            signals['signals'].append({'type': '资金连续流入', 'strength': 2})
            signals['signal_details'].append('资金连续流入')
        if latest.get('big_order_in', False):
            signals['signals'].append({'type': '大单流入', 'strength': 2})
            signals['signal_details'].append('大单流入')
        
        # 量价配合
        if latest.get('vol_price_up', False):
            signals['signals'].append({'type': '量价齐升', 'strength': 1})
            signals['signal_details'].append('量价齐升')
        if latest.get('vol_breakout', False):
            signals['signals'].append({'type': '量能突破', 'strength': 2})
            signals['signal_details'].append('量能突破')
        
        # 形态
        if latest.get('new_high', False):
            signals['signals'].append({'type': '突破新高', 'strength': 2})
            signals['signal_details'].append('突破新高')
        if latest.get('morning_star', False):
            signals['signals'].append({'type': '早晨之星', 'strength': 3})
            signals['signal_details'].append('早晨之星')
        
        # ===== 综合得分 =====
        if signals['signals']:
            signals['score'] = sum(s['strength'] for s in signals['signals'])
        else:
            signals['score'] = 0
        
        # 高置信度信号 (得分 >= 4)
        signals['high_confidence'] = signals['score'] >= 4
        
        return signals


def test_v2():
    """测试 V2 指标"""
    from data_fetcher import DataFetcher
    
    fetcher = DataFetcher()
    df = fetcher.get_stock_data('600519', days=60)
    
    if df is not None:
        ti = TechnicalIndicators(df)
        signals = ti.extract_signals_v2()
        
        print(f"\n{'='*50}")
        print(f"股票: 600519 (茅台)")
        print(f"当前价格: ¥{signals['price']}")
        print(f"信号数量: {len(signals['signals'])}")
        print(f"综合得分: {signals['score']}")
        print(f"高置信度: {signals['high_confidence']}")
        print("\n信号详情:")
        for s in signals['signals']:
            print(f"  - {s['type']}: +{s['strength']}")
    else:
        print("获取数据失败")


if __name__ == "__main__":
    test_v2()
