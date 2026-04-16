import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.llm import AgentReport
from agents.llm.llm_technical import LLMTechnical
from web.api.analyze import generate_sse_events


class TestLLMStructuredParsing(unittest.TestCase):
    def test_plain_text_analysis_does_not_fall_back_to_default_score(self):
        agent = LLMTechnical(provider="mock")
        agent.chat = lambda prompt: (
            "评分: 7.2\n"
            "置信度: 0.83\n"
            "摘要: 技术形态偏强\n"
            "分析: 趋势向上，量价配合良好。\n"
            "风险: 短线有回撤压力\n"
            "机会: 若放量突破可继续跟踪"
        )

        report = agent.analyze("请分析这只股票")

        self.assertAlmostEqual(report.score, 7.2)
        self.assertAlmostEqual(report.confidence, 0.83)
        self.assertEqual(report.summary, "技术形态偏强")
        self.assertEqual(report.analysis, "趋势向上，量价配合良好。")
        self.assertEqual(report.risks, ["短线有回撤压力"])
        self.assertEqual(report.opportunities, ["若放量突破可继续跟踪"])


class TestLLMStreamingPayload(unittest.IsolatedAsyncioTestCase):
    async def test_final_decision_comes_from_leader_and_keeps_agent_analysis(self):
        class FakeAgent:
            def __init__(self, report):
                self.report = report
                self.name = report.agent_name

            def analyze(self, prompt):
                return self.report

        class FakeLeader:
            def __init__(self):
                self.calls = 0

            def analyze(self, prompt):
                self.calls += 1
                if self.calls == 1:
                    return AgentReport(
                        agent_name="👔 队长",
                        agent_role="leader",
                        score=7.1,
                        confidence=0.74,
                        summary="请大家聚焦关键分歧",
                        analysis="先对技术与风险的分歧做澄清。",
                    )
                return AgentReport(
                    agent_name="👔 队长",
                    agent_role="leader",
                    score=8.6,
                    confidence=0.91,
                    summary="建议买入",
                    analysis="综合判断后，当前更适合分批布局。",
                    risks=["回撤风险"],
                    opportunities=["趋势延续"],
                    metadata={
                        "decision": "buy",
                        "action": "建议买入",
                    },
                )

        fake_team = {
            "technical": FakeAgent(
                AgentReport(
                    agent_name="技术分析员",
                    agent_role="technical",
                    score=7.4,
                    confidence=0.8,
                    summary="技术面转强",
                    analysis="均线拐头向上，量能改善。",
                    risks=["上方压力位"],
                    opportunities=["放量突破"],
                )
            ),
            "intelligence": FakeAgent(
                AgentReport(
                    agent_name="情报员",
                    agent_role="intelligence",
                    score=6.8,
                    confidence=0.76,
                    summary="资金面中性偏多",
                    analysis="北向资金有回流迹象。",
                )
            ),
            "risk": FakeAgent(
                AgentReport(
                    agent_name="风控官",
                    agent_role="risk",
                    score=6.2,
                    confidence=0.72,
                    summary="可控但需轻仓",
                    analysis="短线波动仍然较大。",
                    risks=["市场波动"],
                )
            ),
            "fundamental": FakeAgent(
                AgentReport(
                    agent_name="基本面分析员",
                    agent_role="fundamental",
                    score=7.0,
                    confidence=0.79,
                    summary="基本面稳定",
                    analysis="业绩趋势没有明显恶化。",
                    opportunities=["估值修复"],
                )
            ),
            "leader": FakeLeader(),
        }

        fake_rule_decision = SimpleNamespace(
            score_breakdown={
                "technical": {"score": 6.1},
                "intelligence": {"score": 6.0},
                "risk": {"score": 8.0},
                "fundamental": {"score": 7.5},
            },
            execution={
                "current_price": 123.45,
                "entry_zone": [120.0, 122.0],
                "stop_loss": 116.0,
                "take_profit_1": 128.0,
                "take_profit_2": 132.0,
                "position_size": 0.3,
            },
            rationale={
                "buy_reasons": ["趋势改善"],
                "risk_warnings": ["注意回撤"],
            },
            confidence="medium",
            composite_score=6.7,
            final_action="watch",
        )

        async def collect_events():
            events = []
            with patch("web.api.analyze.create_team", return_value=fake_team), \
                 patch("web.api.analyze.get_llm_config", return_value={
                     "provider": "mock",
                     "api_key": "",
                     "base_url": "",
                     "model": "mock",
                 }), \
                 patch("web.api.analyze.get_team", return_value=SimpleNamespace(
                     analyze=lambda **kwargs: fake_rule_decision
                 )), \
                 patch("web.api.analyze.asyncio.sleep", new=self._async_noop):
                async for raw_event in generate_sse_events("300750", "宁德时代"):
                    if raw_event.startswith("event:"):
                        lines = raw_event.strip().split("\n", 1)
                        event_name = lines[0].split(":", 1)[1].strip()
                        payload = json.loads(lines[1].split(":", 1)[1].strip())
                        events.append((event_name, payload))
            return events

        events = await collect_events()
        final_decision = next(payload for event, payload in events if event == "final_decision")
        done_payload = next(payload for event, payload in events if event == "done")

        self.assertEqual(final_decision["final_action"], "buy")
        self.assertEqual(final_decision["action_text"], "建议买入")
        self.assertAlmostEqual(final_decision["composite_score"], 8.6)
        self.assertEqual(final_decision["confidence"], 0.91)
        self.assertEqual(final_decision["analysis"], "综合判断后，当前更适合分批布局。")
        self.assertEqual(final_decision["agent_scores"][0]["analysis"], "均线拐头向上，量能改善。")
        self.assertIn("risks", final_decision["agent_scores"][0])
        self.assertIn("opportunities", final_decision["agent_scores"][0])
        self.assertEqual(done_payload, final_decision)

    @staticmethod
    async def _async_noop(*args, **kwargs):
        return None

