<script setup lang="ts">
import { watch, onUnmounted } from 'vue'

const props = withDefaults(defineProps<{
  open: boolean
  title: string
  description?: string
  side?: 'left' | 'right'
}>(), {
  description: '',
  side: 'right',
})

const emit = defineEmits<{
  close: []
}>()

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}

watch(() => props.open, (val) => {
  if (val) document.addEventListener('keydown', handleKeydown)
  else document.removeEventListener('keydown', handleKeydown)
}, { immediate: true })

onUnmounted(() => document.removeEventListener('keydown', handleKeydown))
</script>

<template>
  <div v-if="props.open" class="fixed inset-0 z-50">
    <button
      type="button"
      class="absolute inset-0 bg-black/60 backdrop-blur-sm"
      aria-label="关闭抽屉"
      @click="emit('close')"
    />

    <aside
      role="dialog"
      aria-modal="true"
      :aria-label="props.title"
      :class="[
        'absolute inset-y-0 flex h-full w-full max-w-xl flex-col overflow-hidden bg-surface-1 shadow-[0_30px_100px_rgba(8,7,5,0.65)]',
        props.side === 'right'
          ? 'right-0 border-l border-amber-100/10'
          : 'left-0 border-r border-amber-100/10',
      ]"
    >
      <header class="flex items-start justify-between gap-4 border-b border-amber-100/10 px-6 py-5">
        <div class="min-w-0">
          <h2 class="text-xl font-semibold text-stone-100">{{ props.title }}</h2>
          <p v-if="props.description" class="mt-1 text-sm text-stone-400">
            {{ props.description }}
          </p>
        </div>

        <button
          data-test="surface-close"
          type="button"
          class="rounded-2xl border border-amber-100/10 bg-white/[0.04] px-3 py-2 text-sm text-stone-200 transition-colors hover:bg-white/[0.08]"
          @click="emit('close')"
        >
          关闭
        </button>
      </header>

      <div class="min-h-0 flex-1 overflow-y-auto px-6 py-5">
        <slot />
      </div>

      <footer v-if="$slots.footer" class="border-t border-amber-100/10 px-6 py-4">
        <slot name="footer" />
      </footer>
    </aside>
  </div>
</template>
