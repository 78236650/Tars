<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { memoryApi } from '@/api'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()

const localParams = ref<Record<string, number>>({})
const communicationStyle = ref('')
const behaviorRules = ref<string[]>([])
const coreBlocks = ref<Record<string, string>>({
  persona: '',
  user_profile: '',
  project_context: '',
  working_principles: '',
})
const saving = ref(false)
const saveMessage = ref('')
const coreBlockTitles: Record<string, string> = {
  persona: 'Persona',
  user_profile: 'User Profile',
  project_context: 'Project Context',
  working_principles: 'Working Principles',
}

const presetPersonalities = [
  { name: 'Professional', params: { honesty: 0.9, humor: 0.3, initiative: 0.8, empathy: 0.6, formality: 0.8, creativity: 0.5, conciseness: 0.8, technical_depth: 0.9, curiosity: 0.7, skepticism: 0.6 } },
  { name: 'Friendly', params: { honesty: 0.8, humor: 0.7, initiative: 0.6, empathy: 0.9, formality: 0.3, creativity: 0.7, conciseness: 0.5, technical_depth: 0.4, curiosity: 0.8, skepticism: 0.2 } },
  { name: 'Creative', params: { honesty: 0.7, humor: 0.6, initiative: 0.9, empathy: 0.7, formality: 0.4, creativity: 0.9, conciseness: 0.4, technical_depth: 0.5, curiosity: 0.9, skepticism: 0.3 } },
  { name: 'Scholar', params: { honesty: 0.9, humor: 0.2, initiative: 0.7, empathy: 0.5, formality: 0.9, creativity: 0.6, conciseness: 0.9, technical_depth: 0.8, curiosity: 0.8, skepticism: 0.7 } },
]

const params = computed(() => localParams.value)

const syncFromStore = () => {
  if (!settingsStore.personality) return
  localParams.value = { ...settingsStore.personality.parameters }
  communicationStyle.value = settingsStore.personality.communication_style
  behaviorRules.value = [...settingsStore.personality.behavior_rules]
}

watch(() => settingsStore.personality, syncFromStore, { deep: true })

const loadData = async () => {
  await settingsStore.loadPersonality()
  syncFromStore()
  const blocks = await memoryApi.getCoreBlocks()
  coreBlocks.value = {
    persona: blocks.blocks.persona || '',
    user_profile: blocks.blocks.user_profile || '',
    project_context: blocks.blocks.project_context || '',
    working_principles: blocks.blocks.working_principles || '',
  }
}

const applyPreset = (preset: typeof presetPersonalities[number]) => {
  localParams.value = { ...preset.params }
}

const saveSettings = async () => {
  saving.value = true
  saveMessage.value = ''
  try {
    const ok = await settingsStore.updatePersonality({
      parameters: { ...localParams.value },
      communication_style: communicationStyle.value,
      behavior_rules: behaviorRules.value.filter((item) => item.trim()),
    })
    if (!ok) {
      saveMessage.value = '人格参数保存失败'
      return
    }
    await Promise.all(
      Object.entries(coreBlocks.value).map(([block, content]) => memoryApi.updateCoreBlock(block, content))
    )
    saveMessage.value = '人格设置与 Core Memory Blocks 已保存'
  } catch (error) {
    console.error(error)
    saveMessage.value = '保存失败'
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <div class="space-y-6">
    <section class="rounded-2xl border border-slate-700 bg-slate-800/80 p-6">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-lg font-semibold text-white">人格参数</h2>
          <p class="mt-1 text-sm text-slate-400">10 维参数 + 4 个预设，保存后同步写入人格设置。</p>
        </div>
        <div v-if="saveMessage" class="rounded-lg bg-slate-700 px-3 py-2 text-sm text-slate-200">
          {{ saveMessage }}
        </div>
      </div>

      <div class="mt-6 grid gap-3 md:grid-cols-4">
        <button
          v-for="preset in presetPersonalities"
          :key="preset.name"
          class="rounded-xl bg-slate-700 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-600"
          @click="applyPreset(preset)"
        >
          {{ preset.name }}
        </button>
      </div>

      <div class="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <div v-for="(value, key) in params" :key="key" class="rounded-xl bg-slate-900 p-4">
          <div class="flex items-center justify-between text-sm">
            <label class="text-slate-300">{{ String(key).replace('_', ' ') }}</label>
            <span class="text-white">{{ Number(value).toFixed(1) }}</span>
          </div>
          <input
            v-model.number="localParams[key]"
            type="range"
            min="0"
            max="1"
            step="0.1"
            class="mt-3 h-2 w-full cursor-pointer appearance-none rounded-lg bg-slate-700 accent-blue-500"
          />
        </div>
      </div>
    </section>

    <section class="rounded-2xl border border-slate-700 bg-slate-800/80 p-6">
      <h2 class="text-lg font-semibold text-white">沟通风格与行为规则</h2>
      <div class="mt-6 grid gap-6 xl:grid-cols-[1.2fr,1fr]">
        <div>
          <label class="mb-3 block text-sm font-medium text-slate-300">communication_style</label>
          <textarea
            v-model="communicationStyle"
            rows="5"
            class="w-full rounded-xl border border-slate-600 bg-slate-900 px-4 py-3 text-sm text-white outline-none focus:border-blue-500"
            placeholder="描述 TARS 的沟通风格"
          />
        </div>

        <div>
          <label class="mb-3 block text-sm font-medium text-slate-300">behavior_rules</label>
          <div class="space-y-2">
            <div v-for="(_rule, index) in behaviorRules" :key="index" class="flex items-center gap-2">
              <input
                v-model="behaviorRules[index]"
                class="flex-1 rounded-xl border border-slate-600 bg-slate-900 px-4 py-2 text-sm text-white outline-none focus:border-blue-500"
              />
              <button
                class="rounded-lg bg-red-600/20 px-3 py-2 text-sm text-red-300"
                @click="behaviorRules.splice(index, 1)"
              >
                删除
              </button>
            </div>
            <button
              class="w-full rounded-xl border border-dashed border-slate-600 px-4 py-3 text-sm text-slate-300 transition hover:border-blue-500 hover:text-white"
              @click="behaviorRules.push('')"
            >
              + 添加规则
            </button>
          </div>
        </div>
      </div>
    </section>

    <section class="rounded-2xl border border-slate-700 bg-slate-800/80 p-6">
      <div>
        <h2 class="text-lg font-semibold text-white">Core Memory Blocks</h2>
        <p class="mt-1 text-sm text-slate-400">直接查看和编辑 4 个核心记忆块，避免已有记忆在前端漏显。</p>
      </div>
      <div class="mt-6 space-y-5">
        <div v-for="(content, key) in coreBlocks" :key="key" class="rounded-2xl bg-slate-950 p-4">
          <label class="mb-3 block text-sm font-medium text-slate-300">
            {{ coreBlockTitles[key] || key }}
          </label>
          <textarea
            v-model="coreBlocks[key]"
            :rows="key === 'persona' ? 6 : 4"
            class="w-full rounded-2xl border border-slate-600 bg-slate-900 px-4 py-4 text-sm leading-6 text-white outline-none focus:border-blue-500"
          />
        </div>
      </div>
    </section>

    <button
      class="w-full rounded-2xl bg-blue-600 px-4 py-3 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
      :disabled="saving"
      @click="saveSettings"
    >
      {{ saving ? '保存中...' : '保存人格设置' }}
    </button>
  </div>
</template>
