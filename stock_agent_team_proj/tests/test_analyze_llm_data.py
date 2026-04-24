"""
LLM 分析数据装配层回归测试（与 docs/superpowers/specs/2026-04-16 一致）：
- 使用 DataFetcher 的原始分角色 payload，不得用规则引擎评论冒充原始数据。
- current_price 优先 quote/technical，而非默认 0。
- 数据缺口时显式列出，不掩盖。
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import web.api.analyze as analyze


class TestResolveCurrentPrice(unittest.TestCase):
    def test_prefers_quote_price(self):
        full = {
            "quote": {"current_price": 10.5},
            "technical": {"current_price": 9.0},
        }
        p = analyze._resolve_current_price(full, {"current_price": 1.0})
        self.assertEqual(p, 10.5)

    def test_falls_back_to_technical(self):
        full = {
            "quote": {},
            "technical": {"current_price": 8.0},
        }
        p = analyze._resolve_current_price(full, {"current_price": 0})
        self.assertEqual(p, 8.0)

    def test_falls_back_to_execution_last(self):
        full = {"quote": {}, "technical": {}}
        p = analyze._resolve_current_price(full, {"current_price": 3.2})
        self.assertEqual(p, 3.2)

    def test_no_fake_zero(self):
        full = {"quote": {}, "technical": {}}
        p = analyze._resolve_current_price(full, {})
        self.assertIsNone(p)


class TestBuildRolePayloads(unittest.TestCase):
    @patch("web.api.analyze.data_fetcher")
    def test_technical_includes_real_slices_not_score_breakdown(self, _mock_df):
        full = {
            "quote": {"current_price": 12.0, "name": "测试"},
            "technical": {"ma5": 11.0, "current_price": 12.0},
            "news": [],
            "financial": {},
            "market": {},
            "fund_flow": {},
            "north_bound": {},
            "valuation": {},
        }
        payloads = analyze._build_role_payloads("000001", full, 12.0)
        self.assertIn("technical", payloads["technical"])
        self.assertIn("quote", payloads["intelligence"])


class TestBuildLlmAnalysisData(unittest.TestCase):
    @patch("web.api.analyze.data_fetcher")
    def test_uses_get_full_data_per_role(self, mock_fetcher):
        mock_fetcher.get_full_data.return_value = {
            "quote": {"current_price": 7.5},
            "technical": {"rsi": 50},
            "news": [],
            "financial": {"pe": 20},
        }
        mock_fetcher.get_news.return_value = []
        rule = SimpleNamespace(
            score_breakdown={
                "technical": {"score": 6, "comment": "规则摘要", "key_points": ["k"]},
                "intelligence": {"score": 5, "comment": "", "key_points": [], "risk_points": []},
                "risk": {"score": 5, "comment": "", "key_points": [], "risk_points": []},
                "fundamental": {"score": 5, "comment": "", "key_points": [], "risk_points": []},
            },
            execution={"entry_zone": []},
        )
        out = analyze._build_llm_analysis_data("300750", rule)
        self.assertEqual(out["current_price"], 7.5)
        mock_fetcher.get_full_data.assert_called_with("300750")
        # 角色原始数据应来自 full_data 分片
        self.assertIn("technical", out["role_payloads"]["technical"])
        self.assertIn("data_gaps", out)
        self.assertIn("news", out["data_gaps"])


class TestBuildRuleReference(unittest.TestCase):
    def test_no_default_fake_score_five(self):
        rule = SimpleNamespace(
            score_breakdown={},
            execution={},
        )
        ref = analyze._build_rule_reference(rule)
        for role in ("technical", "intelligence", "risk", "fundamental"):
            self.assertIsNone(ref[role].get("score"))


if __name__ == "__main__":
    unittest.main()
