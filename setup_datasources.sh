#!/bin/bash
# 股票监控系统 — 数据源扩充脚本
# 在华为云服务器上直接运行
set -e

echo "======================================"
echo "  数据源扩充 - 开始"
echo "======================================"

# 1. 更新代码
echo "[1/6] 更新代码..."
cd /opt/stock-monitor
git pull origin master 2>&1 | tail -3

# 2. 安装新依赖
echo "[2/6] 安装依赖..."
pip3 install akshare tushare -i https://mirrors.aliyun.com/pypi/simple/ 2>&1 | tail -3

# 3. 测试AKShare
echo "[3/6] 测试AKShare..."
python3 -c "
import akshare as ak
try:
    df = ak.stock_zh_a_spot_em()
    print(f'AKShare OK: {len(df)} 只股票')
except Exception as e:
    print(f'AKShare FAIL: {str(e)[:100]}')
"

# 4. 测试东方财富直连API
echo "[4/6] 测试东方财富API..."
python3 -c "
import urllib.request, json
url = 'http://push2.eastmoney.com/api/qt/clist/get'
params = 'pn=1&pz=5&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fields=f2,f3,f12,f14'
full_url = url + '?' + params
req = urllib.request.Request(full_url)
req.add_header('User-Agent', 'Mozilla/5.0')
resp = urllib.request.urlopen(full_url, timeout=10)
data = json.loads(resp.read().decode())
count = data.get('data',{}).get('total', 0) if data else 0
print(f'东方财富API OK: {count} 只股票可用')
"

# 5. 验证当前数据拉取
echo "[5/6] 验证数据拉取..."
cd /opt/stock-monitor
python3 -c "
from data_fetcher import *
results = fetch_all_snapshots()
ok = sum(1 for v in results.values() if 'error' not in v)
for code, snap in results.items():
    err = snap.get('error', '')
    name = snap.get('name', code)
    pe = snap.get('pe_ttm', '?')
    price = snap.get('price', '?')
    status = 'OK' if not err else f'ERROR({err[:30]})'
    print(f'  {name:8s}  ￥{str(price):8s}  PE={str(pe):6s}  {status}')
print(f'总计: {ok}/{len(results)}')
"

# 6. 重启定时任务
echo "[6/6] 检查定时任务..."
crontab -l

echo ""
echo "======================================"
echo "  全部完成！"
echo "======================================"
