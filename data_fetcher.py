#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票分析器 - 数据获取模块
支持多数据源 + 重试机制
"""

import time
import random
import requests
import pandas as pd
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/data_fetcher.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DataSource:
    """数据源基类"""
    
    def __init__(self, name: str, max_retries: int = 3, retry_delay: float = 1.0):
        self.name = name
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://finance.qq.com/'
        })
    
    def _retry_request(self, func, *args, **kwargs):
        """带重试的请求"""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # 随机延迟，避免请求过快
                time.sleep(random.uniform(0.3, 1.5) * (attempt + 1))
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                logger.warning(f"[{self.name}] 请求失败 (尝试 {attempt+1}/{self.max_retries}): {e}")
        
        raise last_error or Exception(f"请求失败 {self.max_retries} 次")
    
    def get_stock_daily(self, symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
        """获取日线数据"""
        raise NotImplementedError


class TencentQuotes(DataSource):
    """腾讯财经实时行情接口"""
    
    def __init__(self):
        super().__init__("TencentQuotes", max_retries=3)
        self.base_url = "https://qt.gtimg.cn/q="
    
    def _convert_symbol(self, symbol: str) -> str:
        """转换股票代码为腾讯格式"""
        if symbol.startswith('6'):
            return f"sh{symbol}"
        elif symbol.startswith(('3', '0')):
            return f"sz{symbol}"
        elif symbol.startswith('8') or symbol.startswith('4'):
            return f"bj{symbol}"
        return symbol
    
    def get_quote(self, symbol: str) -> Optional[Dict]:
        """获取实时行情"""
        symbol = self._convert_symbol(symbol)
        
        def _fetch():
            response = self.session.get(self.base_url + symbol, timeout=10)
            response.raise_for_status()
            
            text = response.text
            if not text or 'n/a' in text.lower():
                raise ValueError("无数据")
            
            # 解析: v_sh600519="1~股票名称~代码~..."
            import re
            match = re.search(r'v_"([^"]+)"', text)
            if not match:
                raise ValueError("解析失败")
            
            parts = match.group(1).split('~')
            if len(parts) < 50:
                raise ValueError("数据不完整")
            
            return {
                'name': parts[1],
                'symbol': parts[2],
                'price': float(parts[3]) if parts[3] else 0,
                'open': float(parts[4]) if parts[4] else 0,
                'high': float(parts[5]) if parts[5] else 0,
                'low': float(parts[6]) if parts[6] else 0,
                'volume': int(parts[7]) if parts[7] else 0,
                'amount': float(parts[8]) if parts[8] else 0,
                'buy1': float(parts[9]) if parts[9] else 0,
                'sell1': float(parts[19]) if parts[19] else 0,
                'datetime': parts[30]
            }
        
        try:
            return self._retry_request(_fetch)
        except Exception as e:
            logger.error(f"获取 {symbol} 实时行情失败: {e}")
            return None
    
    def get_stock_daily(self, symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
        """获取日线数据 - 使用K线接口"""
        symbol = self._convert_symbol(symbol)
        
        def _fetch():
            # 腾讯K线接口
            url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            params = {
                '_var': 'kline_dayqfq',
                'param': f'{symbol},day,,,{days},qfq'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            text = response.text
            import json
            start = text.find('{')
            end = text.rfind('}') + 1
            if start == -1:
                raise ValueError("无法解析数据")
            
            data = json.loads(text[start:end])
            stock_data = data.get('data', {}).get(symbol, {})
            
            if not stock_data:
                return None
            
            # 获取qfq日线
            day_data = stock_data.get('day', [])
            if not day_data:
                # 尝试获取非qfq数据
                day_data = stock_data.get('data', [])
            
            if not day_data:
                return None
            
            # 转换为DataFrame
            df = pd.DataFrame(day_data, columns=['date', 'open', 'close', 'high', 'low', 'volume'])
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            
            # 数值类型转换
            for col in ['open', 'close', 'high', 'low', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df.dropna()
        
        try:
            return self._retry_request(_fetch)
        except Exception as e:
            logger.error(f"获取 {symbol} 日线数据失败: {e}")
            return None


class SinaDaily(DataSource):
    """新浪财经日线接口"""
    
    def __init__(self):
        super().__init__("SinaDaily", max_retries=3)
        self.base_url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    
    def _convert_symbol(self, symbol: str) -> str:
        if symbol.startswith('6'):
            return f"sh{symbol}"
        elif symbol.startswith(('3', '0')):
            return f"sz{symbol}"
        return symbol
    
    def get_stock_daily(self, symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
        symbol = self._convert_symbol(symbol)
        
        def _fetch():
            params = {
                'symbol': symbol,
                'scale': '240',  # 日线
                'ma': '5',
                'datalen': str(days)
            }
            
            response = self.session.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            import json
            data = json.loads(response.text)
            
            if not data:
                return None
            
            # 转换为DataFrame
            df = pd.DataFrame(data)
            df = df.rename(columns={
                'day': 'date',
                'open': 'open',
                'close': 'close',
                'high': 'high',
                'low': 'low',
                'volume': 'volume'
            })
            
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            
            for col in ['open', 'close', 'high', 'low', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df.dropna()
        
        try:
            return self._retry_request(_fetch)
        except Exception as e:
            logger.error(f"获取 {symbol} 日线数据失败: {e}")
            return None


class EastMoney(DataSource):
    """东方财富日线接口"""
    
    def __init__(self):
        super().__init__("EastMoney", max_retries=3)
    
    def _convert_symbol(self, symbol: str) -> str:
        if symbol.startswith('6'):
            return f"1.{symbol}"
        elif symbol.startswith('3'):
            return f"0.{symbol}"
        elif symbol.startswith('0'):
            return f"0.{symbol}"
        return symbol
    
    def get_stock_daily(self, symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
        symbol = self._convert_symbol(symbol)
        
        def _fetch():
            url = f"http://push2his.eastmoney.com/api/qt/stock/kline/get"
            params = {
                'secid': symbol,
                'fields1': 'f1,f2,f3,f4,f5,f6',
                'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
                'klt': '101',  # 日线
                'fqt': '1',    # 前复权
                'end': '20500101',
                'lmt': str(days)
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            klines = data.get('data', {}).get('klines', [])
            if not klines:
                return None
            
            # 解析K线数据
            rows = []
            for line in klines:
                parts = line.split(',')
                rows.append({
                    'date': parts[0],
                    'open': float(parts[1]),
                    'close': float(parts[2]),
                    'high': float(parts[3]),
                    'low': float(parts[4]),
                    'volume': float(parts[5])
                })
            
            df = pd.DataFrame(rows)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            
            return df
        
        try:
            return self._retry_request(_fetch)
        except Exception as e:
            logger.error(f"获取 {symbol} 日线数据失败: {e}")
            return None


class DataFetcher:
    """多数据源管理器"""
    
    def __init__(self):
        self.sources = {
            'eastmoney': EastMoney(),
            'tencent': TencentQuotes(),
            'sina': SinaDaily()
        }
        logger.info("数据获取器初始化完成，数据源: EastMoney, Tencent, Sina")
    
    def get_stock_data(self, symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
        """获取股票数据，自动切换数据源"""
        errors = []
        
        # 按优先级尝试各数据源 (Sina最快最稳定优先)
        for source_name in ['sina', 'tencent', 'eastmoney']:
            source = self.sources[source_name]
            logger.info(f"尝试从 {source_name} 获取 {symbol} 数据...")
            
            try:
                df = source.get_stock_daily(symbol, days)
                if df is not None and len(df) >= days // 2:
                    logger.info(f"成功从 {source_name} 获取 {len(df)} 条数据")
                    return df
                else:
                    errors.append(f"{source_name}: 数据不足")
            except Exception as e:
                errors.append(f"{source_name}: {str(e)[:30]}")
        
        logger.error(f"所有数据源获取失败: {errors}")
        return None
    
    def get_realtime_quote(self, symbol: str) -> Optional[Dict]:
        """获取实时行情"""
        source = self.sources['tencent']
        return source.get_quote(symbol)
    
    def add_source(self, name: str, source: DataSource):
        """添加数据源"""
        self.sources[name] = source
        logger.info(f"添加数据源: {name}")


def test_fetcher():
    """测试数据获取"""
    fetcher = DataFetcher()
    
    # 测试获取几只股票
    test_symbols = ['600519', '000001', '300750']
    
    for symbol in test_symbols:
        print(f"\n{'='*50}")
        print(f"测试获取: {symbol}")
        
        # 获取日线
        df = fetcher.get_stock_data(symbol, days=30)
        if df is not None:
            print(f"获取成功! 共 {len(df)} 条数据")
            print(f"日期范围: {df['date'].min()} ~ {df['date'].max()}")
            print(df.tail(3))
        else:
            print("获取失败")
        
        # 获取实时
        quote = fetcher.get_realtime_quote(symbol)
        if quote:
            print(f"\n实时行情: {quote['name']} ¥{quote['price']}")
        
        time.sleep(1)


if __name__ == "__main__":
    test_fetcher()
