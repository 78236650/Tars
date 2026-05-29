<script setup lang="ts">
import { ref, onMounted } from 'vue'
const stats = ref<Record<string, unknown>>({})
const recent = ref(0)
onMounted(async () => {
  const r = await fetch('/api/evolution/metrics?tenant_id=default')
  const d = await r.json()
  stats.value = d.stats
  recent.value = d.recent_feedback
})
</script>

<template>
  <div class="p-4">
    <h2 class="text-lg font-bold">自进化指标</h2>
    <p>近 7 天反馈条数: {{ recent }}</p>
    <pre>{{ JSON.stringify(stats, null, 2) }}</pre>
  </div>
</template>
