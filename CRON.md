# OpenClaw 股票分析系统 - Cron 配置

## 当前配置

### 1. 每日14:30 选股报告
30 14 * * 1-5 cd /Users/roberto/.openclaw/workspace/stock_analyzer && /usr/bin/python3 sim_trade.py report >> /Users/roberto/.openclaw/workspace/stock_analyzer/cron.log 2>&1

### 2. 实时选股 (10:00, 11:00, 14:00)
0 10,11,14 * * 1-5 cd /Users/roberto/.openclaw/workspace/stock_analyzer && /usr/bin/python3 realtime_scan.py >> /Users/roberto/.openclaw/workspace/stock_analyzer/logs/realtime.log 2>&1

## 说明

- **14:30报告**: 每日收盘后分析选股，发送邮件
- **实时选股**: 交易时段10点、11点、14点执行实时选股

## 手动命令

# 查看当前cron
crontab -l

# 查看日志
tail -f /Users/roberto/.openclaw/workspace/stock_analyzer/cron.log
tail -f /Users/roberto/.openclaw/workspace/stock_analyzer/logs/realtime.log
