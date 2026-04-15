"""
LLM Agent 基类
基于 LLM 的智能 Agent 实现
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import json
import logging

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
        # 尝试提取 JSON
        content = content.strip()
        
        # 查找 JSON 块
        json_start = content.find('{')
        json_end = content.rfind('}')
        
        if json_start != -1 and json_end != -1 and json_start < json_end:
            json_str = content[json_start:json_end + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
        
        # 尝试整体解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # 返回原始内容
        return {"raw_content": content}
    
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
