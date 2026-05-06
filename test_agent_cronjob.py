#!/usr/bin/env python3
"""
测试 TARS Agent 调用 CronJob 工具
"""
import sys
import os
import json
import tempfile
from pathlib import Path

# 添加后端目录到路径
backend_dir = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_dir))

from tars.database import Database
from tars.execution.cronjob import CronJobTool
from tars.execution.registry import registry as tool_registry


async def test_tool_registry():
    """测试工具注册表"""
    print("\n=== 测试工具注册表 ===")
    
    # 使用临时数据库
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        temp_db_path = f.name
    
    try:
        db = Database(db_path=temp_db_path)
        cronjob_tool = CronJobTool(db)
        
        # 注册工具到注册表
        tool_registry.register(cronjob_tool)
        
        # 检查工具是否已注册
        tools = tool_registry.list_tools()
        print(f"已注册的工具: {tools}")
        
        # 获取 cronjob 工具
        registered_tool = tool_registry.get("cronjob")
        if registered_tool:
            print("✅ cronjob 工具已成功注册")
            print(f"工具名称: {registered_tool.name}")
            print(f"工具描述: {registered_tool.description}")
            print(f"工具参数: {registered_tool.parameters_schema}")
        else:
            print("❌ cronjob 工具未注册")
            return False
    finally:
        os.unlink(temp_db_path)
    
    return True


async def test_tool_execution():
    """测试工具执行"""
    print("\n=== 测试工具执行 ===")
    
    # 使用临时数据库
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        temp_db_path = f.name
    
    try:
        db = Database(db_path=temp_db_path)
        cronjob_tool = CronJobTool(db)
        
        # 测试创建任务
        result = await cronjob_tool.execute(
            action="create",
            name="测试定时任务",
            cron="0 9 * * *",
            task_type="reminder",
            task_config={"message": "测试提醒"},
            description="测试任务描述"
        )
        
        print(f"创建任务结果: success={result.success}, output={result.output}")
        if result.success and result.metadata:
            print(f"任务ID: {result.metadata['job_id']}")
            job_id = result.metadata['job_id']
            
            # 测试列出任务
            list_result = await cronjob_tool.execute(action="list")
            print(f"\n列出任务结果: success={list_result.success}")
            if list_result.metadata:
                print(f"任务数量: {list_result.metadata['total']}")
            
            # 测试获取任务
            get_result = await cronjob_tool.execute(action="get", id=job_id)
            print(f"\n获取任务结果: success={get_result.success}")
            if get_result.metadata:
                print(f"任务名称: {get_result.metadata['name']}")
                print(f"Cron表达式: {get_result.metadata['cron']}")
            
            # 测试删除任务
            delete_result = await cronjob_tool.execute(action="delete", id=job_id)
            print(f"\n删除任务结果: success={delete_result.success}, output={delete_result.output}")
    
    finally:
        os.unlink(temp_db_path)
    
    return True


async def test_openai_format():
    """测试转换为 OpenAI 工具格式"""
    print("\n=== 测试 OpenAI 工具格式 ===")
    
    cronjob_tool = tool_registry.get("cronjob")
    if cronjob_tool:
        openai_tool = cronjob_tool.to_openai_tool()
        print("OpenAI 工具格式:")
        print(json.dumps(openai_tool, indent=2, ensure_ascii=False))
    else:
        print("❌ cronjob 工具未注册")
        return False
    
    return True


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("TARS Agent 调用 CronJob 工具测试")
    print("=" * 60)
    
    all_passed = True
    
    try:
        all_passed &= await test_tool_registry()
    except Exception as e:
        print(f"❌ 工具注册表测试失败: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    try:
        all_passed &= await test_tool_execution()
    except Exception as e:
        print(f"❌ 工具执行测试失败: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    try:
        all_passed &= await test_openai_format()
    except Exception as e:
        print(f"❌ OpenAI 格式测试失败: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ 所有测试通过！")
        print("\n🎉 Agent 现在可以调用 CronJob 工具了！")
        print("当用户说 '帮我创建一个每天早上9点的提醒' 时，")
        print("Agent 会自动调用 cronjob 工具来创建定时任务。")
    else:
        print("❌ 部分测试失败！")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    import asyncio
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
