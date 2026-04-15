# -*- coding: utf-8 -*-
"""
LLM 适配层使用示例

本文件展示如何使用 LLM 适配层的各种功能。
"""

# ============================================================
# 方式1: 使用 get_provider() 工厂函数（推荐）
# ============================================================

# from llm import get_provider

# # 使用默认配置（从环境变量读取）
# provider = get_provider("qwen")
# response = provider.chat("你好，请介绍一下自己")
# print(response.content)

# # 使用自定义配置
# provider = get_provider(
#     "deepseek",
#     api_key="sk-xxxx",
#     model="deepseek-chat",
#     temperature=0.5
# )
# response = provider.chat("解释一下什么是股票")
# print(response.content)


# ============================================================
# 方式2: 直接导入具体 Provider 类
# ============================================================

# from llm import QwenProvider, DeepSeekProvider, LLMConfig

# # 创建配置
# config = LLMConfig(
#     api_key="your-api-key",
#     model="qwen-plus",
#     temperature=0.7,
#     max_tokens=2000
# )

# # 创建 Provider
# provider = QwenProvider(config)

# # 发送聊天请求
# response = provider.chat(
#     message="你好",
#     system_prompt="你是一个专业的股票分析师"
# )
# print(response.content)
# print(f"使用的模型: {response.model}")
# print(f"Token 使用: {response.usage}")


# ============================================================
# 方式3: 使用带历史记录的多轮对话
# ============================================================

# from llm import get_provider
# from llm import ChatMessage

# provider = get_provider("zhipu")

# messages = [
#     ChatMessage(role="system", content="你是一个股票投资顾问。"),
#     ChatMessage(role="user", content="我想投资科技股，有什么推荐吗？"),
#     ChatMessage(role="assistant", content="科技股投资需要考虑多个因素..."),
#     ChatMessage(role="user", content="那阿里巴巴的股票怎么样？"),
# ]

# response = provider.chat_with_history(messages)
# print(response.content)


# ============================================================
# 方式4: 流式输出
# ============================================================

# from llm import get_provider

# provider = get_provider("moonshot")

# print("流式输出: ")
# for chunk in provider.chat_stream("给我讲一个关于AI的故事"):
#     print(chunk, end="", flush=True)
# print()  # 换行


# ============================================================
# 方式5: 获取模型信息
# ============================================================

# from llm import get_provider

# provider = get_provider("qwen")
# info = provider.get_model_info()
# print(f"Provider: {info['provider_name']}")
# print(f"Model: {info['model']}")
# print(f"Features: {info['features']}")
# print(f"Available Models: {info['available_models']}")


# ============================================================
# 方式6: 工厂单例模式
# ============================================================

# from llm import get_factory

# factory = get_factory()

# # 获取相同的 provider（会复用已有实例）
# provider1 = factory.get_provider("qwen")
# provider2 = factory.get_provider("qwen")  # 复用 provider1

# print(f"Provider 1: {provider1}")
# print(f"Provider 2: {provider2}")
# print(f"是否为同一实例: {provider1 is provider2}")

# # 查看已创建的 providers
# providers = factory.list_providers()
# print(f"已创建的 Providers: {providers}")

# # 清除缓存
# factory.clear_providers()


# ============================================================
# 完整示例：股票分析助手
# ============================================================

def stock_analysis_example():
    """
    完整的股票分析示例
    """
    from llm import get_provider, ChatMessage
    
    # 创建 Provider
    provider = get_provider(
        "qwen",
        model="qwen-plus",
        temperature=0.7
    )
    
    # 定义系统提示
    system_prompt = """你是一个专业的股票投资分析师。请根据用户的问题，
    提供专业、客观的分析意见。注意：
    1. 投资有风险，建议仅供参考
    2. 结合基本面和技术面进行分析
    3. 给出明确的投资建议和风险提示"""
    
    # 单轮对话
    question = "帮我分析一下贵州茅台这只股票，适合长期持有吗？"
    response = provider.chat(question, system_prompt=system_prompt)
    print(f"问题: {question}")
    print(f"回答: {response.content}")
    print(f"模型: {response.model}")
    print(f"Token使用: {response.usage}")
    
    # 多轮对话
    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content="分析一下宁德时代的投资价值"),
    ]
    response = provider.chat_with_history(messages)
    print(f"\n多轮对话回答: {response.content}")


# ============================================================
# 环境变量配置
# ============================================================

# 在使用前，请设置以下环境变量（或在代码中直接传入）：

# 通义千问
# export DASHSCOPE_API_KEY=your_api_key
# export QWEN_MODEL=qwen-plus

# DeepSeek
# export DEEPSEEK_API_KEY=your_api_key
# export DEEPSEEK_MODEL=deepseek-chat

# 智谱AI
# export ZHIPU_API_KEY=your_api_key
# export ZHIPU_MODEL=glm-4

# Moonshot
# export MOONSHOT_API_KEY=your_api_key
# export MOONSHOT_MODEL=moonshot-v1-8k

# OpenAI 兼容
# export OPENAI_API_KEY=your_api_key
# export OPENAI_BASE_URL=http://localhost:8000/v1
# export OPENAI_MODEL=gpt-3.5-turbo


if __name__ == "__main__":
    # 运行示例
    print("=" * 50)
    print("LLM 适配层使用示例")
    print("=" * 50)
    
    # 取消下面的注释来运行完整示例
    # stock_analysis_example()
    
    print("\n请参考文件中的注释来了解如何使用 LLM 适配层。")
