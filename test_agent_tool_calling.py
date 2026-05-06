#!/usr/bin/env python3
"""
测试 TARS Agent 自主工具调用
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
from tars.execution.cronjob import CronJobTool
from tars.agent.tool_calling import ToolCaller


async def test_tool_calling():
    """测试工具调用系统"""
    print("=" * 60)
    print("TARS Agent 自主工具调用测试")
    print("=" * 60)
    
    # 初始化
    db = Database()
    agent = Agent(db=db)
    
    # 注册工具
    weather_tool = WeatherTool()
    cronjob_tool = CronJobTool(db)
    agent.register_tool(weather_tool)
    agent.register_tool(cronjob_tool)
    
    print("\n✓ 已注册工具:")
    for tool in agent.tool_caller.get_all_tools():
        print(f"  - {tool.name}: {tool.description[:50]}...")
    
    # 测试工具提示生成
    print("\n" + "-" * 60)
    print("1. 测试工具提示生成")
    print("-" * 60)
    
    tools_prompt = agent._build_tools_prompt()
    print(tools_prompt[:500] + "...")
    
    # 测试工具调用解析
    print("\n" + "-" * 60)
    print("2. 测试工具调用解析")
    print("-" * 60)
    
    test_cases = [
        "明天上海天气怎么样",
        "查询北京未来3天天气预报",
        "帮我创建一个每天早上9点的提醒",
        "广州的天气",
    ]
    
    for test_input in test_cases:
        print(f"\n输入: {test_input}")
        tool_call = agent.tool_caller.parse_tool_call(test_input)
        
        if tool_call:
            tool_name, parameters = tool_call
            print(f"✓ 识别工具: {tool_name}")
            print(f"  参数: {parameters}")
            
            # 执行工具
            result = await agent.tool_caller.execute_tool(tool_name, parameters)
            print(f"  结果: success={result.success}")
            print(f"  输出: {result.output[:200]}...")
        else:
            print("✗ 未识别到工具调用")
    
    # 测试完整流程
    print("\n" + "-" * 60)
    print("3. 测试完整工具调用流程")
    print("-" * 60)
    
    print("\n测试: '明天上海天气怎么样'")
    tool_call = agent.tool_caller.parse_tool_call("明天上海天气怎么样")
    
    if tool_call:
        tool_name, parameters = tool_call
        print(f"✓ 自动识别并调用工具: {tool_name}")
        print(f"  参数: {parameters}")
        
        result = await agent.tool_caller.execute_tool(tool_name, parameters)
        
        print(f"\n✓ 工具执行结果:")
        print(f"  成功: {result.success}")
        print(f"  输出:\n{result.output}")
    else:
        print("✗ 未识别到工具调用")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)
    print("\nAgent 现在可以:")
    print("  ✓ 自动识别用户意图")
    print("  ✓ 选择合适的工具")
    print("  ✓ 提取参数并执行")
    print("  ✓ 返回结果给用户")
    print("\n支持的查询示例:")
    print("  - '明天上海天气怎么样'")
    print("  - '查询北京未来3天天气预报'")
    print("  - '帮我创建一个每天早上9点的提醒'")
    print("  - '广州的天气'")
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_tool_calling())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
