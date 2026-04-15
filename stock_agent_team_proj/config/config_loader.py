"""
LLM 配置加载器
提供配置加载、环境变量替换和便捷访问接口
"""
import os
import re
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from functools import lru_cache


@dataclass
class ProviderConfig:
    """模型提供商配置"""
    api_key_env: str
    base_url: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 2000
    
    @property
    def api_key(self) -> Optional[str]:
        """从环境变量获取 API Key"""
        return os.environ.get(self.api_key_env)
    
    @property
    def has_api_key(self) -> bool:
        """检查是否配置了 API Key"""
        key = self.api_key
        return key is not None and key != "" and key != "your_api_key_here"


@dataclass
class AgentConfig:
    """Agent 配置"""
    provider: str
    temperature: float = 0.7


@dataclass
class DiscussionConfig:
    """讨论配置"""
    max_rounds: int = 3
    enable_debate: bool = True


class ConfigLoader:
    """配置加载器"""
    
    DEFAULT_CONFIG_NAME = "llm_config.yaml"
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置加载器
        
        Args:
            config_path: 配置文件路径，默认使用 config/llm_config.yaml
        """
        if config_path is None:
            # 查找配置文件
            possible_paths = [
                Path(__file__).parent / self.DEFAULT_CONFIG_NAME,
                Path.cwd() / "config" / self.DEFAULT_CONFIG_NAME,
                Path.cwd() / self.DEFAULT_CONFIG_NAME,
            ]
            for path in possible_paths:
                if path.exists():
                    config_path = str(path)
                    break
            else:
                raise FileNotFoundError(
                    f"未找到配置文件，请创建 {self.DEFAULT_CONFIG_NAME}"
                )
        
        self.config_path = Path(config_path)
        self._raw_config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """加载并解析配置文件"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._raw_config = yaml.safe_load(f) or {}
        
        # 替换环境变量
        self._substitute_env_vars(self._raw_config)
    
    def _substitute_env_vars(self, config: Any) -> Any:
        """递归替换配置中的环境变量引用 ${VAR_NAME} 或 $VAR_NAME"""
        if isinstance(config, dict):
            return {k: self._substitute_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._substitute_env_vars(item) for item in config]
        elif isinstance(config, str):
            # 替换 ${VAR_NAME} 格式
            pattern = r'\$\{([^}]+)\}'
            def replace_env_var(match):
                var_name = match.group(1)
                return os.environ.get(var_name, match.group(0))
            return re.sub(pattern, replace_env_var, config)
        return config
    
    def _get_nested(self, keys: list, default: Any = None) -> Any:
        """获取嵌套配置值"""
        value = self._raw_config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        return value
    
    # ========== LLM 配置 ==========
    
    @property
    def default_provider(self) -> str:
        """获取默认 provider"""
        return self._get_nested(['llm', 'default_provider'], 'deepseek')
    
    @property
    def timeout(self) -> int:
        """获取超时时间（秒）"""
        return self._get_nested(['llm', 'timeout'], 60)
    
    @property
    def max_retries(self) -> int:
        """获取最大重试次数"""
        return self._get_nested(['llm', 'max_retries'], 3)
    
    def get_providers(self) -> Dict[str, ProviderConfig]:
        """获取所有 provider 配置"""
        providers = self._get_nested(['llm', 'providers'], {})
        return {
            name: ProviderConfig(**config)
            for name, config in providers.items()
        }
    
    def get_provider(self, name: Optional[str] = None) -> ProviderConfig:
        """获取指定 provider 配置"""
        if name is None:
            name = self.default_provider
        providers = self.get_providers()
        if name not in providers:
            raise ValueError(f"未找到 provider: {name}")
        return providers[name]
    
    def get_provider_config(self, name: Optional[str] = None) -> Dict[str, Any]:
        """获取 provider 的原始配置字典"""
        if name is None:
            name = self.default_provider
        providers = self._get_nested(['llm', 'providers'], {})
        if name not in providers:
            raise ValueError(f"未找到 provider: {name}")
        return providers[name].copy()
    
    # ========== Agent 配置 ==========
    
    def get_agents(self) -> Dict[str, AgentConfig]:
        """获取所有 agent 配置"""
        agents = self._get_nested(['agents'], {})
        return {
            name: AgentConfig(**config)
            for name, config in agents.items()
        }
    
    def get_agent(self, name: str) -> AgentConfig:
        """获取指定 agent 配置"""
        agents = self.get_agents()
        if name not in agents:
            raise ValueError(f"未找到 agent: {name}")
        return agents[name]
    
    def get_agent_provider(self, agent_name: str) -> ProviderConfig:
        """获取指定 agent 使用的 provider 配置"""
        agent_config = self.get_agent(agent_name)
        return self.get_provider(agent_config.provider)
    
    def get_agent_llm_config(self, agent_name: str) -> Dict[str, Any]:
        """获取指定 agent 的完整 LLM 配置（包含 provider 和 agent 级别覆盖）"""
        agent_config = self.get_agent(agent_name)
        provider_config = self.get_provider_config(agent_config.provider)
        
        # 合并配置，agent 级别配置覆盖 provider 级别
        return {
            **provider_config,
            'temperature': agent_config.temperature,
            'provider': agent_config.provider
        }
    
    # ========== 讨论配置 ==========
    
    @property
    def discussion_config(self) -> DiscussionConfig:
        """获取讨论配置"""
        config = self._get_nested(['discussion'], {})
        return DiscussionConfig(**config)
    
    @property
    def max_discussion_rounds(self) -> int:
        """获取最大讨论轮数"""
        return self.discussion_config.max_rounds
    
    @property
    def enable_debate(self) -> bool:
        """是否启用辩论模式"""
        return self.discussion_config.enable_debate
    
    # ========== 验证方法 ==========
    
    def validate(self) -> Dict[str, Any]:
        """
        验证配置完整性
        
        Returns:
            包含错误和警告的字典
        """
        errors = []
        warnings = []
        
        # 检查 default_provider 是否存在
        providers = self.get_providers()
        if self.default_provider not in providers:
            errors.append(
                f"默认 provider '{self.default_provider}' 未在 providers 中定义"
            )
        
        # 检查所有 agent 的 provider 是否存在
        for agent_name, agent_config in self.get_agents().items():
            if agent_config.provider not in providers:
                errors.append(
                    f"Agent '{agent_name}' 使用的 provider '{agent_config.provider}' 未定义"
                )
        
        # 检查 API Key 配置
        for provider_name, provider_config in providers.items():
            if not provider_config.has_api_key:
                warnings.append(
                    f"Provider '{provider_name}' 未配置 API Key "
                    f"(环境变量 {provider_config.api_key_env} 未设置)"
                )
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def get_missing_api_keys(self) -> list:
        """获取缺失 API Key 的 provider 列表"""
        missing = []
        for provider_name, provider_config in self.get_providers().items():
            if not provider_config.has_api_key:
                missing.append({
                    'provider': provider_name,
                    'env_var': provider_config.api_key_env
                })
        return missing
    
    # ========== 便捷方法 ==========
    
    def to_dict(self) -> Dict[str, Any]:
        """导出配置字典"""
        return self._raw_config.copy()
    
    def __repr__(self) -> str:
        return f"ConfigLoader(config_path='{self.config_path}')"


# 全局单例实例
_global_loader: Optional[ConfigLoader] = None


def get_config_loader(config_path: Optional[str] = None) -> ConfigLoader:
    """获取配置加载器单例"""
    global _global_loader
    if _global_loader is None or config_path is not None:
        _global_loader = ConfigLoader(config_path)
    return _global_loader


# 便捷访问函数
@lru_cache(maxsize=1)
def get_llm_config() -> ConfigLoader:
    """获取 LLM 配置加载器（带缓存）"""
    return get_config_loader()
