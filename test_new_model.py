#!/usr/bin/env python3
"""
测试 TARS Agent 使用新模型 gemma4:e2b
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
from tars.execution.weather import WeatherTool


async def test_new_model():
    """测试新模型"""
    print("=" * 60)
    print("TARS Agent - gemma4:e2b 模型测试")
    print("=" * 60)
    
    # 初始化
    db = Database()
    agent = Agent(db=db)
    
    print(f"\n当前模型: {agent.current_model}")
    
    # 检查可用模型
    models = await agent.get_available_models()
    print(f"\n可用模型: {len(models)} 个")
    for model in models[:5]:
        marker = "← 当前" if model == agent.current_model else ""
        print(f"  - {model} {marker}")
    
    # 测试简单对话
    print("\n" + "-" * 60)
    print("测试 1: 简单对话")
    print("-" * 60)
    
    test_queries = [
        "你好，请介绍一下自己",
        "1+1等于多少?",
        "明天上海天气怎么样?",
    ]
    
    for query in test_queries:
        print(f"\n问题: {query}")
        print("-" * 40)
        
        try:
            # 直接调用 LLM
            from tars.models import ChatMessage
            system_prompt = agent.workspace.build_context()
            messages = [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=query)
            ]
            
            response = await agent.provider.chat(messages, stream=False)
            print(f"回答: {response[:200]}...")
            
        except Exception as e:
            print(f"❌ 错误: {e}")
            import traceback
            traceback.print_exc()
    
    # 测试工具调用
    print("\n" + "-" * 60)
    print("测试 2: 工具调用")
    print("-" * 60)
    
    # 注册天气工具
    weather_tool = WeatherTool()
    agent.register_tool(weather_tool)
    
    print("\n问题: 明天上海天气怎么样")
    print("-" * 40)
    
    tool_call = agent.tool_caller.parse_tool_call("明天上海天气怎么样")
    if tool_call:
        tool_name, parameters = tool_call
        print(f"✓ 识别工具: {tool_name}")
        print(f"  参数: {parameters}")
        
        result = await agent.tool_caller.execute_tool(tool_name, parameters)
        print(f"\n✓ 工具执行结果:")
        print(result.output)
    else:
        print("✗ 未识别到工具调用")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)
    print(f"\n当前使用的模型: {agent.current_model}")
    print("gemma4:e2b 模型特点:")
    print("  - Google 最新 Gemma 4 系列")
    print("  - 27亿参数")
    print("  - 高效推理")
    print("  - 强大的指令遵循能力")
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_new_model())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
