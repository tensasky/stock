# 🤖 白板红中量化交易系统 - V8

> 多Agent量化交易系统 | 月收益目标5%+

---

## 📋 系统概述

**目标**: 月收益5%+ | 胜率57.8% | 平均收益4.87%/笔

### 核心功能

1. **多Agent架构** - 数据/策略/执行/风控/报告分离
2. **V8策略** - 强势趋势+资金流入+板块启动
3. **实时价格** - 多数据源容错 (腾讯/新浪/东方财富)
4. **交易前置检查** - 只有当日数据有效才执行交易
5. **自动选股** - 每日14:30 + 盘中10/11/14点实时扫描

---

## 🏗️ 架构

```
数据Agent → 策略Agent → 执行Agent → 风控Agent → 报告Agent
              ↓
        实时价格获取 (多数据源)
              ↓
        交易前置检查 (数据有效性验证)
```

---

## 📁 文件结构

```
stock_analyzer/
├── data_agent.py         # 数据抓取/存储
├── strategy_v8.py       # V8策略选股
├── realtime_price.py    # 多数据源实时价格
├── realtime_scan.py     # 实时选股扫描
├── trade_precheck.py    # 交易前置检查
├── execution_agent.py   # 交易执行
├── risk_agent.py       # 风控/止盈止损
├── report_agent.py     # 报告生成/邮件
├── backtest_agent.py   # 回测分析
├── quant_system.py     # 统一入口
└── config_v8.json      # V8策略配置
```

---

## ⚙️ V8策略参数

| 参数 | 值 |
|------|-----|
| 最低评分 | 10分 |
| 持有天数 | 10天 |
| 止损 | 2% |
| 止盈 | 不设限 |

### 选股信号

| 信号 | 分数 |
|------|------|
| 涨幅>3% | +3 |
| 多头排列 | +3 |
| 资金流入 | +3 |
| 接近20日高点 | +2 |
| MACD金叉 | +2 |
| MACD红柱 | +1 |

---

## 🚀 快速开始

```bash
# 1. 安装依赖
pip install requests pandas numpy

# 2. 配置邮件
编辑 mail_config.json

# 3. 运行选股
python3 quant_system.py scan --min-score 10

# 4. 执行交易
python3 quant_system.py exec --sub signals
```

---

## 📊 回测结果

- **区间**: 2025-01-01 ~ 2026-03-12
- **胜率**: 57.8%
- **平均收益**: 4.87%/笔
- **交易次数**: 790次

---

## ⚠️ 关键规则

**交易前置检查**: 只有当日实时价格获取成功才执行交易

```python
from trade_precheck import can_trade
can_trade(code)  # 返回 (bool, reason)
```

---

*由 OpenClaw AI 开发*
