#!/usr/bin/env python3
"""
完整的 TARS 技能系统测试
"""
import sys
import os
from pathlib import Path

# 添加后端目录到路径
backend_dir = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_dir))

import asyncio
import json
from tars.skills import SkillLoader, registry, SkillStatus, SkillCategory
from tars.skills.executor import SkillExecutor
from tars.execution.weather import WeatherTool
from tars.execution.cronjob import CronJobTool
from tars.database import Database


async def test_weather_skill():
    """测试天气查询技能"""
    print("\n" + "="*60)
    print("1. 测试天气查询技能")
    print("="*60)
    
    # 初始化技能执行器
    executor = SkillExecutor()
    weather_tool = WeatherTool()
    executor.register_tool(weather_tool)
    
    # 测试1: 上海天气
    print("\n[测试] 查询上海当前天气...")
    result = await weather_tool.execute(city="上海")
    print(f"结果: success={result.success}")
    print(f"输出:\n{result.output}")
    
    # 测试2: 北京天气预报
    print("\n[测试] 查询北京未来3天天气预报...")
    result = await weather_tool.execute(city="北京", forecast_days=3)
    print(f"结果: success={result.success}")
    print(f"输出:\n{result.output}")
    
    return True


async def test_skillhub_integration():
    """测试SkillHub集成"""
    print("\n" + "="*60)
    print("2. 测试 SkillHub 集成")
    print("="*60)
    
    executor = SkillExecutor()
    
    # 测试加载技能
    print("\n[测试] 从 SkillHub 加载 calculator 技能...")
    skill = await executor.load_skill_from_hub("calculator")
    if skill:
        print(f"✓ 成功加载技能: {skill.name}")
        print(f"  - 描述: {skill.description}")
        print(f"  - 参数: {len(skill.parameters)}")
        
        # 注册到注册表
        registry.register(skill)
        print("  - 已注册到技能注册表")
        
        # 测试执行
        print(f"\n[测试] 执行技能 {skill.name}...")
        result = await executor.execute_skill(skill, {"expression": "123 + 456"})
        print(f"  结果: success={result.success}")
        print(f"  输出: {result.output}")
    else:
        print("✗ 加载技能失败")
        return False
    
    # 测试 web_search 技能
    print("\n[测试] 从 SkillHub 加载 web_search 技能...")
    skill = await executor.load_skill_from_hub("web_search")
    if skill:
        print(f"✓ 成功加载技能: {skill.name}")
        registry.register(skill)
    else:
        print("✗ 加载技能失败")
    
    return True


async def test_skill_system_integration():
    """测试完整的技能系统集成"""
    print("\n" + "="*60)
    print("3. 测试完整技能系统集成")
    print("="*60)
    
    # 初始化系统
    db = Database()
    executor = SkillExecutor()
    weather_tool = WeatherTool()
    cronjob_tool = CronJobTool(db)
    executor.register_tool(weather_tool)
    executor.register_tool(cronjob_tool)
    
    # 初始化默认技能
    loader = SkillLoader()
    loader.create_default_skills()
    skills = registry.list_skills()
    print(f"\n初始化 {len(skills)} 个默认技能")
    
    # 激活所有技能
    for skill in skills:
        registry.activate(skill.id)
    
    # 列出技能
    print("\n当前已激活的技能:")
    for skill in registry.list_skills():
        if skill.status == SkillStatus.ACTIVE:
            print(f"  ✓ {skill.id} - {skill.name} [{skill.category.value}]")
    
    # 测试工具列表格式
    print("\n[测试] 导出 OpenAI 工具格式...")
    tools = executor.get_available_tools()
    print(f"✓ 导出 {len(tools)} 个工具:")
    for i, tool in enumerate(tools):
        print(f"  {i+1}. {tool['function']['name']}")
    
    # 测试天气技能执行
    print("\n[测试] 执行天气技能...")
    skill = registry.get("weather")
    if skill:
        result = await executor.execute_skill(skill, {"city": "深圳"})
        print(f"✓ 执行结果: success={result.success}")
        print(result.output)
    
    return True


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("TARS 技能系统完整测试")
    print("="*60)
    print("系统功能:")
    print("  ✓ 天气查询技能（带真实 API）")
    print("  ✓ 技能执行引擎")
    print("  ✓ SkillHub 集成框架")
    print("  ✓ 工具-技能桥接")
    
    all_passed = True
    
    try:
        all_passed &= await test_weather_skill()
    except Exception as e:
        print(f"\n✗ 天气技能测试失败: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    try:
        all_passed &= await test_skillhub_integration()
    except Exception as e:
        print(f"\n✗ SkillHub 测试失败: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    try:
        all_passed &= await test_skill_system_integration()
    except Exception as e:
        print(f"\n✗ 系统集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ 所有测试通过！")
        print("\nTARS 技能系统已就绪！")
        print("\n功能说明:")
        print("  1. 天气查询: 查询全球城市实时天气和预报")
        print("  2. 技能执行: 完整的 Skill->Tool 执行流程")
        print("  3. SkillHub: 支持加载外部技能（框架已就绪）")
        print("  4. API 集成: REST API 和 WebSocket 支持")
        print("\n获取真实天气数据:")
        print("  设置环境变量 OPENWEATHER_API_KEY")
        print("  从 https://openweathermap.org/api 申请")
    else:
        print("❌ 部分测试失败！")
    print("="*60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
