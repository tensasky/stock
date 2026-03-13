"""
白板量化系统配置 V1
2026-03-04
"""

# ============ 观察池 ============
WATCH_POOL = {
    '煤炭': ['600188','600971','600395','601001','600225','600121','600483'],
    '电力': ['600900','600795','600011','601991','600025','600027'],
    '银行保险': ['600036','601398','601988','601318','601166'],
    '白酒': ['600519','000858','000568','600809'],
    '新能源': ['601012','600438','002129','300750','002594','002460','002311'],
    'AI科技': ['688041','688111','688400','688169','300059','300033'],
    '军工': ['600893','600879','600862','600038','600316'],
    '机器人': ['002410','002230','301029','300024','300567'],
}

ALL_WATCH_CODES = []
for codes in WATCH_POOL.values():
    ALL_WATCH_CODES.extend(codes)

# ============ 策略参数 V6.2 ============
STRATEGY = {
    'version': 'V6.2',
    'name': '多头排列+资金流入',
    'scoring': {
        'bullish_ma': 3,
        'capital_flow': 3,
        'volume_ratio': 2,
        'breakout': 2,
    },
    'buy_threshold': 6,
    'hold_days': 2,
    'volume_ratio_range': (1.2, 3.0),
}

# ============ 快速扫描参数 ============
QUICK_SCAN = {
    'enabled': True,
    'pre_screen_time': '14:25',   # 初筛: 活跃股票池
    'scan_time': '14:30',         # 评分: 完整技术分析
    'min_change': 0.5,            # 初筛涨跌幅门槛
    'max_stocks': 15,             # 初筛最多15只
    'notify_before': 30,          # 提前30分钟通知
}

# ============ 数据源配置 ============
DATA_SOURCE = {
    'priority': ['sina', 'tencent', 'eastmoney'],
    'trading_hours': {
        'morning': ('09:30', '11:30'),
        'afternoon': ('13:00', '15:00'),
    },
    'test_interval': 300,
    'timeout': 10,
}

# ============ 邮件配置 ============
EMAIL = {
    'smtp': 'smtp.qq.com',
    'port': 465,
    'sender': 'your_email@qq.com',
    'receiver': 'target_email@example.com',
}

# ============ 交易时间表 ============
TRADING = {
    'pre_screen': '14:25',   # 初筛活跃股票池
    'score_scan': '14:30',   # 完整评分 -> 通知
}

# ============ V7.0 策略 (测试中) ============
STRATEGY_V7 = {
    'version': 'V7.0',
    'name': '多头排列+资金流入+MACD增强',
    'scoring': {
        'bullish_ma': 3,
        'capital_flow': 3,
        'volume_ratio': 2,
        'breakout': 2,
        'macd_golden': 2,
        'kdj_oversold': 1,
        'rsi_safe': 1,
    },
    'buy_threshold': 7,
    'position': {10: 1.0, 8: 0.7, 6: 0.5},
    'stop_loss': -5,
    'take_profit_1': 5,
    'take_profit_2': 8,
    'hold_days': 2,
}
