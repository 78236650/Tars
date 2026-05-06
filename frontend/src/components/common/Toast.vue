<script setup lang="ts">
import { ref, watch } from 'vue'

interface ToastMessage {
  id: number
  message: string
  type: 'success' | 'error' | 'info'
}

const toasts = ref<ToastMessage[]>([])
let nextId = 0

const show = (message: string, type: 'success' | 'error' | 'info' = 'info', duration = 3000) => {
  const id = nextId++
  toasts.value.push({ id, message, type })

  setTimeout(() => {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }, duration)
}

const success = (message: string, duration?: number) => show(message, 'success', duration)
const error = (message: string, duration?: number) => show(message, 'error', duration)
const info = (message: string, duration?: number) => show(message, 'info', duration)

defineExpose({ show, success, error, info })
</script>

<template>
  <Teleport to="body">
    <div class="fixed top-4 right-4 z-50 flex flex-col gap-2">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="px-4 py-3 rounded-lg shadow-lg min-w-64 max-w-96 flex items-center gap-3"
          :class="{
            'bg-green-600 text-white': toast.type === 'success',
            'bg-red-600 text-white': toast.type === 'error',
            'bg-blue-600 text-white': toast.type === 'info'
          }"
        >
          <span v-if="toast.type === 'success'" class="text-lg">✓</span>
          <span v-else-if="toast.type === 'error'" class="text-lg">✕</span>
          <span v-else class="text-lg">ℹ</span>
          <span class="text-sm">{{ toast.message }}</span>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-enter-active {
  animation: toast-in 0.3s ease-out;
}
.toast-leave-active {
  animation: toast-out 0.3s ease-in;
}

@keyframes toast-in {
  from {
    opacity: 0;
    transform: translateX(100px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes toast-out {
  from {
    opacity: 1;
    transform: translateX(0);
  }
  to {
    opacity: 0;
    transform: translateX(100px);
  }
}
</style>
