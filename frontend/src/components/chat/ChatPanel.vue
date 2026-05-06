<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useI18n } from '@/i18n'
import PlanCard from './PlanCard.vue'
import type { ToolCallEvent } from '@/types'

defineProps<{
  messages: { id: string; role: string; content: string; timestamp: string; toolCalls?: ToolCallEvent[]; plan?: any; planSteps?: any[] }[]
  isGenerating?: boolean
}>()

const { t } = useI18n()

const panelRef = ref<HTMLElement | null>(null)

const formatTime = (timestamp: string) => {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
}

const scrollToBottom = async () => {
  await nextTick()
  if (panelRef.value) {
    panelRef.value.scrollTop = panelRef.value.scrollHeight
  }
}

watch(() => arguments[0].messages.length, scrollToBottom)
</script>

<template>
  <div ref="panelRef" class="flex-1 overflow-y-auto px-6 py-4">
    <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full text-slate-500">
      <div class="w-24 h-24 bg-slate-800 rounded-full flex items-center justify-center mb-4">
        <svg class="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
        </svg>
      </div>
      <p class="text-lg font-medium">{{ t('chat.welcome') }}</p>
      <p class="text-sm mt-2">{{ t('chat.welcomeHint') }}</p>
    </div>

    <div v-else class="space-y-6">
      <div
        v-for="(message, index) in messages"
        :key="index"
      >
        <!-- 计划执行卡片 -->
        <PlanCard
          v-if="(message as any).planSteps"
          :plan="(message as any).plan"
          :steps="(message as any).planSteps"
        />

        <!-- 工具调用卡片 -->
        <div v-if="message.toolCalls && message.toolCalls.length > 0" class="mb-3 space-y-2">
          <div
            v-for="(tc, tcIdx) in message.toolCalls"
            :key="tcIdx"
            class="bg-slate-800/50 border border-slate-700 rounded-lg p-3"
          >
            <div class="flex items-center gap-2 text-sm">
              <span class="text-blue-400 font-medium">🔧 {{ tc.tool }}</span>
              <span class="text-slate-500">{{ JSON.stringify(tc.parameters) }}</span>
            </div>
            <div v-if="tc.output" class="mt-2 text-sm text-slate-300 bg-slate-900 rounded p-2 max-h-32 overflow-auto">
              {{ tc.output }}
            </div>
            <div v-if="tc.error" class="mt-2 text-sm text-red-400">
              {{ tc.error }}
            </div>
          </div>
        </div>

        <!-- 消息气泡 -->
        <div
          class="flex gap-4"
          :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
        >
          <div
            class="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center"
            :class="message.role === 'user' ? 'bg-blue-600' : 'bg-slate-700'"
          >
            <svg v-if="message.role === 'user'" class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
            </svg>
            <svg v-else class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
            </svg>
          </div>

          <div
            class="max-w-[70%] px-4 py-3 rounded-xl"
            :class="{
              'bg-blue-600 text-white rounded-br-sm': message.role === 'user',
              'bg-slate-800 text-slate-200 rounded-bl-sm': message.role === 'assistant',
              'bg-red-900/50 text-red-300 rounded-bl-sm': message.role === 'system'
            }"
          >
            <p class="whitespace-pre-wrap">{{ message.content }}</p>
            <p class="text-xs mt-1 opacity-60">{{ formatTime(message.timestamp) }}</p>
          </div>
        </div>

        <!-- 生成中指示器 -->
        <div
          v-if="message.role === 'user' && isGenerating && index === messages.length - 1"
          class="flex items-center gap-2 text-slate-400 animate-pulse ml-14"
        >
          <div class="flex gap-1">
            <span class="w-1.5 h-4 bg-slate-500 rounded animate-pulse"></span>
            <span class="w-1.5 h-4 bg-slate-500 rounded animate-pulse" style="animation-delay: 0.2s"></span>
            <span class="w-1.5 h-4 bg-slate-500 rounded animate-pulse" style="animation-delay: 0.4s"></span>
          </div>
          <span class="text-xs">{{ t('chat.thinking') }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
