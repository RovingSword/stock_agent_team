"""
LLM Agent 基类
基于 LLM 的智能 Agent 实现
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import json
import logging
import re

from .models import (
    AgentReport, 
    DiscussionMessage, 
    LLMResponse,
    StockAnalysisContext
)


def _get_llm():
    """获取 LLM 模块的 get_provider 函数"""
    try:
        from llm import get_provider
        return get_provider
    except ImportError:
        # 回退到 Mock
        from llm.providers import MockProvider
        return lambda name, **kwargs: MockProvider()


class BaseLLMAgent(ABC):
    """
    LLM Agent 基类
    
    提供基于 LLM 的智能分析能力，
    支持对话历史、上下文管理、结构化输出
    """
    
    # 子类必须定义
    DEFAULT_SYSTEM_PROMPT: str = ""
    AGENT_ROLE: str = "assistant"
    ROLE_DESCRIPTION: str = "智能助手"  # 角色描述，用于讨论时展示
    
    def __init__(
        self,
        name: str,
        role: str,
        provider: str = "mock",
        model: str = "default",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout: int = 60,
        # LLM 配置参数
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs
    ):
        """
        初始化 LLM Agent
        
        Args:
            name: Agent 名称
            role: Agent 角色
            provider: LLM Provider 名称 (mock/qwen/deepseek/zhipu/moonshot/openai_compatible)
            model: 模型名称
            system_prompt: 自定义 system prompt
            temperature: 温度参数 (0-1)
            max_tokens: 最大 token 数
            timeout: 超时时间(秒)
            api_key: API Key (可选，用于自定义配置)
            base_url: API Base URL (可选，用于自定义配置)
            **kwargs: 其他 LLM 配置参数
        """
        self.name = name
        self.role = role
        self.role_description = self.ROLE_DESCRIPTION  # 角色描述
        self.provider_name = provider
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        
        # LLM 配置参数（用于创建 Provider）
        self._llm_config = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout,
        }
        if api_key:
            self._llm_config["api_key"] = api_key
        if base_url:
            self._llm_config["base_url"] = base_url
        if kwargs:
            self._llm_config.update(kwargs)
        
        # System prompt
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        
        # 对话历史
        self.conversation_history: List[Dict[str, str]] = []
        self._initialize_conversation()
        
        # 获取 LLM Provider
        self._llm = None
        
        # 日志
        self.logger = logging.getLogger(f"llm_agent.{role}")
    
    @property
    def llm(self):
        """延迟加载 LLM Provider"""
        if self._llm is None:
            get_provider = _get_llm()
            self._llm = get_provider(self.provider_name, **self._llm_config)
        return self._llm
    
    def _initialize_conversation(self):
        """初始化对话"""
        self.conversation_history = []
        if self.system_prompt:
            self.conversation_history.append({
                "role": "system",
                "content": self.system_prompt
            })
    
    def chat(self, user_message: str, **kwargs) -> str:
        """
        发送消息给 LLM 并获取响应
        
        Args:
            user_message: 用户消息
            **kwargs: 额外参数
            
        Returns:
            LLM 响应内容
        """
        # 添加用户消息
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        try:
            # 构建消息列表
            from llm.base_provider import ChatMessage
            messages = [
                ChatMessage(role=msg["role"], content=msg["content"])
                for msg in self.conversation_history
            ]
            
            # 调用 LLM
            response = self.llm.chat_with_history(
                messages=messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
            )
            
            # 解析响应
            content = response.content
            
            # 添加助手回复到历史
            self.conversation_history.append({
                "role": "assistant",
                "content": content
            })
            
            return content
            
        except Exception as e:
            self.logger.error(f"LLM 调用失败: {e}")
            return self._fallback_response(str(e))

    def discuss_reply(self, user_message: str, **kwargs) -> str:
        """
        圆桌讨论专用：单轮自然语言短答，不写入 JSON 分析范式，也不污染 chat 历史。
        """
        from llm.base_provider import ChatMessage

        sys_prompt = (
            f"你是投研团队中的「{self.role_description}」（{self.name}）。\n"
            "当前为讨论环节：请用中文自然段落回答，2～6 句话；可引用输入中的数据与观点。\n"
            "禁止输出 JSON、YAML、Markdown 代码块；避免生成长编号清单，以连贯叙述为主。"
        )
        messages = [
            ChatMessage(role="system", content=sys_prompt),
            ChatMessage(role="user", content=user_message),
        ]
        try:
            response = self.llm.chat_with_history(
                messages=messages,
                temperature=kwargs.get("temperature", min(self.temperature, 0.65)),
                max_tokens=kwargs.get("max_tokens", min(self.max_tokens, 600)),
            )
            return (response.content or "").strip()
        except Exception as e:
            self.logger.error(f"讨论回应失败: {e}")
            return f"（讨论回应暂不可用：{e}）"

    def _fallback_response(self, error: str) -> str:
        """降级响应"""
        return json.dumps({
            "error": str(error),
            "score": 5.0,
            "confidence": 0.3,
            "summary": "分析过程出现错误",
            "analysis": f"系统发生错误: {error}",
            "risks": ["系统异常"],
            "opportunities": []
        }, ensure_ascii=False)
    
    def parse_structured_response(self, content: str) -> Dict[str, Any]:
        """
        解析结构化响应
        
        尝试从 LLM 响应中解析 JSON 结构
        
        Args:
            content: LLM 响应内容
            
        Returns:
            解析后的字典
        """
        content = content.strip()

        parsed_json = self._extract_json_payload(content)
        if parsed_json is not None:
            normalized = self._normalize_structured_payload(parsed_json)
            normalized["raw_content"] = content
            normalized["parse_mode"] = "json"
            return normalized

        parsed_text = self._extract_text_payload(content)
        if parsed_text:
            normalized = self._normalize_structured_payload(parsed_text)
            normalized["raw_content"] = content
            normalized["parse_mode"] = "text"
            return normalized

        return {
            "raw_content": content,
            "summary": content[:100] if content else "",
            "analysis": content,
            "parse_mode": "raw",
        }

    def _extract_json_payload(self, content: str) -> Optional[Dict[str, Any]]:
        """优先从 JSON 内容中提取结构化数据"""
        json_start = content.find('{')
        json_end = content.rfind('}')

        if json_start != -1 and json_end != -1 and json_start < json_end:
            json_str = content[json_start:json_end + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None

    def _extract_text_payload(self, content: str) -> Dict[str, Any]:
        """兼容纯文本格式的兜底解析"""
        field_aliases = {
            "score": ("评分", "score"),
            "confidence": ("置信度", "confidence"),
            "summary": ("摘要", "summary", "总结"),
            "analysis": ("分析", "analysis", "详细分析"),
            "risks": ("风险", "风险点", "risks"),
            "opportunities": ("机会", "机会点", "opportunities"),
            "decision": ("决策", "decision"),
            "action": ("操作", "建议", "action"),
            "target_price": ("目标价", "target_price"),
            "stop_loss": ("止损", "stop_loss"),
            "position_ratio": ("仓位", "position_ratio"),
        }

        extracted: Dict[str, Any] = {}
        for key, aliases in field_aliases.items():
            value = self._match_labeled_value(content, aliases)
            if value:
                extracted[key] = value

        return extracted

    @staticmethod
    def _match_labeled_value(content: str, labels) -> Optional[str]:
        for label in labels:
            pattern = rf"(?:^|\n)\s*{re.escape(label)}\s*[:：]\s*(.+?)(?=\n\s*[\u4e00-\u9fa5A-Za-z_]+\s*[:：]|\Z)"
            match = re.search(pattern, content, flags=re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        return None

    def _normalize_structured_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """统一结构化字段类型，避免下游反复兜底"""
        normalized = dict(payload)

        if "score" in normalized:
            normalized["score"] = self._safe_float(normalized.get("score"))
        if "confidence" in normalized:
            normalized["confidence"] = self._safe_float(normalized.get("confidence"))
        if "target_price" in normalized:
            normalized["target_price"] = self._safe_float(normalized.get("target_price"))
        if "stop_loss" in normalized:
            normalized["stop_loss"] = self._safe_float(normalized.get("stop_loss"))
        if "position_ratio" in normalized:
            normalized["position_ratio"] = self._safe_float(normalized.get("position_ratio"))

        normalized["risks"] = self._ensure_list(normalized.get("risks"))
        normalized["opportunities"] = self._ensure_list(normalized.get("opportunities"))

        for field in ("summary", "analysis", "decision", "action"):
            value = normalized.get(field)
            if value is not None and not isinstance(value, str):
                normalized[field] = str(value)

        if "chart_key_levels" in normalized:
            normalized["chart_key_levels"] = self._normalize_chart_key_levels(
                normalized.get("chart_key_levels")
            )

        return normalized

    @staticmethod
    def _normalize_chart_key_levels(raw: Any) -> List[Dict[str, Any]]:
        """K 线图关键价位：kind + price + label，与 web.api.analyze 约定一致。"""
        out: List[Dict[str, Any]] = []
        if not isinstance(raw, list):
            return out
        kind_alias = {"支撑": "support", "阻力": "resistance", "压力": "resistance"}
        for item in raw[:8]:
            if not isinstance(item, dict):
                continue
            price = BaseLLMAgent._safe_float(item.get("price"))
            if price is None or price <= 0:
                continue
            kind = str(item.get("kind") or item.get("type") or "other").lower()
            if kind in kind_alias:
                kind = kind_alias[kind]
            label = item.get("label") or item.get("name") or kind
            out.append({"kind": kind, "price": round(price, 4), "label": str(label)[:48]})
        return out

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip()
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return None
        return float(match.group(0))

    @staticmethod
    def _ensure_list(value: Any) -> List[str]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]

        text = str(value).strip()
        if not text:
            return []

        parts = re.split(r"[,\n;；、]+", text)
        return [part.strip(" -") for part in parts if part.strip(" -")]

    def build_agent_report(
        self,
        response: str,
        result: Dict[str, Any],
        default_summary: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentReport:
        """基于统一解析结果构建 AgentReport"""
        analysis = result.get("analysis") or result.get("raw_content") or response
        summary = result.get("summary") or (analysis[:100] if analysis else default_summary)

        return AgentReport(
            agent_name=self.name,
            agent_role=self.role,
            score=result.get("score") if result.get("score") is not None else 0.0,
            confidence=result.get("confidence") if result.get("confidence") is not None else 0.5,
            summary=summary or default_summary,
            analysis=analysis or response,
            risks=self._ensure_list(result.get("risks")),
            opportunities=self._ensure_list(result.get("opportunities")),
            metadata=metadata or {}
        )
    
    @abstractmethod
    def analyze(self, context: StockAnalysisContext) -> AgentReport:
        """
        执行分析
        
        Args:
            context: 分析上下文
            
        Returns:
            分析报告
        """
        pass
    
    def build_analysis_prompt(self, context: StockAnalysisContext) -> str:
        """
        构建分析提示词
        
        子类可重写此方法自定义提示词
        
        Args:
            context: 分析上下文
            
        Returns:
            提示词
        """
        return f"""请分析以下股票:

