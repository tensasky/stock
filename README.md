# 🤖 白板量化交易系统 - V6.2

> 模拟交易系统 | 自动选股 | RPS强势股扫描

---

## 📋 系统概述

- **版本**: V6.2.1
- **目标**: 稳定量化收益
- **核心功能**: RPS强势股扫描 + 自动买入 + 模拟交易

---

## 🏗️ 架构

```
数据获取 → 选股策略 → 自动买入 → 风控 → 报告
   ↓           ↓           ↓         ↓       ↓
数据库    技术分析    滑点计算   止损止盈   邮件/Discord
```

---

## 📁 文件结构

```
stock_analyzer/
├── sim_trade.py          # 主程序 (选股/买入/卖出)
├── core.py               # 核心引擎
├── smart_fetcher.py      # 智能数据获取
├── indicators.py         # 技术指标计算
├── data_fetcher.py       # 数据抓取
├── daily_report.py       # 日报生成
├── backtest_agent.py     # 回测分析
├── execution_agent.py    # 交易执行
├── report_agent.py       # 报告生成
├── realtime_agent.py     # 实时监控
├── fix_missing_klines.py # 数据补全
├── data/
│   └── stocks.db        # 股票数据库
├── changelog/
│   └── V6.2.1.md       # 更新日志
└── mail_config.json     # 邮件配置
```

---

## 🚀 快速开始

```bash
# 扫描观察池股票
python3 sim_trade.py scan

# 自动买入模式 (交易时段)
python3 sim_trade.py trade

# RPS强势股扫描
python3 sim_trade.py rps

# RPS扫描 + 自动买入
python3 sim_trade.py rps_trade

# 查看持仓
python3 sim_trade.py status

# 生成报告
python3 sim_trade.py report
```

---

## 📊 交易策略

### 买入条件

| 条件 | 说明 |
|------|------|
| RPS > 85 | 120日涨幅排名前15% |
| 多头排列 | MA5 > MA10 > MA20 |
| 放量 | 量比 1.2-3 |

### 卖出条件

| 条件 | 说明 |
|------|------|
| 止损 | -5% |
| 止盈 | +10% |
| 持有期 | 最长10天 |

### 费用

- 买入滑点: 0.2%
- 卖出手续费: 万三 (0.03%)

---

## ⏰ Cron 任务

| 任务 | 时间 | 说明 |
|------|------|------|
| sim-trade-auto | 9:30-11:30, 13:00-14:57 | 每30分钟扫描买入 |
| rps-scan | 10:00 | RPS强势股扫描 |
| daily-report | 14:30 | 每日报告 |

---

## 🗄️ 数据库

- **位置**: `data/stocks.db`
- **表**: daily_data (code, date, open, high, low, close, volume, amount)
- **更新**: 每日16:00自动补数据

---

## 📝 更新日志

See `changelog/V6.2.1.md`

---

*由 OpenClaw AI 开发*
