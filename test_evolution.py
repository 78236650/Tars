#!/usr/bin/env python3
"""
测试 TARS 自进化功能
"""
import sys
import os
from pathlib import Path

# 添加后端目录到路径
backend_dir = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_dir))

from tars.evolution import EvolutionManager
from tars.evolution.evaluator import ResponseEvaluator
from tars.evolution.optimizer import PersonalityOptimizer
from tars.evolution.prompt_tuner import PromptTuner


def test_evaluator():
    """测试评估器"""
    print("\n=== 测试 ResponseEvaluator ===")
    evaluator = ResponseEvaluator()
    
    # 测试基本评估
    query = "帮我写一个 Python 函数"
    response = "好的，我来帮你写一个 Python 函数。\n\ndef hello(name):\n    print(f'Hello, {name}!')"
    
    evaluation = evaluator.evaluate(query, response, explicit_feedback="很好！非常有帮助！")
    
    print(f"Overall Score: {evaluation.overall_score:.2f}")
    print(f"Relevance: {evaluation.relevance:.2f}")
    print(f"Completeness: {evaluation.completeness:.2f}")
    print(f"Accuracy: {evaluation.accuracy:.2f}")
    print(f"Style Match: {evaluation.style_match:.2f}")
    
    return True


def test_optimizer():
    """测试优化器"""
    print("\n=== 测试 PersonalityOptimizer ===")
    optimizer = PersonalityOptimizer()
    
    current_params = {
        'honesty': 0.9,
        'humor': 0.7,
        'initiative': 0.8,
        'empathy': 0.7,
        'formality': 0.5,
        'creativity': 0.6,
        'conciseness': 0.5,
        'technical_depth': 0.6,
        'curiosity': 0.7,
        'skepticism': 0.3
    }
    
    print(f"初始参数: {current_params}")
    print("注意：需要更多历史对话数据才能进行有意义的优化")
    
    return True


def test_prompt_tuner():
    """测试提示词调优器"""
    print("\n=== 测试 PromptTuner ===")
    tuner = PromptTuner()
    
    print("当前 Master Prompt:")
    print(tuner.get_current_prompt('master'))
    
    print("\n当前 Code Prompt:")
    print(tuner.get_current_prompt('code'))
    
    return True


def test_evolution_manager():
    """测试完整的自进化管理器"""
    print("\n=== 测试 EvolutionManager ===")
    manager = EvolutionManager()
    
    print(f"Enabled: {manager.enabled}")
    print(f"Auto Optimize: {manager.auto_optimize}")
    
    # 测试记录对话
    print("\n记录测试对话...")
    for i in range(10):
        manager.record_conversation(
            conversation_id=f"test_{i}",
            query=f"测试问题 {i}",
            response=f"测试回答 {i}",
            explicit_feedback="好的" if i % 2 == 0 else "还行"
        )
    
    # 获取统计
    stats = manager.get_stats()
    print(f"对话记录数: {stats.get('conversation_count', 0)}")
    print(f"统计: {stats}")
    
    # 测试优化
    print("\n触发优化...")
    results = manager.optimize()
    print(f"优化结果: {results}")
    
    return True


def main():
    """运行所有测试"""
    print("=" * 60)
    print("TARS 自进化功能测试")
    print("=" * 60)
    
    all_passed = True
    
    try:
        all_passed &= test_evaluator()
    except Exception as e:
        print(f"❌ Evaluator 测试失败: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    try:
        all_passed &= test_optimizer()
    except Exception as e:
        print(f"❌ Optimizer 测试失败: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    try:
        all_passed &= test_prompt_tuner()
    except Exception as e:
        print(f"❌ Prompt Tuner 测试失败: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    try:
        all_passed &= test_evolution_manager()
    except Exception as e:
        print(f"❌ Evolution Manager 测试失败: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ 所有测试通过！")
    else:
        print("❌ 部分测试失败！")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
