"""intel_pipeline：结构化报告与 IntelBrief。"""
import unittest

from utils import intel_pipeline as ip


class TestRawIntelPayload(unittest.TestCase):
    def test_extracts_search_lists_only(self):
        raw = {
            "news": [{"title": "a", "summary": "s"}],
            "stock_code": "300750",
            "tracked_at": "2026-01-01",
        }
        p = ip.raw_intel_to_search_payload(raw)
        self.assertEqual(list(p.keys()), ["news"])
        self.assertTrue(ip.cache_intel_has_search_lists(raw))

    def test_empty_when_no_lists(self):
        raw = {"stock_code": "1", "announcements": []}
        self.assertFalse(ip.cache_intel_has_search_lists(raw))


class TestIntelBrief(unittest.TestCase):
    def test_rule_brief_has_role_hints(self):
        report = {
            "gather_time": "2026-04-24 12:00:00",
            "overall_sentiment": "positive",
            "key_positive": ["利好一条"],
            "key_negative": ["风险一条"],
            "hot_topics": ["题材A"],
            "news": [],
            "research": [{"title": "研报", "summary": "目标价 50 元"}],
            "institutional_views": [{"title": "机构", "summary": "看好"}],
            "credibility_summary": {"high_credibility": 3, "low_credibility": 0},
        }
        b = ip.build_rule_based_intel_brief(report, "300750", "测试股", user_request="短线")
        self.assertEqual(b["schema_version"], "intel_brief_v1")
        self.assertIn("technical", b["role_hints"])
        self.assertTrue(b["role_hints"]["technical"])
        self.assertTrue(b["bull_case"])
        sl = ip.slice_brief_for_agent_role(b, "risk")
        self.assertIn("risk_flags", sl)
        txt = ip.format_brief_for_prompt(sl)
        self.assertIn("情报摘要 Brief", txt)
        self.assertIn("核心叙事", txt)


class TestPreparePackage(unittest.TestCase):
    def test_builds_report_and_brief(self):
        raw = {
            "news": [
                {
                    "title": "公司发布业绩预告",
                    "summary": "净利润同比上升",
                    "time": "2026-04-20",
                }
            ],
            "research": [],
            "sentiment": [],
            "tracked_at": "2026-04-24T10:00:00",
        }
        pkg = ip.prepare_intel_package_for_analysis(
            "000001", "平安银行", raw, tracked_at=raw["tracked_at"], user_request=""
        )
        self.assertIsNotNone(pkg)
        report, brief = pkg
        self.assertIn("gather_time", report)
        self.assertIn("core_thesis", brief)


if __name__ == "__main__":
    unittest.main()
