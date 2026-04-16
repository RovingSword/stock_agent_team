import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.data_fetcher import DataFetcher


class TestDataFetcherFundamentalFallbacks(unittest.TestCase):
    def setUp(self):
        init_patch = patch.object(DataFetcher, "_init_data_sources", lambda self: None)
        self.addCleanup(init_patch.stop)
        init_patch.start()

        self.fetcher = DataFetcher()
        self.fetcher.data_sources = []
        self.fetcher.ak = None
        self.fetcher.ef = None

    def test_valuation_falls_back_to_efinance_and_supports_new_pe_column_name(self):
        self.fetcher.data_sources = ["akshare", "efinance"]
        self.fetcher.ak = SimpleNamespace()
        self.fetcher.ef = SimpleNamespace(
            stock=SimpleNamespace(get_base_info=lambda codes: None)
        )

        efinance_df = pd.DataFrame(
            [
                {
                    "股票代码": "002202",
                    "市盈率(动)": 37.8,
                    "市净率": 2.7,
                    "总市值": 104876672105.01,
                    "流通市值": 83515831161.23,
                }
            ]
        )

        with patch.object(
            self.fetcher,
            "_call_efinance_safely",
            return_value=efinance_df,
        ):
            valuation = self.fetcher.get_valuation_data("002202")

        self.assertEqual(valuation["data_source"], "efinance")
        self.assertAlmostEqual(valuation["pe_ttm"], 37.8)
        self.assertAlmostEqual(valuation["pb"], 2.7)

    def test_financial_uses_efinance_when_akshare_returns_empty_dataframe(self):
        self.fetcher.data_sources = ["akshare", "efinance"]
        self.fetcher.ak = SimpleNamespace(
            stock_financial_analysis_indicator=lambda symbol: pd.DataFrame()
        )
        self.fetcher.ef = SimpleNamespace(
            stock=SimpleNamespace(get_base_info=lambda codes: None)
        )

        efinance_df = pd.DataFrame(
            [
                {
                    "股票代码": "002202",
                    "净利润": 2774356663.48,
                    "ROE": 7.08,
                    "毛利率": 14.1839723919,
                    "净利率": 4.1419112776,
                }
            ]
        )

        with patch.object(
            self.fetcher,
            "_call_efinance_safely",
            return_value=efinance_df,
        ):
            financial = self.fetcher.get_financial_data("002202")

        self.assertIsNotNone(financial)
        self.assertAlmostEqual(financial["net_profit"], 2774356663.48)
        self.assertAlmostEqual(financial["roe"], 0.0708)
        self.assertAlmostEqual(financial["gross_margin"], 0.141839723919)
        self.assertAlmostEqual(financial["net_margin"], 0.041419112776)

    def test_valuation_retries_direct_efinance_call_when_safe_wrapper_returns_none(self):
        self.fetcher.data_sources = ["efinance"]
        efinance_df = pd.DataFrame(
            [
                {
                    "股票代码": "002202",
                    "市盈率(动)": 37.8,
                    "市净率": 2.7,
                    "总市值": 104876672105.01,
                    "流通市值": 83515831161.23,
                }
            ]
        )
        direct_get_base_info = lambda codes: efinance_df
        self.fetcher.ef = SimpleNamespace(
            stock=SimpleNamespace(get_base_info=direct_get_base_info)
        )

        with patch.object(
            self.fetcher,
            "_call_efinance_safely",
            return_value=None,
        ):
            valuation = self.fetcher.get_valuation_data("002202")

        self.assertEqual(valuation["data_source"], "efinance")
        self.assertAlmostEqual(valuation["pe_ttm"], 37.8)

    def test_financial_retries_direct_efinance_call_when_safe_wrapper_returns_none(self):
        self.fetcher.data_sources = ["efinance"]
        efinance_df = pd.DataFrame(
            [
                {
                    "股票代码": "002202",
                    "净利润": 2774356663.48,
                    "ROE": 7.08,
                    "毛利率": 14.1839723919,
                    "净利率": 4.1419112776,
                }
            ]
        )
        direct_get_base_info = lambda codes: efinance_df
        self.fetcher.ef = SimpleNamespace(
            stock=SimpleNamespace(get_base_info=direct_get_base_info)
        )

        with patch.object(
            self.fetcher,
            "_call_efinance_safely",
            return_value=None,
        ):
            financial = self.fetcher.get_financial_data("002202")

        self.assertIsNotNone(financial)
        self.assertAlmostEqual(financial["net_profit"], 2774356663.48)

    def test_valuation_uses_akshare_baidu_series_when_legacy_interface_is_missing(self):
        self.fetcher.data_sources = ["akshare"]

        def stock_zh_valuation_baidu(symbol, indicator, period):
            dataset = {
                "市盈率(TTM)": pd.DataFrame(
                    [{"date": "2026-04-14", "value": 36.5}, {"date": "2026-04-15", "value": 38.1}]
                ),
                "市净率": pd.DataFrame(
                    [{"date": "2026-04-14", "value": 2.63}, {"date": "2026-04-15", "value": 2.72}]
                ),
                "总市值": pd.DataFrame(
                    [{"date": "2026-04-14", "value": 1068.62}, {"date": "2026-04-15", "value": 1056.79}]
                ),
            }
            return dataset[indicator]

        self.fetcher.ak = SimpleNamespace(
            stock_zh_valuation_baidu=stock_zh_valuation_baidu,
        )

        valuation = self.fetcher.get_valuation_data("002202")

        self.assertEqual(valuation["data_source"], "akshare_baidu")
        self.assertAlmostEqual(valuation["pe_ttm"], 38.1)
        self.assertAlmostEqual(valuation["pb"], 2.72)
        self.assertAlmostEqual(valuation["market_cap"], 1056.79 * 100000000)

    def test_financial_uses_akshare_new_ths_summary_when_indicator_table_is_empty(self):
        self.fetcher.data_sources = ["akshare"]

        def stock_financial_abstract_new_ths(symbol):
            return pd.DataFrame(
                [
                    {"report_date": "2025-12-31", "metric_name": "operating_income_total", "value": "73023477737.2700"},
                    {"report_date": "2025-12-31", "metric_name": "calculate_operating_income_total_yoy_growth_ratio", "value": "28.79110400"},
                    {"report_date": "2025-12-31", "metric_name": "parent_holder_net_profit", "value": "2774356663.4800"},
                    {"report_date": "2025-12-31", "metric_name": "calculate_parent_holder_net_profit_yoy_growth_ratio", "value": "49.12319000"},
                    {"report_date": "2025-12-31", "metric_name": "sale_gross_margin", "value": "14.1840"},
                    {"report_date": "2025-12-31", "metric_name": "sale_net_interest_ratio", "value": "4.1419"},
                    {"report_date": "2025-12-31", "metric_name": "index_full_diluted_roe", "value": "6.3872"},
                ]
            )

        self.fetcher.ak = SimpleNamespace(
            stock_financial_analysis_indicator=lambda symbol: pd.DataFrame(),
            stock_financial_abstract_new_ths=stock_financial_abstract_new_ths,
        )

        financial = self.fetcher.get_financial_data("002202")

        self.assertEqual(financial["data_source"], "akshare_ths")
        self.assertAlmostEqual(financial["revenue"], 73023477737.27)
        self.assertAlmostEqual(financial["revenue_growth"], 0.28791104)
        self.assertAlmostEqual(financial["net_profit"], 2774356663.48)
        self.assertAlmostEqual(financial["profit_growth"], 0.4912319)
        self.assertAlmostEqual(financial["gross_margin"], 0.14184)
        self.assertAlmostEqual(financial["net_margin"], 0.041419)
        self.assertAlmostEqual(financial["roe"], 0.063872)

