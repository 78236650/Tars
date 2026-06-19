<template>
  <div class="semantic-view p-6">
    <h1 class="text-xl font-bold mb-4">{{ t('nav.semantic') }}</h1>
    <p class="text-sm text-stone-400 mb-6">{{ t('nav.semantic.subtitle') }}</p>

    <div class="flex gap-4 mb-6 items-end flex-wrap">
      <div>
        <label class="block text-xs text-stone-400 mb-1">{{ t('semantic.domain') }}</label>
        <select v-model="domainFilter" class="ds-select" @change="loadTerms">
          <option value="">{{ t('semantic.allDomains') }}</option>
          <option v-for="d in domains" :key="d" :value="d">{{ d }}</option>
        </select>
      </div>
      <button class="btn-primary" @click="showCreate = true">{{ t('semantic.addTerm') }}</button>
    </div>

    <div class="grid gap-4 md:grid-cols-2">
      <div class="bg-white/[0.04] rounded-lg p-4">
        <h2 class="text-sm font-semibold mb-3">{{ t('semantic.glossary') }} ({{ terms.length }})</h2>
        <ul class="space-y-2 max-h-96 overflow-y-auto">
          <li v-for="term in terms" :key="term.id" class="border-b border-amber-100/10 pb-2">
            <div class="flex justify-between items-start gap-2">
              <div>
                <span class="font-medium text-amber-200">{{ term.term }}</span>
                <span class="text-xs text-stone-500 ml-2">{{ term.domain }}</span>
                <p class="text-sm text-stone-400 mt-1">{{ term.definition }}</p>
              </div>
              <button class="text-red-400 text-xs shrink-0" @click="removeTerm(term.id)">×</button>
            </div>
          </li>
        </ul>
      </div>

      <div class="bg-white/[0.04] rounded-lg p-4">
        <h2 class="text-sm font-semibold mb-3">{{ t('semantic.fieldBindings') }}</h2>
        <div class="flex gap-2 mb-3 flex-wrap">
          <select v-model="datasourceId" class="ds-select flex-1 min-w-[120px]" @change="loadBindings">
            <option value="">{{ t('semantic.pickDatasource') }}</option>
            <option v-for="ds in datasources" :key="ds.id" :value="ds.id">{{ ds.name }}</option>
          </select>
          <input v-model="tableName" class="ds-select w-32" :placeholder="t('semantic.table')" @keyup.enter="loadBindings" />
        </div>
        <ul v-if="bindings.length" class="space-y-2 max-h-80 overflow-y-auto">
          <li v-for="b in bindings" :key="b.id" class="text-sm flex justify-between items-center">
            <span>{{ b.table_name }}.{{ b.column_name }} → {{ b.suggested_term || b.term_id }}</span>
            <span class="text-xs" :class="b.status === 'confirmed' ? 'text-emerald-400' : 'text-amber-400'">{{ b.status }}</span>
          </li>
        </ul>
        <p v-else class="text-sm text-stone-500">{{ t('semantic.noBindings') }}</p>
      </div>
    </div>

    <div v-if="showCreate" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-stone-800 rounded-xl p-6 w-full max-w-md">
        <h3 class="text-lg font-semibold mb-4">{{ t('semantic.addTerm') }}</h3>
        <input v-model="newTerm.term" class="ds-select w-full mb-2" :placeholder="t('semantic.termName')" />
        <textarea v-model="newTerm.definition" class="ds-select w-full mb-2 h-24" :placeholder="t('semantic.definition')" />
        <input v-model="newTerm.domain" class="ds-select w-full mb-4" placeholder="domain" />
        <div class="flex gap-2 justify-end">
          <button class="btn-secondary" @click="showCreate = false">{{ t('common.cancel') }}</button>
          <button class="btn-primary" @click="createTerm">{{ t('common.save') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { semanticApi, type GlossaryTerm, type FieldSemantic } from '@/api/semantic'
import { useBiDataSources } from '@/composables/useBiDataSources'
import { useI18n } from '@/i18n'

const { t } = useI18n()
const { datasources, loadDataSources } = useBiDataSources()

const terms = ref<GlossaryTerm[]>([])
const bindings = ref<FieldSemantic[]>([])
const domainFilter = ref('')
const datasourceId = ref('')
const tableName = ref('')
const showCreate = ref(false)
const domains = ['port', 'vessel', 'container', 'berth', 'yard', 'operation', 'document', 'customs', 'trade', 'equipment']

const newTerm = reactive({ term: '', definition: '', domain: 'port' })

async function loadTerms() {
  terms.value = await semanticApi.listTerms(domainFilter.value || undefined)
}

async function loadBindings() {
  if (!datasourceId.value) {
    bindings.value = []
    return
  }
  bindings.value = await semanticApi.listFieldSemantics(
    datasourceId.value,
    tableName.value || undefined,
  )
}

async function createTerm() {
  await semanticApi.createTerm({ ...newTerm })
  showCreate.value = false
  newTerm.term = ''
  newTerm.definition = ''
  await loadTerms()
}

async function removeTerm(id: string) {
  await semanticApi.deleteTerm(id)
  await loadTerms()
}

onMounted(async () => {
  await loadDataSources()
  await loadTerms()
})
</script>

<style scoped>
.ds-select {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(217,119,6,0.1);
  color: #d6d3d1;
  padding: 0.5rem 0.75rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
}
.btn-primary { background: #d97706; color: #1c1917; padding: 0.5rem 1rem; border-radius: 0.5rem; font-size: 0.875rem; font-weight: 500; }
.btn-secondary { background: rgba(255,255,255,0.06); color: #d6d3d1; padding: 0.5rem 1rem; border-radius: 0.5rem; font-size: 0.875rem; }
</style>
