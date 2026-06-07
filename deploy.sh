#!/bin/bash
# 部署到华为云
apt-get update -y
apt-get install -y python3 python3-pip cron

# 安装依赖
pip3 install yfinance pandas numpy openpyxl akshare --break-system-packages

# 创建目录
mkdir -p /opt/stock-monitor/data /opt/stock-monitor/reports

# 这一行会被替换为实际代码部署
echo "Deploy phase 1 complete"
