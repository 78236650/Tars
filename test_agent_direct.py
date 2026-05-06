#!/usr/bin/env python3
"""
直接测试 TARS Agent
"""
import sys
import os
from pathlib import Path

# 添加后端目录到路径
backend_dir = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_dir))

import asyncio
from tars.agent import Agent
from tars.database import Database
from tars.skills import SkillLoader, registry


async def test_weather_query():
    """测试天气查询"""
    print("=" * 60)
    print("TARS Agent 测试 - 天气查询")
    print("=" * 60)
    
    # 初始化
    db = Database()
    agent = Agent(db=db)
    
    # 初始化技能
    loader = SkillLoader(skills_dir="skills")
    loader.create_default_skills()
    
    # 激活天气技能
    registry.activate("weather")
    
    print("\n✅ Agent 已初始化")
    print(f"当前模型: {agent.current_model}")
    
    # 检查可用模型
    models = await agent.get_available_models()
    print(f"可用模型: {models}")
    
    print("\n" + "-" * 60)
    print("测试问题: 明天上海天气情况怎么样")
    print("-" * 60)
    
    # 直接调用 LLM
    from tars.models import ChatMessage
    
    system_prompt = agent.workspace.build_context()
    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content="明天上海天气情况怎么样")
    ]
    
    print("\n📤 发送到 LLM...")
    
    try:
        response = await agent.provider.chat(messages, stream=False)
        
        print("\n📥 Agent 响应:")
        print("-" * 60)
        print(response if isinstance(response, str) else str(response))
        print("-" * 60)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_weather_query())
