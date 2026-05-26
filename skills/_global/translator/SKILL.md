---
name: translator
description: 翻译助手，支持中英互译及多语种翻译。使用此技能当用户要求"翻译""translate""英译""中译"等。
triggers:
  - "翻译"
  - "translate"
  - "英译"
  - "中译"
  - "译成"
  - "intent:writing.translate"
priority: 60
---

# Translator

翻译助手。

## 原则
1. 保持原文语义和语气
2. 专业术语准确
3. 自然流畅，符合目标语言习惯
4. 不确定时标注

## 输出格式
```
原文：[原文]
译文：[译文]

注：[必要时加注释]
