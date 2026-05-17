<script setup lang="ts">
import { useI18n } from '@/i18n'

const { t } = useI18n()

const newFeatures = [
  'settings.changelog.feature1',
  'settings.changelog.feature2',
  'settings.changelog.feature3',
  'settings.changelog.feature4',
  'settings.changelog.feature5',
  'settings.changelog.feature6',
]

const improvements = [
  'settings.changelog.improvement1',
  'settings.changelog.improvement2',
  'settings.changelog.improvement3',
  'settings.changelog.improvement4',
  'settings.changelog.improvement5',
  'settings.changelog.improvement6',
]
</script>

<template>
  <div class="flex flex-col gap-6 max-w-3xl">
    <!-- 新增功能 -->
    <section>
      <h2 class="flex items-center gap-2 text-lg font-semibold text-stone-100 mb-3">
        <span class="text-emerald-400 text-base">✦</span>
        {{ t('settings.changelog.newFeatures') }}
      </h2>
      <div class="rounded-2xl border border-amber-100/10 bg-white/[0.03] divide-y divide-amber-100/5">
        <div
          v-for="(key, idx) in newFeatures"
          :key="idx"
          class="px-5 py-3.5 flex items-start gap-3"
        >
          <span class="mt-0.5 w-5 h-5 rounded-full bg-emerald-500/15 text-emerald-400 flex items-center justify-center text-[10px] font-bold flex-shrink-0">
            {{ idx + 1 }}
          </span>
          <span class="text-sm text-stone-300 leading-relaxed">{{ t(key) }}</span>
        </div>
      </div>
    </section>

    <!-- 改进变更 -->
    <section>
      <h2 class="flex items-center gap-2 text-lg font-semibold text-stone-100 mb-3">
        <span class="text-amber-400 text-base">↻</span>
        {{ t('settings.changelog.improvements') }}
      </h2>
      <div class="rounded-2xl border border-amber-100/10 bg-white/[0.03] divide-y divide-amber-100/5">
        <div
          v-for="(key, idx) in improvements"
          :key="idx"
          class="px-5 py-3.5 flex items-start gap-3"
        >
          <span class="mt-0.5 w-5 h-5 rounded-full bg-amber-500/15 text-amber-400 flex items-center justify-center text-[10px] font-bold flex-shrink-0">
            {{ idx + 1 }}
          </span>
          <span class="text-sm text-stone-300 leading-relaxed">{{ t(key) }}</span>
        </div>
      </div>
    </section>

    <!-- Footer -->
    <div class="mt-2 pt-4 border-t border-amber-100/10">
      <p class="text-xs text-stone-500">
        TARS v4.0.0 — Hardened Base · {{ t('settings.changelog.releaseDate') }}
      </p>
    </div>
  </div>
</template>
