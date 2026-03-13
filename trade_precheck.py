# 交易前置检查 - 数据源有效性验证
# 确保只有当日数据最新最准时才执行交易

from realtime_price import get_realtime_price
import sqlite3

class TradePreCheck:
    """交易前置检查"""
    
    def __init__(self, db_path='data/stocks.db'):
        self.db_path = db_path
        self.last_check = None
        self.last_status = None
    
    def check_realtime_price(self, code):
        """
        检查实时价格是否有效
        
        返回: (can_trade: bool, reason: str)
        """
        # 1. 尝试获取实时价格
        price_data = get_realtime_price(code)
        
        if price_data is None:
            return False, "实时价格获取失败"
        
        # 2. 检查价格有效性
        if price_data.get('price', 0) <= 0:
            return False, f"价格无效: {price_data.get('price')}"
        
        # 3. 检查数据来源
        source = price_data.get('source', 'unknown')
        from_cache = price_data.get('from_cache', False)
        
        if from_cache:
            # 缓存数据已过期
            return False, f"数据来自缓存(过期),来源:{source}"
        
        # 4. 检查是否为过期缓存
        if price_data.get('expired', False):
            return False, "数据已过期"
        
        # 5. 成功
        return True, f"OK 来源:{source} 价格:¥{price_data['price']:.2f}"
    
    def check_batch(self, codes):
        """
        批量检查
        
        返回: {
            'can_trade': bool,  # 是否可以交易
            'valid_codes': [],  # 有效的股票
            'invalid_codes': [], # 无效的股票
            'results': {}       # 详细结果
        }
        """
        results = {}
        valid_codes = []
        invalid_codes = []
        
        for code in codes:
            can_trade, reason = self.check_realtime_price(code)
            results[code] = {'can_trade': can_trade, 'reason': reason}
            
            if can_trade:
                valid_codes.append(code)
            else:
                invalid_codes.append(code)
        
        can_trade = len(valid_codes) > 0
        
        return {
            'can_trade': can_trade,
            'valid_count': len(valid_codes),
            'invalid_count': len(invalid_codes),
            'valid_codes': valid_codes,
            'invalid_codes': invalid_codes,
            'results': results
        }
    
    def check_and_log(self, codes):
        """检查并记录日志"""
        result = self.check_batch(codes)
        
        print("\n" + "="*60)
        print("🔍 交易前置检查")
        print("="*60)
        
        print(f"\n可交易股票: {result['valid_count']}只")
        for code in result['valid_codes']:
            r = result['results'][code]
            print(f"  ✅ {code}: {r['reason']}")
        
        if result['invalid_count'] > 0:
            print(f"\n不可交易: {result['invalid_count']}只")
            for code in result['invalid_codes']:
                r = result['results'][code]
                print(f"  ❌ {code}: {r['reason']}")
        
        print("="*60)
        
        return result


# 单个股票检查
def can_trade(code):
    """单个股票能否交易"""
    checker = TradePreCheck()
    can_trade, reason = checker.check_realtime_price(code)
    return can_trade, reason


if __name__ == '__main__':
    import sys
    
    # 测试
    codes = ['600188', '000507', '000001']
    
    checker = TradePreCheck()
    result = checker.check_and_log(codes)
    
    print(f"\n最终结果: {'可以交易' if result['can_trade'] else '不可交易'}")
