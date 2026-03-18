#!/bin/bash
# 量化交易系统 - 定时任务
# 每30分钟运行一次

cd /Users/roberto/.openclaw/workspace/stock_analyzer

# 运行选股
python3 core.py scan

# 检查持仓
python3 core.py trade
