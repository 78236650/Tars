<script setup lang="ts">
import { computed } from 'vue'
import { useToast } from '@/composables/useToast'

const toast = useToast()
const toastItems = computed(() => toast.toasts.value)
</script>

<template>
  <Teleport to="body">
    <div class="toast-host" aria-live="polite" aria-atomic="true">
      <TransitionGroup name="toast">
        <div
          v-for="item in toastItems"
          :key="item.id"
          class="toast-item"
          :class="{
            'toast-item--success': item.type === 'success',
            'toast-item--error': item.type === 'error',
            'toast-item--info': item.type === 'info',
          }"
        >
          <span v-if="item.type === 'success'" class="toast-icon">✓</span>
          <span v-else-if="item.type === 'error'" class="toast-icon">✕</span>
          <span v-else class="toast-icon">ℹ</span>
          <span class="toast-message">{{ item.message }}</span>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-host {
  position: fixed;
  top: 1rem;
  right: 1rem;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  pointer-events: none;
}

.toast-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-width: 16rem;
  max-width: 24rem;
  padding: 0.75rem 1rem;
  border-radius: 0.75rem;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.35);
  color: #fff;
  pointer-events: auto;
}

.toast-item--success {
  background: #16a34a;
}

.toast-item--error {
  background: #dc2626;
}

.toast-item--info {
  background: #2563eb;
}

.toast-icon {
  font-size: 1.125rem;
  line-height: 1;
}

.toast-message {
  font-size: 0.875rem;
  line-height: 1.4;
}

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
