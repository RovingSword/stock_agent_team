"""
数据源诊断脚本 - 排查技术分析失败原因
"""
import sys
import traceback
from datetime import datetime

print("=" * 60)
print(f"数据源诊断 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

# 测试股票代码
TEST_CODE = "300750"  # 宁德时代

# ============================================================
# 1. 测试数据源包是否安装
# ============================================================
print("\n【1. 检查数据源包安装】")

akshare_ok = False
efinance_ok = False
tushare_ok = False
requests_ok = False

try:
    import requests
    print(f"  ✅ requests 已安装")
    requests_ok = True
except ImportError as e:
    print(f"  ❌ requests 未安装: {e}")

try:
    import tushare as ts
    print(f"  ✅ tushare 已安装，版本: {ts.__version__}")
    tushare_ok = True
except ImportError as e:
    print(f"  ⚠️ tushare 未安装: {e}")

try:
    import akshare as ak
    print(f"  ✅ akshare 已安装，版本: {ak.__version__}")
    akshare_ok = True
except ImportError as e:
    print(f"  ❌ akshare 未安装: {e}")

try:
    import efinance as ef
    print(f"  ✅ efinance 已安装，版本: {ef.__version__}")
    efinance_ok = True
except ImportError as e:
    print(f"  ❌ efinance 未安装: {e}")

# ============================================================
# 2. 测试新浪财经数据源（新增）
# ============================================================
print(f"\n【2. 测试新浪财经数据源 - 推荐】")
if requests_ok:
    try:
        # 测试实时行情
        market = 'sh' if TEST_CODE.startswith('6') else 'sz'
        url = f"https://hq.sinajs.cn/list={market}{TEST_CODE}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn/',
        }
        
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200 and '="' in resp.text:
            data_str = resp.text.split('"')[1]
            if data_str:
                parts = data_str.split(',')
                print(f"  ✅ 新浪实时行情成功: {parts[0]} 当前价 ¥{parts[3]}")
            else:
                print("  ❌ 新浪实时行情返回空数据")
        else:
            print(f"  ❌ 新浪实时行情失败: HTTP {resp.status_code}")
    except Exception as e:
        print(f"  ❌ 新浪实时行情失败: {e}")
    
    # 测试K线数据
    try:
        url = "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData"
        params = {
            'symbol': f"{market}{TEST_CODE}",
            'scale': '240',
            'ma': 'no',
            'datalen': 60
        }
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list) and len(data) > 0:
                print(f"  ✅ 新浪K线数据成功: 获取 {len(data)} 条")
            else:
                print("  ❌ 新浪K线返回空数据")
        else:
            print(f"  ❌ 新浪K线失败: HTTP {resp.status_code}")
    except Exception as e:
        print(f"  ❌ 新浪K线获取失败: {e}")
else:
    print("  ⚠️ requests 未安装，跳过新浪财经测试")

# ============================================================
# 3. 测试 tushare 获取K线
# ============================================================
if tushare_ok:
    print(f"\n【3. 测试 tushare 数据源】")
    try:
        import tushare as ts
        # 免费接口测试
        df = ts.get_k_data(TEST_CODE, ktype='D')
        if df is not None and not df.empty:
            print(f"  ✅ tushare 免费接口成功: 获取 {len(df)} 条K线")
        else:
            print("  ⚠️ tushare 返回空数据（可能需要Token）")
    except Exception as e:
        print(f"  ❌ tushare 获取失败: {e}")

# ============================================================
# 4. 测试 efinance 获取K线
# ============================================================
if efinance_ok:
    print(f"\n【4. 测试 efinance 获取K线 - {TEST_CODE}】")
    try:
        df = ef.stock.get_quote_history(
            TEST_CODE,
            klt=101,  # 日K
            fqt=1     # 前复权
        )
        if df is not None and not df.empty:
            print(f"  ✅ 成功获取 {len(df)} 条K线数据")
            print(f"  最新数据: {df.iloc[-1].to_dict()}")
        else:
            print("  ❌ 返回空数据")
    except Exception as e:
        print(f"  ❌ 获取失败: {e}")
        traceback.print_exc()

# ============================================================
# 5. 测试 akshare 获取K线
# ============================================================
if akshare_ok:
    print(f"\n【5. 测试 akshare 获取K线 - {TEST_CODE}】")
    try:
        from datetime import timedelta
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=120)).strftime('%Y%m%d')
        
        df = ak.stock_zh_a_hist(
            symbol=TEST_CODE,
            period='daily',
            start_date=start_date,
            end_date=end_date,
            adjust='qfq'
        )
        if df is not None and not df.empty:
            print(f"  ✅ 成功获取 {len(df)} 条K线数据")
            print(f"  列名: {list(df.columns)}")
            print(f"  最新数据: {df.iloc[-1].to_dict()}")
        else:
            print("  ❌ 返回空数据")
    except Exception as e:
        print(f"  ❌ 获取失败: {e}")
        traceback.print_exc()

# ============================================================
# 6. 测试 akshare 实时行情
# ============================================================
if akshare_ok:
    print(f"\n【6. 测试 akshare 实时行情】")
    try:
        df = ak.stock_zh_a_spot_em()
        if df is not None and not df.empty:
            print(f"  ✅ 成功获取 {len(df)} 只股票行情")
            # 查找测试股票
            stock_df = df[df['代码'] == TEST_CODE]
            if not stock_df.empty:
                print(f"  找到 {TEST_CODE}: {stock_df.iloc[0]['名称']} - ¥{stock_df.iloc[0]['最新价']}")
            else:
                print(f"  ⚠️ 未找到股票 {TEST_CODE}")
        else:
            print("  ❌ 返回空数据")
    except Exception as e:
        print(f"  ❌ 获取失败: {e}")
        traceback.print_exc()

# ============================================================
# 7. 测试网络连接
# ============================================================
print("\n【7. 测试网络连接】")
import urllib.request

test_urls = [
    ("东方财富", "https://quote.eastmoney.com/"),
    ("新浪财经", "https://finance.sina.com.cn/"),
]

for name, url in test_urls:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        urllib.request.urlopen(req, timeout=5)
        print(f"  ✅ {name} 可访问")
    except Exception as e:
        print(f"  ❌ {name} 无法访问: {e}")

# ============================================================
# 8. 检查代理设置
# ============================================================
print("\n【8. 检查代理设置】")
import os

http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')

if http_proxy or https_proxy:
    print(f"  ⚠️ 检测到代理设置:")
    if http_proxy:
        print(f"     HTTP_PROXY: {http_proxy}")
    if https_proxy:
        print(f"     HTTPS_PROXY: {https_proxy}")
    print("  提示: 代理可能导致东方财富API访问失败")
    print("  解决方案: 取消代理或添加例外")
else:
    print("  ✅ 未设置代理")

# ============================================================
# 9. 使用 DataFetcher 测试
# ============================================================
print("\n【9. 使用项目 DataFetcher 测试】")
try:
    from utils.data_fetcher import DataFetcher
    fetcher = DataFetcher()
    
    print(f"  已加载数据源: {fetcher.data_sources}")
    
    # 获取技术指标
    result = fetcher.get_technical_indicators(f"SH{TEST_CODE}")
    
    if result:
        print(f"  ✅ 技术指标获取成功")
        print(f"     当前价格: ¥{result.get('current_price')}")
        print(f"     MA5: {result.get('ma5')}")
        print(f"     周期趋势: {result.get('weekly_trend')}")
    else:
        print("  ❌ 技术指标返回 None")
        
except Exception as e:
    print(f"  ❌ DataFetcher 测试失败: {e}")
    traceback.print_exc()

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)
