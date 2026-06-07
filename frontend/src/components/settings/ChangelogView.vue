<script setup lang="ts">
import { useI18n } from '@/i18n'

const { t } = useI18n()

interface VersionSection {
  version: string
  subtitle: string
  releaseDateKey: string
  features: string[]
  improvements: string[]
}

const versions: VersionSection[] = [
  {
    version: 'v5.0.4',
    subtitle: 'Wiki 知识体系 + 模型升级',
    releaseDateKey: 'settings.changelog.v504ReleaseDate',
    features: [
      'settings.changelog.v504.feature1',
      'settings.changelog.v504.feature2',
      'settings.changelog.v504.feature3',
      'settings.changelog.v504.feature4',
    ],
    improvements: [
      'settings.changelog.v504.improvement1',
      'settings.changelog.v504.improvement2',
      'settings.changelog.v504.improvement3',
      'settings.changelog.v504.improvement4',
      'settings.changelog.v504.improvement5',
      'settings.changelog.v504.improvement6',
    ],
  },
  {
    version: 'v4.3.2',
    subtitle: 'Superpowers Integration',
    releaseDateKey: 'settings.changelog.v432ReleaseDate',
    features: [
      'settings.changelog.v432.feature1',
      'settings.changelog.v432.feature2',
      'settings.changelog.v432.feature3',
      'settings.changelog.v432.feature4',
    ],
    improvements: [
      'settings.changelog.v432.improvement1',
    ],
  },
  {
    version: 'v4.3.1',
    subtitle: 'Platform Patch',
    releaseDateKey: 'settings.changelog.v431ReleaseDate',
    features: [
      'settings.changelog.v431.feature1',
      'settings.changelog.v431.feature2',
      'settings.changelog.v431.feature3',
      'settings.changelog.v431.feature4',
    ],
    improvements: [
      'settings.changelog.v431.improvement1',
    ],
  },
  {
    version: 'v4.3.0',
    subtitle: 'Channels & Execution',
    releaseDateKey: 'settings.changelog.v430ReleaseDate',
    features: [
      'settings.changelog.v430.feature1',
      'settings.changelog.v430.feature2',
      'settings.changelog.v430.feature3',
      'settings.changelog.v430.feature4',
    ],
    improvements: [
      'settings.changelog.v430.improvement1',
    ],
  },
  {
    version: 'v4.2.0',
    subtitle: 'Data Copilot & Evolution',
    releaseDateKey: 'settings.changelog.v420ReleaseDate',
    features: [
      'settings.changelog.v420.feature1',
      'settings.changelog.v420.feature2',
      'settings.changelog.v420.feature3',
    ],
    improvements: [
      'settings.changelog.v420.improvement1',
    ],
  },
  {
    version: 'v4.1.4',
    subtitle: 'Memory Entity Tree',
    releaseDateKey: 'settings.changelog.v414ReleaseDate',
    features: [
      'settings.changelog.v414.feature1',
      'settings.changelog.v414.feature2',
      'settings.changelog.v414.feature3',
      'settings.changelog.v414.feature4',
    ],
    improvements: [
      'settings.changelog.v414.improvement1',
      'settings.changelog.v414.improvement2',
    ],
  },
  {
    version: 'v4.1.3',
    subtitle: 'Chat Polish & Remember',
    releaseDateKey: 'settings.changelog.v413ReleaseDate',
    features: [
      'settings.changelog.v413.feature1',
      'settings.changelog.v413.feature2',
      'settings.changelog.v413.feature3',
    ],
    improvements: ['settings.changelog.v413.improvement1'],
  },
  {
    version: 'v4.1.2',
    subtitle: 'Skill Ops & Platform UI',
    releaseDateKey: 'settings.changelog.v412ReleaseDate',
    features: [
      'settings.changelog.v412.feature1',
      'settings.changelog.v412.feature2',
    ],
    improvements: ['settings.changelog.v412.improvement1'],
  },
  {
    version: 'v4.1.1',
    subtitle: 'Experience Layer',
    releaseDateKey: 'settings.changelog.v411ReleaseDate',
    features: [
      'settings.changelog.v411.feature1',
      'settings.changelog.v411.feature2',
      'settings.changelog.v411.feature3',
      'settings.changelog.v411.feature4',
    ],
    improvements: [
      'settings.changelog.v411.improvement1',
      'settings.changelog.v411.improvement2',
    ],
  },
  {
    version: 'v4.1.0',
    subtitle: 'Skill Ecosystem',
    releaseDateKey: 'settings.changelog.v410ReleaseDate',
    features: [
      'settings.changelog.v410.feature1',
      'settings.changelog.v410.feature2',
      'settings.changelog.v410.feature3',
      'settings.changelog.v410.feature4',
      'settings.changelog.v410.feature5',
      'settings.changelog.v410.feature6',
    ],
    improvements: [
      'settings.changelog.v410.improvement1',
      'settings.changelog.v410.improvement2',
      'settings.changelog.v410.improvement3',
    ],
  },
  {
    version: 'v4.0.0',
    subtitle: 'Hardened Base',
    releaseDateKey: 'settings.changelog.releaseDate',
    features: [
      'settings.changelog.feature1',
      'settings.changelog.feature2',
      'settings.changelog.feature3',
      'settings.changelog.feature4',
      'settings.changelog.feature5',
      'settings.changelog.feature6',
    ],
    improvements: [
      'settings.changelog.improvement1',
      'settings.changelog.improvement2',
      'settings.changelog.improvement3',
      'settings.changelog.improvement4',
      'settings.changelog.improvement5',
      'settings.changelog.improvement6',
    ],
  },
]
</script>

