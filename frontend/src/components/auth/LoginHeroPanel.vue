<script setup lang="ts">
import { useI18n } from '@/i18n'

const { t } = useI18n()
</script>

<template>
  <section class="flex h-full flex-col justify-between rounded-[32px] border border-amber-100/10 bg-[#15110d] p-8 text-stone-100">
    <div>
      <img src="/miluo_logo.png" alt="Portmeta logo" class="h-14 w-14 rounded-2xl" />
      <p class="mt-6 text-sm uppercase tracking-[0.24em] text-amber-300">Portmeta</p>
      <h1 class="mt-3 text-4xl font-semibold tracking-tight">{{ t('login.heroTitle') }}</h1>
      <p class="mt-4 max-w-xl text-sm leading-7 text-stone-400">
        {{ t('login.heroDescription') }}
      </p>
    </div>
    <div class="grid gap-3 md:grid-cols-2">
      <div class="rounded-2xl border border-amber-100/10 bg-white/[0.03] p-4">
        <p class="text-xs uppercase tracking-[0.2em] text-amber-200">{{ t('login.adminTitle') }}</p>
        <p class="mt-2 text-sm text-stone-300">{{ t('login.adminDescription') }}</p>
      </div>
      <div class="rounded-2xl border border-amber-100/10 bg-white/[0.03] p-4">
        <p class="text-xs uppercase tracking-[0.2em] text-amber-200">{{ t('login.memberTitle') }}</p>
        <p class="mt-2 text-sm text-stone-300">{{ t('login.memberDescription') }}</p>
      </div>
    </div>
  </section>
</template>
