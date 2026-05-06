#!/usr/bin/env python3
"""
测试 TARS Skill 系统状态
"""
import sys
import os
from pathlib import Path

# 添加后端目录到路径
backend_dir = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_dir))

from tars.skills import SkillLoader, registry, SkillStatus, SkillCategory


def test_skill_system():
    """测试技能系统"""
    print("=" * 60)
    print("TARS Skill 系统状态检查")
    print("=" * 60)
    
    # 1. 检查技能注册表
    print("\n=== 技能注册表状态 ===")
    skills = registry.list_skills()
    print(f"已注册技能数量: {len(skills)}")
    
    if skills:
        print("\n已注册的技能:")
        for skill in skills:
            print(f"  - {skill.id}: {skill.name} (状态: {skill.status.value}, 分类: {skill.category.value})")
    else:
        print("暂无已注册的技能")
    
    # 2. 初始化默认技能
    print("\n=== 初始化默认技能 ===")
    loader = SkillLoader(skills_dir="skills")
    loader.create_default_skills()
    
    # 3. 再次检查注册表
    print("\n=== 初始化后的技能注册表 ===")
    skills = registry.list_skills()
    print(f"已注册技能数量: {len(skills)}")
    
    print("\n已注册的技能:")
    for skill in skills:
        print(f"  - {skill.id}: {skill.name}")
        print(f"    描述: {skill.description}")
        print(f"    状态: {skill.status.value}")
        print(f"    分类: {skill.category.value}")
        print(f"    图标: {skill.icon}")
        print(f"    标签: {', '.join(skill.tags)}")
        print(f"    触发器: {len(skill.triggers)} 个")
        print(f"    参数: {len(skill.parameters)} 个")
        print()
    
    # 4. 测试激活/停用
    print("\n=== 测试激活/停用 ===")
    if skills:
        test_skill = skills[0]
        print(f"测试技能: {test_skill.name}")
        
        # 激活
        registry.activate(test_skill.id)
        print(f"激活后状态: {registry.get(test_skill.id).status.value}")
        
        # 停用
        registry.deactivate(test_skill.id)
        print(f"停用后状态: {registry.get(test_skill.id).status.value}")
    
    # 5. 测试按分类查询
    print("\n=== 按分类查询技能 ===")
    for category in SkillCategory:
        category_skills = registry.list_by_category(category)
        if category_skills:
            print(f"{category.value}: {len(category_skills)} 个")
            for s in category_skills:
                print(f"  - {s.name}")
    
    # 6. 测试技能加载
    print("\n=== 测试技能文件加载 ===")
    skills_dir = Path("skills")
    if skills_dir.exists():
        skill_files = list(skills_dir.glob("*.md"))
        print(f"技能文件数量: {len(skill_files)}")
        for sf in skill_files:
            print(f"  - {sf.name}")
    else:
        print("技能目录不存在")
    
    print("\n" + "=" * 60)
    print("✅ Skill 系统状态检查完成！")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    try:
        test_skill_system()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
