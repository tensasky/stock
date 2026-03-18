#!/usr/bin/env python3
"""智能数据源 - 交易时段动态选择最快源"""

import time
from data_fetcher import SinaDaily, TencentQuotes, EastMoney

class SmartDataFetcher:
    """智能数据源 - 自动选择最快的数据源"""
    
    def __init__(self):
        self.sources_order = ['sina', 'tencent', 'eastmoney']
        self.fastest = 'sina'  # 当前最优源
        self.last_test = 0
        self.test_interval = 300  # 5分钟测速一次
    
    def is_trading_time(self):
        """检查是否在交易时段"""
        from datetime import datetime
        now = datetime.now()
        h, m = now.hour, now.minute
        # 交易时段: 9:30-11:30, 13:00-15:00
        return (9, 30) <= (h, m) <= (11, 30) or (13, 0) <= (h, m) <= (15, 0)
    
    def test_sources(self):
        """测试各数据源速度"""
        srcs = {'sina': SinaDaily(), 'tencent': TencentQuotes(), 'eastmoney': EastMoney()}
        results = []
        
        for name, src in srcs.items():
            try:
                start = time.time()
                df = src.get_stock_daily('600971', days=3)
                elapsed = time.time() - start
                if df is not None:
                    results.append((name, elapsed))
            except:
                pass
        
        if results:
            results.sort(key=lambda x: x[1])
            self.fastest = results[0][0]
            self.last_test = time.time()
            print(f"📡 数据源测速: {[(n,round(t,2)) for n,t in results]} -> 最快: {self.fastest}")
        
        return self.fastest
    
    def get_stock_data(self, symbol, days=30):
        """使用当前最优源获取数据"""
        # 交易时段定期测速
        if self.is_trading_time() and time.time() - self.last_test > self.test_interval:
            self.test_sources()
        
        # 优先用最快的
        srcs = {'sina': SinaDaily(), 'tencent': TencentQuotes(), 'eastmoney': EastMoney()}
        
        for src_name in [self.fastest] + [s for s in self.sources_order if s != self.fastest]:
            try:
                df = srcs[src_name].get_stock_daily(symbol, days)
                if df is not None:
                    return df
            except:
                pass
        
        return None


if __name__ == '__main__':
    print("🧪 测试智能数据源...")
    sf = SmartDataFetcher()
    print(f"交易时段: {sf.is_trading_time()}")
    sf.test_sources()