{context.to_prompt_context()}

请以 JSON 格式输出分析结果，包含:
- score: 0-10 的评分
- confidence: 0-1 的置信度
- summary: 一句话总结
- analysis: 详细分析
- risks: 风险点列表
- opportunities: 机会点列表
"""
    
    def clear_history(self):
        """清空对话历史"""
        self._initialize_conversation()
        self.logger.info(f"{self.name} 对话历史已清空")
    
    def get_history(self) -> List[Dict[str, str]]:
        """获取对话历史"""
        return self.conversation_history.copy()
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name}, role={self.role})>"


class DiscussionAgent(BaseLLMAgent):
    """
    支持讨论的 LLM Agent
    
    适用于多 Agent 讨论场景
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.discussion_history: List[DiscussionMessage] = []
        self.current_round: int = 0
    
    def add_discussion_message(
        self,
        content: str,
        message_type: str = "opinion"
    ) -> DiscussionMessage:
        """
        添加讨论消息
        
        Args:
            content: 消息内容
            message_type: 消息类型
            
        Returns:
            讨论消息对象
        """
        msg = DiscussionMessage(
            agent_name=self.name,
            content=content,
            round=self.current_round,
            message_type=message_type
        )
        self.discussion_history.append(msg)
        return msg
    
    def start_new_round(self):
        """开始新一轮讨论"""
        self.current_round += 1
    
    def get_discussion_summary(self) -> str:
        """获取讨论摘要"""
        if not self.discussion_history:
            return "暂无讨论记录"
        
        summary_parts = [f"=== 讨论摘要 (共 {len(self.discussion_history)} 条消息) ==="]
        
        for msg in self.discussion_history[-5:]:  # 最近5条
            summary_parts.append(
                f"[{msg.agent_name}] ({msg.message_type}): {msg.content[:100]}..."
            )
        
        return "\n".join(summary_parts)
    
    def clear_discussion(self):
        """清空讨论历史"""
        self.discussion_history = []
        self.current_round = 0


__all__ = [
    'BaseLLMAgent',
    'DiscussionAgent',
    'AgentReport',
    'DiscussionMessage',
    'LLMResponse',
    'StockAnalysisContext'
]
