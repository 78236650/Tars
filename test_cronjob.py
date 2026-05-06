#!/usr/bin/env python3
"""
测试 TARS 定时任务功能
"""
import sys
import os
from pathlib import Path

# 添加后端目录到路径
backend_dir = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_dir))

from tars.database import Database
from tars.scheduler import get_scheduler, init_scheduler
import asyncio
from datetime import datetime


async def test_database():
    """测试数据库操作"""
    print("\n=== 测试数据库操作 ===")
    
    db = Database()
    
    # 创建定时任务
    job1 = db.create_cronjob(
        user_id="test_user",
        name="每日提醒",
        cron_expression="* * * * *",
        task_type="reminder",
        task_config='{"message": "记得喝水！"}',
        description="每小时提醒喝水"
    )
    print(f"创建任务: {job1.id} - {job1.name}")
    
    # 获取用户任务
    jobs = db.get_user_cronjobs("test_user")
    print(f"用户任务数: {len(jobs)}")
    
    # 获取单个任务
    job = db.get_cronjob(job1.id)
    print(f"获取任务: {job.name}")
    
    # 更新任务
    db.update_cronjob(job1.id, description="每小时喝水提醒")
    print("任务已更新")
    
    # 测试完成
    print("数据库操作测试完成！")


async def test_scheduler():
    """测试调度器"""
    print("\n=== 测试调度器 ===")
    
    # 初始化调度器
    await init_scheduler()
    scheduler = get_scheduler()
    
    counter = 0
    
    async def test_task():
        nonlocal counter
        counter += 1
        print(f"测试任务执行: {counter} - {datetime.now()}")
    
    # 添加任务
    task_id = scheduler.add_task(
        name="测试任务",
        cron_expression="* * * * *",
        task=test_task
    )
    print(f"添加任务: {task_id}")
    
    # 列出任务
    tasks = scheduler.get_tasks()
    print(f"当前任务数: {len(tasks)}")
    for t in tasks:
        print(f"  - {t.name} (ID: {t.task_id})")
    
    # 运行一会儿
    print("\n调度器运行中... (10 秒后停止)")
    await asyncio.sleep(10)
    
    # 测试完成
    print("\n调度器测试完成！")


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("TARS 定时任务功能测试")
    print("=" * 60)
    
    try:
        await test_database()
        await test_scheduler()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
