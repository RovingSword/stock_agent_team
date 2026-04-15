"""
测试 LLM API 连接
"""
import os
import sys

# 直接设置环境变量
os.environ["OPENAI_API_KEY"] = "sk-mgzorsYLeEFnIJHrK2B1LQurNOn5VCj3nrSAtXymUGToTzcb"
os.environ["OPENAI_BASE_URL"] = "https://www.dmxapi.cn/v1"

print("=" * 60)
print("LLM API 连接测试")
print("=" * 60)

# 检查环境变量
api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL")

print(f"\n【配置信息】")
print(f"  API Key: {api_key[:20]}...{api_key[-10:] if api_key else '未设置'}")
print(f"  Base URL: {base_url}")

if not api_key:
    print("\n❌ API Key 未设置，请检查 .env 文件")
    sys.exit(1)

# 测试 OpenAI 兼容接口
print(f"\n【测试 OpenAI 兼容接口】")
try:
    from openai import OpenAI
    
    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )
    
    print("  发送测试请求...")
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # 先用通用模型测试
        messages=[
            {"role": "system", "content": "你是一个股票分析师助手。"},
            {"role": "user", "content": "请用一句话介绍你自己。"}
        ],
        max_tokens=100,
        temperature=0.7
    )
    
    print(f"\n  ✅ API 连接成功！")
    print(f"\n  模型: {response.model}")
    print(f"  响应: {response.choices[0].message.content}")
    print(f"  Token 使用: prompt={response.usage.prompt_tokens}, completion={response.usage.completion_tokens}")
    
except Exception as e:
    print(f"\n  ❌ API 连接失败: {e}")
    sys.exit(1)

# 测试可用模型
print(f"\n【查询可用模型】")
try:
    models = client.models.list()
    model_list = [m.id for m in models.data[:10]]  # 只显示前10个
    print(f"  可用模型: {model_list}")
except Exception as e:
    print(f"  无法获取模型列表: {e}")

print("\n" + "=" * 60)
print("测试完成 ✅")
print("=" * 60)
