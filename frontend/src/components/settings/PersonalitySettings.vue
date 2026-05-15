<script setup lang="ts">import { ref, computed } from 'vue';
import { useSettingsStore } from '@/stores/settings';
const settingsStore = useSettingsStore();
const localParams = ref({});
const communicationStyle = ref('');
const behaviorRules = ref<string[]>([]);
const showSuccess = ref(false);
const presetPersonalities = [
 { name: 'Professional', params: { honesty: 0.9, humor: 0.3, initiative: 0.8, empathy: 0.6, formality: 0.8, creativity: 0.5, conciseness: 0.8, technical_depth: 0.9, curiosity: 0.7, skepticism: 0.6 } },
 { name: 'Friendly', params: { honesty: 0.8, humor: 0.7, initiative: 0.6, empathy: 0.9, formality: 0.3, creativity: 0.7, conciseness: 0.5, technical_depth: 0.4, curiosity: 0.8, skepticism: 0.2 } },
 { name: 'Creative', params: { honesty: 0.7, humor: 0.6, initiative: 0.9, empathy: 0.7, formality: 0.4, creativity: 0.9, conciseness: 0.4, technical_depth: 0.5, curiosity: 0.9, skepticism: 0.3 } },
 { name: 'Scholar', params: { honesty: 0.9, humor: 0.2, initiative: 0.7, empathy: 0.5, formality: 0.9, creativity: 0.6, conciseness: 0.9, technical_depth: 0.8, curiosity: 0.8, skepticism: 0.7 } }
];
const params = computed(() => {
 if (settingsStore.personality) {
 return { ...settingsStore.personality.parameters, ...localParams.value };
 }
 return localParams.value;
});
const loadParams = () => {
 if (settingsStore.personality) {
 localParams.value = { ...settingsStore.personality.parameters };
 communicationStyle.value = settingsStore.personality.communication_style;
 behaviorRules.value = [...settingsStore.personality.behavior_rules];
 }
};
const applyPreset = (preset: typeof presetPersonalities[0]) => {
 localParams.value = { ...preset.params };
};
const saveSettings = async () => {
 const result = await settingsStore.updatePersonality({
 parameters: { ...localParams.value },
 communication_style: communicationStyle.value,
 behavior_rules: behaviorRules.value
 });
 if (result) {
 showSuccess.value = true;
 setTimeout(() => showSuccess.value = false, 3000);
 }
};
loadParams();
</script>

<template>
  <div class="max-w-4xl mx-auto">
    <div class="bg-slate-800 rounded-xl p-6">
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-xl font-semibold text-white">Personality Settings</h2>
        <div v-if="showSuccess" class="flex items-center gap-2 px-4 py-2 bg-green-900/50 text-green-400 rounded-lg">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
          </svg>
          <span class="text-sm">Settings saved successfully</span>
        </div>
      </div>
      
      <div class="mb-6">
        <label class="block text-sm font-medium text-slate-300 mb-3">Personality Preset</label>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
          <button
            v-for="preset in presetPersonalities"
            :key="preset.name"
            @click="applyPreset(preset)"
            class="px-4 py-3 bg-slate-700 hover:bg-slate-600 rounded-lg text-white transition-colors"
          >
            {{ preset.name }}
          </button>
        </div>
      </div>
      
      <div class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <div v-for="(value, key) in params" :key="key" class="bg-slate-700 rounded-lg p-4">
          <label class="block text-sm text-slate-400 mb-2 capitalize">{{ String(key).replace('_', ' ') }}</label>
          <input
            type="range"
            v-model.number="localParams[key]"
            min="0"
            max="1"
            step="0.1"
            class="w-full h-2 bg-slate-600 rounded-lg appearance-none cursor-pointer accent-blue-500"
          />
          <p class="text-sm text-white mt-2 text-center">{{ Number(value).toFixed(1) }}</p>
        </div>
      </div>
      
      <div class="mb-6">
        <label class="block text-sm font-medium text-slate-300 mb-3">Communication Style</label>
        <textarea
          v-model="communicationStyle"
          rows="3"
          class="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-3 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          placeholder="Describe the communication style..."
        ></textarea>
      </div>
      
      <div class="mb-6">
        <label class="block text-sm font-medium text-slate-300 mb-3">Behavior Rules</label>
        <div class="space-y-2">
          <div
            v-for="(rule, index) in behaviorRules"
            :key="index"
            class="flex items-center gap-2"
          >
            <input
              v-model="behaviorRules[index]"
              class="flex-1 bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              @click="behaviorRules.splice(index, 1)"
              class="p-2 text-red-400 hover:bg-red-900/50 rounded-lg transition-colors"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>
          <button
            @click="behaviorRules.push('')"
            class="w-full py-2 border border-dashed border-slate-600 rounded-lg text-slate-400 hover:border-blue-500 hover:text-blue-400 transition-colors"
          >
            + Add Rule
          </button>
        </div>
      </div>
      
      <button
        @click="saveSettings"
        class="w-full py-3 bg-blue-600 hover:bg-blue-700 rounded-xl text-white font-medium transition-colors"
      >
        Save Personality Settings
      </button>
    </div>
  </div>
</template>