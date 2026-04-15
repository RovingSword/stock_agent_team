#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 LLM Agent Team Web 集成
"""
import os
import sys
import json
import asyncio

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

async def test_llm_analysis():
    """测试LLM Agent分析"""
    from web.api.analyze import generate_sse_events, get_llm_config
    
    print("=" * 60)
    print("LLM Agent Team Web 集成测试")
    print("=" * 60)
    
    # 打印配置
    config = get_llm_config()
    print(f"\nLLM 配置:")
    print(f"  Provider: {config.get('provider')}")
    print(f"  Base URL: {config.get('base_url')}")
    print(f"  Model: {config.get('model')}")
    print(f"  API Key: {'*' * 20}{config.get('api_key', '')[-10:] if config.get('api_key') else 'Not Set'}")
    
    print("\n" + "-" * 60)
    print("生成SSE事件流测试...")
    print("-" * 60)
    
    # 测试生成SSE事件
    events = []
    async for event in generate_sse_events("300750", "宁德时代"):
        events.append(event)
        # 打印前几个事件
        if len(events) <= 15:
            if event.startswith("event:"):
                parts = event.split("\n", 1)
                event_type = parts[0].replace("event:", "").strip()
                if len(parts) > 1:
                    data = parts[1].replace("data:", "").strip()
                    try:
                        data_obj = json.loads(data)
                        print(f"\n[{event_type}] {data_obj.get('round', '')} {data_obj.get('status', '')} {data_obj.get('title', '')}")
                        if 'agent_name' in data_obj:
                            print(f"  Agent: {data_obj['agent_name']}")
                        if 'score' in data_obj:
                            print(f"  Score: {data_obj['score']}")
                    except:
                        print(f"\n[{event_type}] {data[:80]}...")
        else:
            break
    
    print("\n" + "-" * 60)
    print(f"生成了 {len(events)} 个事件")
    
    # 统计事件类型
    event_counts = {}
    for event in events:
        if event.startswith("event:"):
            event_type = event.split("\n")[0].replace("event:", "").strip()
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
    
    print("\n事件类型统计:")
    for event_type, count in event_counts.items():
        print(f"  {event_type}: {count}")
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_llm_analysis())
