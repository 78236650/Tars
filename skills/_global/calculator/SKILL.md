---
name: calculator
description: 精确数学计算工具。使用此技能当用户要求计算、数学运算、求值等。支持四则运算、三角函数、对数、幂运算、sqrt/log/sin/cos/exp/pi/e 等。此技能已注册为工具 calculator，LLM 需要调用该工具来执行计算。
---

# Calculator

精确数学计算工具。

## 使用方式

调用 `calculator` 工具，传入数学表达式。

**支持的运算**：+-*/（四则运算）、**（幂）、sqrt/log/sin/cos/exp/pi/e

**示例**：
- `calculator("2+3*4")` → 14
- `calculator("sqrt(16) + sin(pi/2)")` → 5.0

## 注意事项
- 表达式中的乘号必须写 `*`（不能省略为 `2(3+4)`）
- 返回数值结果，需自行解读