<template>
  <div class="flex flex-col gap-8 max-w-3xl">
    <section v-for="section in versions" :key="section.version" class="space-y-4">
      <div>
        <h2 class="text-lg font-semibold text-stone-100">
          TARS {{ section.version }}
          <span class="ml-2 text-sm font-normal text-stone-500">{{ section.subtitle }}</span>
        </h2>
        <p class="mt-1 text-xs text-stone-500">{{ t(section.releaseDateKey) }}</p>
      </div>

      <div>
        <h3 class="mb-3 flex items-center gap-2 text-sm font-semibold text-stone-200">
          <span class="text-emerald-400">✦</span>
          {{ t('settings.changelog.newFeatures') }}
        </h3>
        <div class="rounded-2xl border border-amber-100/10 bg-white/[0.03] divide-y divide-amber-100/5">
          <div
            v-for="(key, idx) in section.features"
            :key="`${section.version}-f-${idx}`"
            class="px-5 py-3.5 flex items-start gap-3"
          >
            <span class="mt-0.5 w-5 h-5 rounded-full bg-emerald-500/15 text-emerald-400 flex items-center justify-center text-[10px] font-bold flex-shrink-0">
              {{ idx + 1 }}
            </span>
            <span class="text-sm text-stone-300 leading-relaxed">{{ t(key) }}</span>
          </div>
        </div>
      </div>

      <div>
        <h3 class="mb-3 flex items-center gap-2 text-sm font-semibold text-stone-200">
          <span class="text-amber-400">↻</span>
          {{ t('settings.changelog.improvements') }}
        </h3>
        <div class="rounded-2xl border border-amber-100/10 bg-white/[0.03] divide-y divide-amber-100/5">
          <div
            v-for="(key, idx) in section.improvements"
            :key="`${section.version}-i-${idx}`"
            class="px-5 py-3.5 flex items-start gap-3"
          >
            <span class="mt-0.5 w-5 h-5 rounded-full bg-amber-500/15 text-amber-400 flex items-center justify-center text-[10px] font-bold flex-shrink-0">
              {{ idx + 1 }}
            </span>
            <span class="text-sm text-stone-300 leading-relaxed">{{ t(key) }}</span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
