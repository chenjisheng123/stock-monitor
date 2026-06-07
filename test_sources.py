"""测试所有数据源"""
import json, time

print("=" * 50)
print("测试数据源...")

# 1. 新浪API
print("\n1. 新浪财经API:")
import urllib.request
url = "http://hq.sinajs.cn/list=sh601127,sz002920,sh603986"
req = urllib.request.Request(url)
req.add_header("Referer", "https://finance.sina.com.cn")
req.add_header("User-Agent", "Mozilla/5.0")
try:
    resp = urllib.request.urlopen(url, timeout=10)
    data = resp.read().decode("gbk", errors="replace")
    lines = [l for l in data.split("\n") if l.strip()]
    print(f"   OK: {len(lines)} stocks")
except Exception as e:
    print(f"   FAIL: {e}")

# 2. 东方财富直连
print("\n2. 东方财富API:")
url2 = "http://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=5&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fields=f2,f12,f14"
req2 = urllib.request.Request(url2)
req2.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
try:
    resp2 = urllib.request.urlopen(url2, timeout=10)
    j = json.loads(resp2.read().decode())
    count = j.get("data", {}).get("total", 0)
    print(f"   OK: {count} stocks available")
except Exception as e:
    print(f"   FAIL: {str(e)[:80]}")

# 3. 腾讯财经
print("\n3. 腾讯财经API:")
url3 = "http://qt.gtimg.cn/q=sh601127,sz002920"
req3 = urllib.request.Request(url3)
req3.add_header("User-Agent", "Mozilla/5.0")
try:
    resp3 = urllib.request.urlopen(url3, timeout=10)
    data3 = resp3.read().decode("gbk", errors="replace")
    lines3 = [l for l in data3.split("\n") if l.strip() and "=" in l]
    print(f"   OK: {len(lines3)} stocks")
except Exception as e:
    print(f"   FAIL: {e}")

# 4. 百度财经
print("\n4. 百度财经API:")
url4 = "https://finance.pae.baidu.com/vapi/v1/getquotation?srcid=5293&pointType=string&group=quotation_minute_ab&query=沪深300&code=000300&market_type=ab&newFormat=1"
req4 = urllib.request.Request(url4)
req4.add_header("User-Agent", "Mozilla/5.0")
try:
    resp4 = urllib.request.urlopen(url4, timeout=10)
    print(f"   OK: {len(resp4.read())} bytes")
except Exception as e:
    print(f"   FAIL: {e}")

print("\n" + "=" * 50)
print("测试完成!")
