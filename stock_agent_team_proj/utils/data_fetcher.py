"""
数据获取模块 - 多数据源版本
支持 akshare、efinance 等多个数据源，自动切换和重试
"""
import random
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd
import requests

from utils.logger import get_logger

logger = get_logger('data_fetcher')

# 新浪/腾讯 API 请求头
SINA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://finance.sina.com.cn/",
}
TENCENT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://gu.qq.com/",
}

# 安装线程异常钩子，抑制 efinance 内部 multitasking 线程的未捕获异常
_original_excepthook = threading.excepthook

def _suppress_efinance_thread_exception(args):
    """抑制 efinance/multitasking 线程中的网络异常，避免污染控制台输出"""
    if args.exc_type and issubclass(args.exc_type, Exception):
        # efinance 内部线程的网络异常，只记录 debug 日志
        logger.debug(
            f"[suppressed] 线程异常 ({args.thread.name}): "
            f"{args.exc_type.__name__}: {args.exc_value}"
        )
    else:
        # 非网络异常，交给原始钩子处理
        _original_excepthook(args)

threading.excepthook = _suppress_efinance_thread_exception


class DataFetcher:
    """多数据源股票数据获取器"""
    
    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 2  # 重试间隔秒
        self._cache = {}
        self._cache_time = {}
        self.cache_timeout = 300  # 5分钟缓存
        self.request_timeout = 10  # 请求超时秒数
        
        # 尝试导入多个数据源
        self.data_sources = []
        self._init_data_sources()
    
        # 标记是否使用了模拟数据
        self._using_mock_data = {}

    def _init_data_sources(self):
        """初始化数据源"""
        # 数据源1: akshare
        try:
            import akshare as ak
            self.ak = ak
            self.data_sources.append('akshare')
            logger.info("akshare 数据源已加载")
        except Exception as e:
            self.ak = None
            logger.warning(f"akshare 加载失败: {e}")
        
        # 数据源2: efinance
        try:
            import efinance as ef
            self.ef = ef
            # 设置 efinance 的请求超时，防止线程长时间挂起
            try:
                import requests as req
                # 为 efinance 内部 session 设置默认超时
                for attr_name in dir(ef.stock):
                    obj = getattr(ef.stock, attr_name, None)
                    if obj and hasattr(obj, '__self__'):
                        instance = obj.__self__
                        if hasattr(instance, 'session'):
                            instance.session.timeout = self.request_timeout
            except Exception:
                pass
            self.data_sources.append('efinance')
            logger.info("efinance 数据源已加载")
        except Exception as e:
            self.ef = None
            logger.warning(f"efinance 加载失败: {e}")
    
    def _retry_request(self, func, *args, **kwargs):
        """带重试的请求"""
        last_error = None
        
        for i in range(self.max_retries):
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                last_error = e
                if i < self.max_retries - 1:
                    delay = self.retry_delay + random.uniform(0, 1)
                    logger.warning(f"请求失败，{delay:.1f}秒后重试 ({i+1}/{self.max_retries}): {e}")
                    time.sleep(delay)
        
        logger.error(f"请求最终失败: {last_error}")
        return None
    
    def _get_with_cache(self, key: str, fetch_func):
        """带缓存的数据获取"""
        now = datetime.now()
        
        if key in self._cache and key in self._cache_time:
            if (now - self._cache_time[key]).total_seconds() < self.cache_timeout:
                return self._cache[key]
        
        result = self._retry_request(fetch_func)
        if result is not None:
            self._cache[key] = result
            self._cache_time[key] = now
        
        return result

    @staticmethod
    def _pick_first_available(row, *field_names, default=None):
        """按候选字段顺序取值，兼容外部接口字段变更"""
        for field_name in field_names:
            if hasattr(row, "get"):
                value = row.get(field_name, None)
            else:
                value = None
            if value is not None and pd.notna(value):
                return value
        return default

    @staticmethod
    def _safe_float(value, default=0.0, scale=1.0) -> float:
        """安全转换数值"""
        if value is None or (isinstance(value, str) and not value.strip()):
            return default
        try:
            if pd.isna(value):
                return default
        except Exception:
            pass

        try:
            return float(value) * scale
        except (TypeError, ValueError):
            return default
    
    # ============================================================
    # K线数据 - 多数据源
    # ============================================================
    
    def get_daily_kline(self, stock_code: str, days: int = 60) -> Optional[pd.DataFrame]:
        """
        获取日K线数据 - 多数据源尝试
        
        Args:
            stock_code: 股票代码
            days: 获取天数
        """
        code = stock_code.replace('SH', '').replace('SZ', '').replace('BJ', '')
        cache_key = f"daily_kline_{code}_{days}"
        
        def fetch():
            # 优先尝试新浪财经（东方财富API可能被反爬限制）
            df = self._get_kline_sina(code, days)
            if df is not None and not df.empty:
                return df

            # 备选 efinance
            if 'efinance' in self.data_sources:
                df = self._get_kline_efinance(code, days)
                if df is not None and not df.empty:
                    return df
            
            # 备选 akshare
            if 'akshare' in self.data_sources:
                df = self._get_kline_akshare(code, days)
                if df is not None and not df.empty:
                    return df
            
            return None
        
        return self._get_with_cache(cache_key, fetch)
    
    def _call_efinance_safely(self, func, *args, **kwargs):
        """安全调用 efinance 方法，捕获线程内异常"""
        import threading
        result_holder = {'result': None, 'error': None}
        event = threading.Event()

        def _worker():
            try:
                result_holder['result'] = func(*args, **kwargs)
            except Exception as e:
                result_holder['error'] = e
            finally:
                event.set()

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        # 等待超时
        if not event.wait(timeout=self.request_timeout + 5):
            logger.warning(f"efinance 调用超时({self.request_timeout + 5}s)")
            return None

        if result_holder['error'] is not None:
            logger.debug(f"efinance 调用异常: {result_holder['error']}")
            return None

        return result_holder['result']

    def _get_efinance_base_info(self, code: str):
        """获取 efinance 基本信息，安全调用失败时回退直连"""
        if 'efinance' not in self.data_sources or self.ef is None:
            return None

        try:
            df = self._call_efinance_safely(
                self.ef.stock.get_base_info, [code]
            )
            if df is not None and not getattr(df, 'empty', True):
                return df
        except Exception as e:
            logger.debug(f"efinance 基本信息安全调用失败: {e}")

        try:
            df = self.ef.stock.get_base_info([code])
            if df is not None and not getattr(df, 'empty', True):
                logger.debug(f"efinance 基本信息直连重试成功: {code}")
                return df
        except Exception as e:
            logger.debug(f"efinance 基本信息直连失败: {e}")

        return None

    def _get_akshare_financial_summary(self, code: str) -> Optional[Dict[str, Any]]:
        """使用 akshare 的结构化同花顺财务摘要"""
        if 'akshare' not in self.data_sources or self.ak is None:
            return None

        summary_func = getattr(self.ak, 'stock_financial_abstract_new_ths', None)
        if summary_func is None:
            return None

        try:
            df = summary_func(symbol=code)
            if df is None or df.empty:
                return None

            latest_date = str(df.iloc[0]['report_date'])
            latest_df = df[df['report_date'].astype(str) == latest_date]
            metric_map = {
                row['metric_name']: row.get('value')
                for _, row in latest_df.iterrows()
            }

            return {
                'revenue': self._safe_float(metric_map.get('operating_income_total')),
                'revenue_growth': self._safe_float(
                    metric_map.get('calculate_operating_income_total_yoy_growth_ratio'),
                    scale=0.01,
                ),
                'net_profit': self._safe_float(metric_map.get('parent_holder_net_profit')),
                'profit_growth': self._safe_float(
                    metric_map.get('calculate_parent_holder_net_profit_yoy_growth_ratio'),
                    scale=0.01,
                ),
                'gross_margin': self._safe_float(metric_map.get('sale_gross_margin'), scale=0.01),
                'net_margin': self._safe_float(metric_map.get('sale_net_interest_ratio'), scale=0.01),
                'roe': self._safe_float(metric_map.get('index_full_diluted_roe'), scale=0.01),
                'data_source': 'akshare_ths',
            }
        except Exception as e:
            logger.debug(f"akshare 同花顺财务摘要获取失败: {e}")
            return None

    def _get_akshare_baidu_valuation(self, code: str) -> Optional[Dict[str, Any]]:
        """使用 akshare 百度估值接口获取 PE/PB/市值"""
        if 'akshare' not in self.data_sources or self.ak is None:
            return None

        valuation_func = getattr(self.ak, 'stock_zh_valuation_baidu', None)
        if valuation_func is None:
            return None

        try:
            pe_df = valuation_func(symbol=code, indicator='市盈率(TTM)', period='近一年')
            pb_df = valuation_func(symbol=code, indicator='市净率', period='近一年')
            market_cap_df = valuation_func(symbol=code, indicator='总市值', period='近一年')

            if pe_df is None or pe_df.empty or pb_df is None or pb_df.empty:
                return None

            pe_series = pe_df['value'].dropna()
            pb_series = pb_df['value'].dropna()
            if pe_series.empty or pb_series.empty:
                return None

            pe_ttm = self._safe_float(pe_series.iloc[-1])
            pb = self._safe_float(pb_series.iloc[-1])
            pe_percentile = 0.5
            if pe_ttm > 0 and not pe_series.empty:
                pe_percentile = float((pe_series < pe_ttm).sum() / len(pe_series))

            market_cap = 0.0
            if market_cap_df is not None and not market_cap_df.empty:
                market_cap_series = market_cap_df['value'].dropna()
                if not market_cap_series.empty:
                    market_cap = self._safe_float(market_cap_series.iloc[-1]) * 100000000

            return {
                'pe_ttm': round(pe_ttm, 2),
                'pb': round(pb, 2),
                'industry_pe': 25,
                'pe_percentile': round(pe_percentile, 2),
                'market_cap': market_cap,
                'circulating_market_cap': 0,
                'data_source': 'akshare_baidu',
            }
        except Exception as e:
            logger.debug(f"akshare 百度估值获取失败: {e}")
            return None

    def _get_kline_efinance(self, code: str, days: int) -> Optional[pd.DataFrame]:
        """使用 efinance 获取K线"""
        try:
            # 使用安全调用方式，避免 efinance 内部线程异常无法捕获
            df = self._call_efinance_safely(
                self.ef.stock.get_quote_history,
                code,
                klt=101,  # 日K
                fqt=1    # 前复权
            )
            
            if df is None or (hasattr(df, 'empty') and df.empty):
                return None
            
            # 标准化列名
            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount',
                '涨跌幅': 'change_pct'
            })
            
            # 取最近N天
            df = df.tail(days)
            
            return df
        except Exception as e:
            logger.debug(f"efinance K线获取失败: {e}")
            return None
    
    def _get_kline_akshare(self, code: str, days: int) -> Optional[pd.DataFrame]:
        """使用 akshare 获取K线"""
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days*2)).strftime('%Y%m%d')
            
            df = self.ak.stock_zh_a_hist(
                symbol=code,
                period='daily',
                start_date=start_date,
                end_date=end_date,
                adjust='qfq'
            )
            
            if df is None or df.empty:
                return None
            
            # 标准化列名
            col_map = {
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount'
            }
            df = df.rename(columns=col_map)
            
            # 取最近N天
            df = df.tail(days)
            
            return df
        except Exception as e:
            logger.debug(f"akshare K线获取失败: {e}")
            return None
    
    def _get_kline_sina(self, code: str, days: int) -> Optional[pd.DataFrame]:
        """使用新浪财经 API 获取K线数据"""
        try:
            # 判断市场：沪市(60/68开头)用sh，深市(00/30开头)用sz，北交所(8/4开头)用bj
            if code.startswith(('60', '68')):
                symbol = f"sh{code}"
            elif code.startswith(('00', '30')):
                symbol = f"sz{code}"
            else:
                symbol = f"bj{code}"

            url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
            params = {
                "symbol": symbol,
                "scale": "240",  # 日K
                "ma": "no",
                "datalen": str(days * 2),  # 多取一些数据
            }

            resp = requests.get(url, params=params, headers=SINA_HEADERS, timeout=15)
            if resp.status_code != 200 or not resp.text or resp.text == "null":
                return None

            data = resp.json()
            if not data or not isinstance(data, list):
                return None

            # 转换为 DataFrame
            df = pd.DataFrame(data)

            # 标准化列名
            col_map = {
                'day': 'date',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume',
            }
            df = df.rename(columns=col_map)

            # 数值转换
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # 按日期排序并取最近N天
            df = df.sort_values('date').tail(days)

            logger.info(f"✅ 新浪财经K线获取成功 ({code}), 共 {len(df)} 条")
            return df

        except Exception as e:
            logger.debug(f"新浪财经K线获取失败: {e}")
            return None

    def get_weekly_kline(self, stock_code: str, weeks: int = 26) -> Optional[pd.DataFrame]:
        """
        获取周K线数据 - 用于中期趋势判断
        """
        code = stock_code.replace('SH', '').replace('SZ', '').replace('BJ', '')
        cache_key = f"weekly_kline_{code}_{weeks}"
        
        def fetch():
            # 优先尝试新浪财经
            df = self._get_weekly_kline_sina(code, weeks)
            if df is not None and not df.empty:
                return df

            # 备选 efinance
            if 'efinance' in self.data_sources:
                try:
                    df = self.ef.stock.get_quote_history(
                        code,
                        klt=102,  # 周K
                        fqt=1
                    )
                    
                    if df is not None and not df.empty:
                        df = df.rename(columns={
                            '日期': 'date', '开盘': 'open', '收盘': 'close',
                            '最高': 'high', '最低': 'low', '成交量': 'volume'
                        })
                        return df.tail(weeks)
                except Exception as e:
                    logger.debug(f"efinance 周K获取失败: {e}")
            
            # 备选 akshare
            if 'akshare' in self.data_sources:
                try:
                    df = self.ak.stock_zh_a_hist(
                        symbol=code,
                        period='weekly',
                        adjust='qfq'
                    )
                    if df is not None and not df.empty:
                        df = df.rename(columns={'日期': 'date', '开盘': 'open', '收盘': 'close',
                                                 '最高': 'high', '最低': 'low', '成交量': 'volume'})
                        return df.tail(weeks)
                except Exception as e:
                    logger.debug(f"akshare 周K获取失败: {e}")
            
            return None
        
        return self._get_with_cache(cache_key, fetch)
    
    def _get_weekly_kline_sina(self, code: str, weeks: int) -> Optional[pd.DataFrame]:
        """使用新浪财经 API 获取周K线数据"""
        try:
            # 判断市场
            if code.startswith(('60', '68')):
                symbol = f"sh{code}"
            elif code.startswith(('00', '30')):
                symbol = f"sz{code}"
            else:
                symbol = f"bj{code}"

            url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
            params = {
                "symbol": symbol,
                "scale": "1440",  # 周K（分钟数）
                "ma": "no",
                "datalen": str(weeks * 2),
            }

            resp = requests.get(url, params=params, headers=SINA_HEADERS, timeout=15)
            if resp.status_code != 200 or not resp.text or resp.text == "null":
                return None

            data = resp.json()
            if not data or not isinstance(data, list):
                return None

            df = pd.DataFrame(data)
            col_map = {'day': 'date', 'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close', 'volume': 'volume'}
            df = df.rename(columns=col_map)

            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            df = df.sort_values('date').tail(weeks)
            logger.info(f"✅ 新浪财经周K线获取成功 ({code}), 共 {len(df)} 条")
            return df

        except Exception as e:
            logger.debug(f"新浪财经周K线获取失败: {e}")
            return None

    # ============================================================
    # 技术指标计算
    # ============================================================
    
    def is_mock_data(self, stock_code: str) -> bool:
        """检查指定股票是否使用了模拟数据"""
        return self._using_mock_data.get(stock_code, False)

    def get_technical_indicators(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取技术指标数据"""
        try:
            # 获取日K数据
            df = self.get_daily_kline(stock_code, days=60)
            
            if df is None or df.empty:
                logger.warning(f"无法获取 {stock_code} 的真实K线数据，使用模拟数据")
                self._using_mock_data[stock_code] = True
                return self._generate_mock_technical_data(stock_code)
            
            self._using_mock_data[stock_code] = False

            # 确保数据类型正确
            for col in ['open', 'close', 'high', 'low', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 计算均线
            df['ma5'] = df['close'].rolling(window=5).mean()
            df['ma10'] = df['close'].rolling(window=10).mean()
            df['ma20'] = df['close'].rolling(window=20).mean()
            df['ma60'] = df['close'].rolling(window=60).mean()
            
            # 计算MACD
            ema12 = df['close'].ewm(span=12, adjust=False).mean()
            ema26 = df['close'].ewm(span=26, adjust=False).mean()
            df['dif'] = ema12 - ema26
            df['dea'] = df['dif'].ewm(span=9, adjust=False).mean()
            df['macd'] = (df['dif'] - df['dea']) * 2
            
            # 计算RSI
            def calc_rsi(series, period=14):
                delta = series.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
                rs = gain / loss.replace(0, np.inf)
                return 100 - (100 / (1 + rs))
            
            df['rsi6'] = calc_rsi(df['close'], 6)
            df['rsi12'] = calc_rsi(df['close'], 12)
            df['rsi24'] = calc_rsi(df['close'], 24)
            
            # 计算KDJ
            low_min = df['low'].rolling(window=9).min()
            high_max = df['high'].rolling(window=9).max()
            df['rsv'] = (df['close'] - low_min) / (high_max - low_min + 0.0001) * 100
            df['k'] = df['rsv'].ewm(com=2, adjust=False).mean()
            df['d'] = df['k'].ewm(com=2, adjust=False).mean()
            df['j'] = 3 * df['k'] - 2 * df['d']
            
            # 获取最新数据
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            
            # 计算涨跌幅
            change_pct = ((latest['close'] - prev['close']) / prev['close'] * 100) if prev['close'] > 0 else 0
            
            # 计算支撑压力位
            recent_20 = df.tail(20)
            support_levels = [
                float(recent_20['low'].min()),
                float(latest['ma20']) if pd.notna(latest['ma20']) else float(latest['close'] * 0.95)
            ]
            resistance_levels = [
                float(latest['close'] * 1.05),
                float(recent_20['high'].max())
            ]
            
            # 获取周K数据判断中期趋势
            weekly_df = self.get_weekly_kline(stock_code)
            weekly_trend = "未知"
            if weekly_df is not None and len(weekly_df) >= 20:
                weekly_ma5 = weekly_df['close'].rolling(5).mean().iloc[-1]
                weekly_ma10 = weekly_df['close'].rolling(10).mean().iloc[-1]
                weekly_close = weekly_df['close'].iloc[-1]
                if weekly_ma5 > weekly_ma10 and weekly_close > weekly_ma5:
                    weekly_trend = "中期上涨"
                elif weekly_ma5 < weekly_ma10 and weekly_close < weekly_ma5:
                    weekly_trend = "中期下跌"
                else:
                    weekly_trend = "中期震荡"
            
            return {
                'current_price': float(latest['close']),
                'prev_close': float(prev['close']),
                'open': float(latest['open']),
                'high': float(latest['high']),
                'low': float(latest['low']),
                'volume': float(latest['volume']) if pd.notna(latest['volume']) else 0,
                'amount': float(latest.get('amount', 0)) if 'amount' in latest else 0,
                
                # 均线
                'ma5': float(latest['ma5']) if pd.notna(latest['ma5']) else 0,
                'ma10': float(latest['ma10']) if pd.notna(latest['ma10']) else 0,
                'ma20': float(latest['ma20']) if pd.notna(latest['ma20']) else 0,
                'ma60': float(latest['ma60']) if pd.notna(latest['ma60']) else 0,
                
                # MACD
                'macd': {
                    'dif': float(latest['dif']) if pd.notna(latest['dif']) else 0,
                    'dea': float(latest['dea']) if pd.notna(latest['dea']) else 0,
                    'histogram': float(latest['macd']) if pd.notna(latest['macd']) else 0
                },
                
                # RSI
                'rsi': {
                    'rsi6': float(latest['rsi6']) if pd.notna(latest['rsi6']) else 50,
                    'rsi12': float(latest['rsi12']) if pd.notna(latest['rsi12']) else 50,
                    'rsi24': float(latest['rsi24']) if pd.notna(latest['rsi24']) else 50
                },
                
                # KDJ
                'kdj': {
                    'k': float(latest['k']) if pd.notna(latest['k']) else 50,
                    'd': float(latest['d']) if pd.notna(latest['d']) else 50,
                    'j': float(latest['j']) if pd.notna(latest['j']) else 50
                },
                
                # 支撑压力
                'support_levels': support_levels,
                'resistance_levels': resistance_levels,
                'recent_high': float(recent_20['high'].max()),
                'recent_low': float(recent_20['low'].min()),
                
                # 变化
                'change_pct': change_pct,
                
                # 中期趋势（周K判断）
                'weekly_trend': weekly_trend,
            }
        except Exception as e:
            logger.error(f"获取技术指标失败: {e}")
            return None
    
    # ============================================================
    # 行情数据
    # ============================================================
    
    def get_realtime_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取实时行情"""
        code = stock_code.replace('SH', '').replace('SZ', '').replace('BJ', '')
        cache_key = f"quote_{code}"
        
        def fetch():
            # 尝试 efinance
            if 'efinance' in self.data_sources:
                try:
                    df = self._get_efinance_base_info(code)
                    if df is not None and not df.empty:
                        row = df.iloc[0]
                        return {
                            'code': code,
                            'name': str(row.get('股票名称', '')),
                            'current_price': float(row.get('最新价', 0)),
                            'open': float(row.get('开盘价', 0)),
                            'high': float(row.get('最高价', 0)),
                            'low': float(row.get('最低价', 0)),
                            'prev_close': float(row.get('昨收', 0)),
                            'volume': float(row.get('成交量', 0)),
                            'amount': float(row.get('成交额', 0)),
                            'change_pct': float(row.get('涨跌幅', 0)),
                        }
                except Exception as e:
                    logger.debug(f"efinance 行情获取失败: {e}")
            
            # 尝试 akshare
            if 'akshare' in self.data_sources:
                try:
                    df = self.ak.stock_zh_a_spot_em()
                    stock_df = df[df['代码'] == code]
                    if not stock_df.empty:
                        row = stock_df.iloc[0]
                        return {
                            'code': code,
                            'name': str(row['名称']),
                            'current_price': float(row['最新价']) if pd.notna(row['最新价']) else 0,
                            'open': float(row['今开']) if pd.notna(row['今开']) else 0,
                            'high': float(row['最高']) if pd.notna(row['最高']) else 0,
                            'low': float(row['最低']) if pd.notna(row['最低']) else 0,
                            'prev_close': float(row['昨收']) if pd.notna(row['昨收']) else 0,
                            'volume': float(row['成交量']) if pd.notna(row['成交量']) else 0,
                            'amount': float(row['成交额']) if pd.notna(row['成交额']) else 0,
                            'change_pct': float(row['涨跌幅']) if pd.notna(row['涨跌幅']) else 0,
                        }
                except Exception as e:
                    logger.debug(f"akshare 行情获取失败: {e}")
            
            return None
        
        return self._get_with_cache(cache_key, fetch)
    
    # ============================================================
    # 资金数据
    # ============================================================
    
    def get_fund_flow(self, stock_code: str, days: int = 5) -> Optional[Dict[str, Any]]:
        """获取资金流向"""
        code = stock_code.replace('SH', '').replace('SZ', '').replace('BJ', '')
        cache_key = f"fund_flow_{code}_{days}"
        
        def fetch():
            # 尝试 akshare
            if 'akshare' in self.data_sources:
                try:
                    market = 'sh' if code.startswith('6') else 'sz'
                    df = self.ak.stock_individual_fund_flow(stock=code, market=market)
                    
                    if df is not None and not df.empty:
                        df = df.head(days)
                        
                        fund_flows = []
                        for _, row in df.iterrows():
                            fund_flows.append({
                                'date': str(row['日期']),
                                'net_inflow': float(row['主力净流入-净额']) if pd.notna(row['主力净流入-净额']) else 0,
                                'net_inflow_pct': float(row['主力净流入-净占比']) if pd.notna(row['主力净流入-净占比']) else 0,
                            })
                        
                        total_net_inflow = sum(f['net_inflow'] for f in fund_flows)
                        inflow_days = sum(1 for f in fund_flows if f['net_inflow'] > 0)
                        
                        return {
                            'fund_flows': fund_flows,
                            'net_inflow_5d': total_net_inflow,
                            'inflow_days': inflow_days,
                            'avg_net_inflow_pct': sum(f['net_inflow_pct'] for f in fund_flows) / len(fund_flows) if fund_flows else 0
                        }
                except Exception as e:
                    logger.debug(f"akshare 资金流获取失败: {e}")
            
            return None
        
        return self._get_with_cache(cache_key, fetch)
    
    def get_north_bound_flow(self, days: int = 5) -> Optional[Dict[str, Any]]:
        """获取北向资金数据"""
        cache_key = f"north_bound_{days}"
        
        def fetch():
            if 'akshare' in self.data_sources:
                try:
                    df = self.ak.stock_hsgt_hist_em(symbol="北向资金")
                    if df is not None and not df.empty:
                        df = df.head(days)
                        
                        flows = []
                        for _, row in df.iterrows():
                            flows.append({
                                'date': str(row['日期']),
                                'net_flow': float(row['当日成交净买额']) if pd.notna(row['当日成交净买额']) else 0,
                            })
                        
                        total_flow = sum(f['net_flow'] for f in flows)
                        positive_days = sum(1 for f in flows if f['net_flow'] > 0)
                        
                        return {
                            'flows': flows,
                            'total_flow_5d': total_flow,
                            'positive_days': positive_days,
                            'trend': 'inflow' if total_flow > 0 else 'outflow'
                        }
                except Exception as e:
                    logger.debug(f"北向资金获取失败: {e}")
            
            return None
        
        return self._get_with_cache(cache_key, fetch)
    
    # ============================================================
    # 大盘数据
    # ============================================================
    
    def get_market_data(self) -> Optional[Dict[str, Any]]:
        """获取大盘数据"""
        cache_key = "market_data"
        
        def fetch():
            result = {
                'market_index': {'sh': 0, 'sz': 0, 'cyb': 0},
                'market_trend': '震荡',
                'limit_up': 50,
                'limit_down': 10,
                'limit_ratio': 5.0,
            }
            
            # 获取指数
            if 'akshare' in self.data_sources:
                try:
                    # 上证指数
                    sh_df = self.ak.stock_zh_index_daily(symbol="sh000001")
                    if sh_df is not None and not sh_df.empty:
                        result['market_index']['sh'] = float(sh_df.iloc[-1]['close'])
                    
                    # 深证成指
                    sz_df = self.ak.stock_zh_index_daily(symbol="sz399001")
                    if sz_df is not None and not sz_df.empty:
                        result['market_index']['sz'] = float(sz_df.iloc[-1]['close'])
                    
                    # 创业板指
                    cyb_df = self.ak.stock_zh_index_daily(symbol="sz399006")
                    if cyb_df is not None and not cyb_df.empty:
                        result['market_index']['cyb'] = float(cyb_df.iloc[-1]['close'])
                    
                    # 涨跌停
                    today = datetime.now().strftime('%Y%m%d')
                    try:
                        zt_df = self.ak.stock_zt_pool_em(date=today)
                        result['limit_up'] = len(zt_df) if zt_df is not None and not zt_df.empty else 50
                    except:
                        pass
                    
                    try:
                        dt_df = self.ak.stock_dt_pool_em(date=today)
                        result['limit_down'] = len(dt_df) if dt_df is not None and not dt_df.empty else 10
                    except:
                        pass
                    
                    result['limit_ratio'] = result['limit_up'] / max(result['limit_down'], 1)
                    
                    # 判断趋势
                    if sh_df is not None and len(sh_df) >= 2:
                        change = (sh_df.iloc[-1]['close'] - sh_df.iloc[-2]['close']) / sh_df.iloc[-2]['close'] * 100
                        if change > 1:
                            result['market_trend'] = '强势上涨'
                        elif change > 0.3:
                            result['market_trend'] = '震荡偏强'
                        elif change > -0.3:
                            result['market_trend'] = '震荡'
                        elif change > -1:
                            result['market_trend'] = '震荡偏弱'
                        else:
                            result['market_trend'] = '弱势下跌'
                    
                except Exception as e:
                    logger.debug(f"大盘数据获取失败: {e}")
            
            return result
        
        return self._get_with_cache(cache_key, fetch)
    
    # ============================================================
    # 基本面数据
    # ============================================================
    
    def get_financial_data(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取财务数据"""
        code = stock_code.replace('SH', '').replace('SZ', '').replace('BJ', '')
        cache_key = f"financial_{code}"
        
        def fetch():
            if 'akshare' in self.data_sources:
                try:
                    df = self.ak.stock_financial_analysis_indicator(symbol=code)
                    if df is not None and not df.empty:
                        latest = df.iloc[0]
                        return {
                            'revenue': self._safe_float(latest.get('营业收入', 0)),
                            'revenue_growth': self._safe_float(latest.get('营业收入同比增长率', 0), scale=0.01),
                            'net_profit': self._safe_float(latest.get('净利润', 0)),
                            'profit_growth': self._safe_float(latest.get('净利润同比增长率', 0), scale=0.01),
                            'gross_margin': self._safe_float(latest.get('销售毛利率', 0), scale=0.01),
                            'net_margin': self._safe_float(latest.get('销售净利率', 0), scale=0.01),
                            'roe': self._safe_float(latest.get('净资产收益率', 0), scale=0.01),
                            'data_source': 'akshare',
                        }
                except Exception as e:
                    logger.debug(f"财务数据获取失败: {e}")

            akshare_summary = self._get_akshare_financial_summary(code)
            if akshare_summary is not None:
                return akshare_summary

            if 'efinance' in self.data_sources:
                try:
                    df = self._get_efinance_base_info(code)
                    if df is not None and not df.empty:
                        row = df.iloc[0]
                        return {
                            'revenue': self._safe_float(
                                self._pick_first_available(row, '营业总收入', '营业收入', '营收')
                            ),
                            'revenue_growth': self._safe_float(
                                self._pick_first_available(row, '营收同比', '营业收入同比增长率', '营业总收入同比增长率'),
                                scale=0.01,
                            ),
                            'net_profit': self._safe_float(
                                self._pick_first_available(row, '净利润', '归母净利润')
                            ),
                            'profit_growth': self._safe_float(
                                self._pick_first_available(row, '净利润同比', '净利润同比增长率', '归母净利润同比增长率'),
                                scale=0.01,
                            ),
                            'gross_margin': self._safe_float(
                                self._pick_first_available(row, '毛利率', '销售毛利率'),
                                scale=0.01,
                            ),
                            'net_margin': self._safe_float(
                                self._pick_first_available(row, '净利率', '销售净利率'),
                                scale=0.01,
                            ),
                            'roe': self._safe_float(
                                self._pick_first_available(row, 'ROE', '净资产收益率'),
                                scale=0.01,
                            ),
                            'data_source': 'efinance',
                        }
                except Exception as e:
                    logger.debug(f"efinance 财务数据获取失败: {e}")

            return None
        
        return self._get_with_cache(cache_key, fetch)
    
    def get_valuation_data(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取估值数据"""
        code = stock_code.replace('SH', '').replace('SZ', '').replace('BJ', '')
        cache_key = f"valuation_{code}"
        
        def fetch():
            # 优先使用 akshare 获取真实估值数据
            if 'akshare' in self.data_sources:
                try:
                    # 获取个股信息（含PE、PB等）
                    indicator_func = getattr(self.ak, 'stock_a_indicator_lg', None)
                    if indicator_func is not None:
                        df = indicator_func(symbol=code)
                    else:
                        df = None
                    if df is not None and not df.empty:
                        latest = df.iloc[-1]
                        pe_ttm = self._safe_float(
                            self._pick_first_available(latest, 'pe_ttm', '市盈率TTM', '市盈率')
                        )
                        pb = self._safe_float(
                            self._pick_first_available(latest, 'pb', '市净率')
                        )
        
                        # 获取行业PE作为参考
                        industry_pe = 25  # 默认值
                        try:
                            # 尝试获取行业估值
                            industry_df = self.ak.stock_board_industry_name_em()
                            # 根据个股所属行业获取行业PE
                            # 简化处理：使用默认值 + 一定波动
                            industry_pe = 25
                        except Exception:
                            pass

                        # 估算PE百分位（基于历史数据简化计算）
                        if len(df) >= 100 and pe_ttm > 0:
                            hist_pe = df['pe_ttm'].dropna()
                            if len(hist_pe) > 0:
                                pe_percentile = float((hist_pe < pe_ttm).sum() / len(hist_pe))
                            else:
                                pe_percentile = 0.5
                        else:
                            pe_percentile = 0.5

                        result = {
                            'pe_ttm': round(pe_ttm, 2),
                            'pb': round(pb, 2),
                            'industry_pe': industry_pe,
                            'pe_percentile': round(pe_percentile, 2),
                            'market_cap': 0,
                            'circulating_market_cap': 0,
                            'data_source': 'akshare',
                        }

                        # 尝试获取市值数据
                        try:
                            quote = self.get_realtime_quote(stock_code)
                            if quote and quote.get('current_price', 0) > 0:
                                # 市值估算需要总股本信息，这里简化处理
                                result['market_cap'] = 0
                                result['circulating_market_cap'] = 0
                        except Exception:
                            pass

                        return result
                    logger.debug("akshare 估值数据接口不可用或返回空数据")
                except Exception as e:
                    logger.debug(f"akshare 估值数据获取失败: {e}")

            akshare_baidu_result = self._get_akshare_baidu_valuation(code)
            if akshare_baidu_result is not None:
                return akshare_baidu_result

            # 备选：efinance 获取基本信息
            if 'efinance' in self.data_sources:
                try:
                    df = self._get_efinance_base_info(code)
                    if df is not None and not df.empty:
                        row = df.iloc[0]
                        return {
                            'pe_ttm': self._safe_float(
                                self._pick_first_available(row, '市盈率-动态', '市盈率(动)', '市盈率')
                            ),
                            'pb': self._safe_float(
                                self._pick_first_available(row, '市净率', 'PB')
                            ),
                            'industry_pe': 25,
                            'pe_percentile': 0.5,
                            'market_cap': self._safe_float(
                                self._pick_first_available(row, '总市值')
                            ),
                            'circulating_market_cap': self._safe_float(
                                self._pick_first_available(row, '流通市值')
                            ),
                            'data_source': 'efinance',
                        }
                except Exception as e:
                    logger.debug(f"efinance 估值数据获取失败: {e}")

            # 兜底：返回默认估值并标注
            logger.warning(f"无法获取 {stock_code} 的真实估值数据，使用默认值")
            return {
                'pe_ttm': 0,
                'pb': 0,
                'industry_pe': 0,
                'pe_percentile': 0,
                'market_cap': 0,
                'circulating_market_cap': 0,
                'data_source': 'default',  # 标记为默认值
            }

        return self._get_with_cache(cache_key, fetch)
    
    def get_news(self, stock_code: str, limit: int = 5) -> Optional[List[Dict[str, Any]]]:
        """获取股票新闻"""
        code = stock_code.replace('SH', '').replace('SZ', '').replace('BJ', '')
        cache_key = f"news_{code}_{limit}"
    
        def fetch():
            # 尝试使用 akshare 获取新闻
            if 'akshare' in self.data_sources:
                try:
                    df = self.ak.stock_news_em(symbol=code)
                    if df is not None and not df.empty:
                        news_list = []
                        for _, row in df.head(limit).iterrows():
                            news_list.append({
                                'title': str(row.get('新闻标题', '')),
                                'content': str(row.get('新闻内容', ''))[:200],
                                'date': str(row.get('发布时间', '')),
                                'source': str(row.get('文章来源', '')),
                            })
                        return news_list
                except Exception as e:
                    logger.debug(f"akshare 新闻获取失败: {e}")

            # 无法获取新闻时返回空列表
            return []

        return self._get_with_cache(cache_key, fetch)

    # ============================================================
    # 模拟数据生成器（网络故障时的兜底方案）
    # ============================================================
    
    def _generate_mock_technical_data(self, stock_code: str) -> Dict[str, Any]:
        """生成模拟技术数据（用于网络故障时的兜底）"""
        import hashlib
        
        # 使用股票代码生成确定性随机数种子，保证同一股票每次生成相同数据
        seed = int(hashlib.md5(stock_code.encode()).hexdigest()[:8], 16) % 10000
        np.random.seed(seed)
        
        # 生成模拟价格（基于真实股票的大致价格区间）
        base_price = 50 + (seed % 200)  # 50-250元区间

        logger.info(f"⚠️ 使用模拟数据生成技术指标（{stock_code}），数据仅供参考，不具实际参考价值")
        current_price = base_price * (1 + np.random.uniform(-0.1, 0.1))
        
        # 生成模拟技术指标
        ma5 = current_price * (1 + np.random.uniform(-0.02, 0.02))
        ma10 = current_price * (1 + np.random.uniform(-0.03, 0.03))
        ma20 = current_price * (1 + np.random.uniform(-0.05, 0.05))
        ma60 = current_price * (1 + np.random.uniform(-0.08, 0.08))
        
        # MACD
        dif = np.random.uniform(-1, 1)
        dea = dif * np.random.uniform(0.6, 0.9)
        
        # RSI
        rsi6 = np.random.uniform(40, 70)
        rsi12 = np.random.uniform(40, 65)
        rsi24 = np.random.uniform(35, 60)
        
        # KDJ
        k = np.random.uniform(40, 70)
        d = k * np.random.uniform(0.85, 0.95)
        j = 3 * k - 2 * d
        
        return {
            'current_price': round(current_price, 2),
            'prev_close': round(current_price * (1 - np.random.uniform(-0.03, 0.03)), 2),
            'open': round(current_price * (1 + np.random.uniform(-0.01, 0.01)), 2),
            'high': round(current_price * (1 + np.random.uniform(0, 0.03)), 2),
            'low': round(current_price * (1 - np.random.uniform(0, 0.03)), 2),
            'volume': int(np.random.uniform(10000000, 50000000)),
            'amount': int(np.random.uniform(500000000, 3000000000)),
            
            # 均线
            'ma5': round(ma5, 2),
            'ma10': round(ma10, 2),
            'ma20': round(ma20, 2),
            'ma60': round(ma60, 2),
            
            # MACD
            'macd': {
                'dif': round(dif, 3),
                'dea': round(dea, 3),
                'histogram': round((dif - dea) * 2, 3)
            },
            
            # RSI
            'rsi': {
                'rsi6': round(rsi6, 2),
                'rsi12': round(rsi12, 2),
                'rsi24': round(rsi24, 2)
            },
            
            # KDJ
            'kdj': {
                'k': round(k, 2),
                'd': round(d, 2),
                'j': round(j, 2)
            },
            
            # 支撑压力
            'support_levels': [round(current_price * 0.95, 2), round(ma20, 2)],
            'resistance_levels': [round(current_price * 1.05, 2), round(current_price * 1.10, 2)],
            'recent_high': round(current_price * 1.08, 2),
            'recent_low': round(current_price * 0.92, 2),
            
            # 变化
            'change_pct': round(np.random.uniform(-3, 3), 2),
            
            # 中期趋势
            'weekly_trend': '中期震荡',

            # 标记数据来源
            'data_source': 'mock',  # 标记为模拟数据
        }
    
    # ============================================================
    # 综合数据
    # ============================================================
    
    def get_full_data(self, stock_code: str) -> Dict[str, Any]:
        """获取完整数据"""
        return {
            'technical': self.get_technical_indicators(stock_code),
            'fund_flow': self.get_fund_flow(stock_code),
            'north_bound': self.get_north_bound_flow(),
            'market': self.get_market_data(),
            'financial': self.get_financial_data(stock_code),
            'valuation': self.get_valuation_data(stock_code),
            'quote': self.get_realtime_quote(stock_code),
        }


# 全局实例
data_fetcher = DataFetcher()
