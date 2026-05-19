---
name: run_tests
description: 运行项目测试套件并汇总结果。使用此技能当用户要求运行测试、test、验证代码时。自动检测测试框架（pytest/npm test/go test等）。
permissions:
  - shell
---
# Run Tests
运行项目测试并汇总结果。调用 task_planner 工具，传入 pdca_ref="skill://run_tests/pdca.yaml"。
