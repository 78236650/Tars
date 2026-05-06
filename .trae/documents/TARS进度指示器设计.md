# TARS 进度指示器设计方案

## 问题
用户发送消息后，不知道 TARS 是在思考还是正在输出回答。

## 设计方案

### 方案 1：打字机光标 + 状态文字（推荐）
```vue
<div class="flex items-center gap-2 text-slate-400">
  <span class="text-sm">TARS</span>
  <div class="flex gap-1">
    <span class="w-1.5 h-4 bg-blue-500 animate-pulse"></span>
    <span class="w-1.5 h-4 bg-blue-500 animate-pulse" style="animation-delay: 0.2s"></span>
    <span class="w-1.5 h-4 bg-blue-500 animate-pulse" style="animation-delay: 0.4s"></span>
  </div>
  <span class="text-xs opacity-75">思考中...</span>
</div>
```

**特点**：
- 简洁直观
- 动态效果吸引注意力
- 显示当前状态（思考/输入）

---

### 方案 2：旋转加载图标 + 状态
```vue
<div class="flex items-center gap-2">
  <svg class="w-5 h-5 text-blue-500 animate-spin" fill="none" viewBox="0 0 24 24">
    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
  </svg>
  <span class="text-sm text-slate-400">TARS 正在思考...</span>
</div>
```

**特点**：
- 明确的加载状态
- 传统但有效
- 可自定义图标

---

### 方案 3：TARS Logo 脉冲动画
```vue
<div class="flex items-center gap-3">
  <div class="relative">
    <div class="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center animate-pulse">
      <span class="text-white font-bold text-lg">T</span>
    </div>
    <div class="absolute inset-0 w-10 h-10 bg-blue-500 rounded-full animate-ping opacity-20"></div>
  </div>
  <div class="flex flex-col">
    <span class="text-sm font-medium text-white">TARS</span>
    <span class="text-xs text-slate-400">正在生成回答...</span>
  </div>
</div>
```

**特点**：
- 最具品牌感
- 与 TARS 主题契合
- 视觉突出

---

### 方案 4：多阶段状态指示
```vue
<div class="flex items-center gap-4">
  <!-- 状态指示器 -->
  <div class="flex items-center gap-2">
    <div class="flex gap-1">
      <div class="w-2 h-2 bg-blue-500 rounded-full" :class="thinking ? 'animate-bounce' : ''"></div>
      <div class="w-2 h-2 bg-blue-400 rounded-full" :class="thinking ? 'animate-bounce' : ''" style="animation-delay: 0.1s"></div>
      <div class="w-2 h-2 bg-blue-300 rounded-full" :class="thinking ? 'animate-bounce' : ''" style="animation-delay: 0.2s"></div>
    </div>
  </div>
  
  <!-- 状态文字 -->
  <span class="text-sm" :class="thinking ? 'text-slate-400' : 'text-slate-500'">
    {{ thinking ? 'TARS 思考中...' : 'TARS 输入中...' }}
  </span>
  
  <!-- 时间 -->
  <span class="text-xs text-slate-500">00:{{ elapsed.toString().padStart(2, '0') }}</span>
</div>
```

**特点**：
- 显示思考/输入两阶段
- 带计时功能
- 交互感强

---

## 推荐方案

**方案 1** 是最佳选择：
- ✅ 简洁不占空间
- ✅ 动态效果自然
- ✅ 实现简单
- ✅ 状态文字清晰

**方案 3** 如果你想要更强的品牌感：
- ✅ 最具 TARS 特色
- ✅ 视觉突出
- ⚠️ 会占用更多空间

---

## 实现建议

在 `ChatPanel.vue` 中添加一个进度指示器组件：

```vue
<!-- 添加到 assistant 消息气泡后面 -->
<div v-if="isGenerating" class="flex items-center gap-2 text-slate-400 animate-pulse">
  <div class="flex gap-1">
    <span class="w-1.5 h-4 bg-blue-500 rounded animate-pulse"></span>
    <span class="w-1.5 h-4 bg-blue-500 rounded animate-pulse" style="animation-delay: 0.2s"></span>
    <span class="w-1.5 h-4 bg-blue-500 rounded animate-pulse" style="animation-delay: 0.4s"></span>
  </div>
  <span class="text-xs">TARS 思考中...</span>
</div>
```

需要我实现哪个方案？
