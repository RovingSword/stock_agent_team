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

try:
    import akshare as ak

    print(f"  ✅ akshare 已安装，版本: {ak.__version__}")
    akshare_ok = True
except ImportError as e:
    print(f"  ❌ akshare 未安装: {e}")

try:
    import efinance as ef

    # efinance 没有 __version__ 属性，用其他方式标识
    print("  ✅ efinance 已安装")
    efinance_ok = True
except ImportError as e:
    print(f"  ❌ efinance 未安装: {e}")

if not akshare_ok and not efinance_ok:
    print("\n❌ 没有可用的数据源，请先安装:")
    print("   pip install akshare")
    print("   pip install efinance")
    sys.exit(1)

# ============================================================
# 2. 测试 efinance 获取K线
# ============================================================
if efinance_ok:
    print(f"\n【2. 测试 efinance 获取K线 - {TEST_CODE}】")
    try:
        df = ef.stock.get_quote_history(
            TEST_CODE,
            klt=101,  # 日K
            fqt=1  # 前复权
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
# 3. 测试 akshare 获取K线
# ============================================================
if akshare_ok:
    print(f"\n【3. 测试 akshare 获取K线 - {TEST_CODE}】")
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
# 4. 测试 akshare 实时行情
# ============================================================
if akshare_ok:
    print(f"\n【4. 测试 akshare 实时行情】")
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
# 5. 测试网络连接
# ============================================================
print("\n【5. 测试网络连接】")
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
# 6. 检查代理设置
# ============================================================
print("\n【6. 检查代理设置】")
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
# 7. 使用 DataFetcher 测试
# ============================================================
print("\n【7. 使用项目 DataFetcher 测试】")
try:
    from utils.data_fetcher import DataFetcher

    fetcher = DataFetcher()

    print(f"  已加载数据源: {fetcher.data_sources}")

    # 获取技术指标
    # 300开头是创业板(深交所)，用SZ前缀
    result = fetcher.get_technical_indicators(f"SZ{TEST_CODE}")

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
