"""
IntelBrief 评测：对比无 Brief / 有 Brief 时首轮 prompt 形态（长度与关键片段）。
固定「标的」用合成数据，不调用外网。
"""
import json
import unittest

from utils.intel_pipeline import (
    build_rule_based_intel_brief,
    prepare_intel_package_for_analysis,
    slice_brief_for_agent_role,
)
import web.api.analyze as analyze


def _synthetic_intel(stock_code: str):
    return {
        "tracked_at": "2026-04-24T12:00:00",
        "news": [
            {
                "title": f"{stock_code} 相关新闻一条",
                "summary": "行业景气度回升，关注订单",
                "time": "2026-04-23",
            }
        ],
        "research": [
            {
                "title": "券商覆盖",
                "summary": "给予增持评级，目标价 88 元",
                "time": "2026-04-22",
            }
        ],
        "sentiment": [],
    }


class TestBriefPromptFootprint(unittest.TestCase):
    def test_technical_prompt_includes_brief_not_full_intel_lists(self):
        stock_code, stock_name = "300750", "示例新能源"
        raw = _synthetic_intel(stock_code)
        pkg = prepare_intel_package_for_analysis(
            stock_code, stock_name, raw, tracked_at=raw["tracked_at"], user_request="波段"
        )
        self.assertIsNotNone(pkg)
        report_dict, brief = pkg

        rule_ref = {"score": 6.0, "comment": "", "key_points": [], "risk_points": [], "execution": {}}
        raw_data = {"quote": {"current_price": 50}, "technical": {"rsi": 55}}

        p_with = analyze._build_llm_agent_prompt(
            agent_name="T",
            role_name="技术分析员",
            stock_code=stock_code,
            stock_name=stock_name,
            current_price=50,
            raw_data=raw_data,
            rule_reference=rule_ref,
            web_intelligence=None,
            agent_role="technical",
            intel_brief_slice=slice_brief_for_agent_role(brief, "technical"),
        )
        self.assertIn("情报摘要 Brief", p_with)
        self.assertNotIn("网络情报结构化报告", p_with)

        p_intel = analyze._build_llm_agent_prompt(
            agent_name="I",
            role_name="情报员",
            stock_code=stock_code,
            stock_name=stock_name,
            current_price=50,
            raw_data=raw_data,
            rule_reference=rule_ref,
            web_intelligence=report_dict,
            agent_role="intelligence",
            intel_brief_slice=slice_brief_for_agent_role(brief, "intelligence"),
        )
        self.assertIn("网络情报结构化报告", p_intel)

        p_without_brief = analyze._build_llm_agent_prompt(
            agent_name="T",
            role_name="技术分析员",
            stock_code=stock_code,
            stock_name=stock_name,
            current_price=50,
            raw_data=raw_data,
            rule_reference=rule_ref,
            web_intelligence=None,
            agent_role="technical",
            intel_brief_slice=None,
        )
        self.assertNotIn("情报摘要 Brief", p_without_brief)
        self.assertLess(len(p_without_brief), len(p_with))

    def test_two_tickers_brief_distinct_thesis(self):
        """两档合成标的：Brief 核心叙事应区分股票名称/代码。"""
        specs = [("600519", "贵州茅台"), ("300750", "宁德时代")]
        theses = []
        for code, name in specs:
            raw = _synthetic_intel(code)
            pkg = prepare_intel_package_for_analysis(code, name, raw, tracked_at=raw["tracked_at"])
            self.assertIsNotNone(pkg)
            _, brief = pkg
            theses.append(brief["core_thesis"])
        self.assertNotEqual(theses[0], theses[1])
        self.assertIn("600519", theses[0])
        self.assertIn("300750", theses[1])

    def test_final_decision_brief_json_placeholder(self):
        """队长最终 prompt 片段：应能嵌入 IntelBrief JSON（此处只测序列化长度）。"""
        report = {
            "gather_time": "2026-04-24 12:00:00",
            "overall_sentiment": "neutral",
            "key_positive": [],
            "key_negative": [],
            "hot_topics": [],
            "news": [],
            "research": [],
        }
        b = build_rule_based_intel_brief(report, "000001", "测试")
        s = json.dumps(b, ensure_ascii=False)
        self.assertGreater(len(s), 50)
        self.assertIn("intel_brief_v1", s)


if __name__ == "__main__":
    unittest.main()
