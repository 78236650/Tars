<template>
  <div class="governance-view p-6">
    <h1 class="text-xl font-bold mb-4">数据治理</h1>

    <!-- 数据源 / 表选择 -->
    <div class="flex gap-4 mb-4 items-end">
      <div>
        <label class="block text-xs text-stone-400 mb-1">数据源</label>
        <select v-model="datasourceId" @change="onDatasourceChange" class="ds-select">
          <option value="">选择数据源</option>
          <option v-for="ds in datasources" :key="ds.id" :value="ds.id">
            {{ ds.name }} ({{ ds.db_type }})
          </option>
        </select>
      </div>
      <div>
        <label class="block text-xs text-stone-400 mb-1">表名</label>
        <input
          v-model="tableName"
          type="text"
          class="ds-select"
          placeholder="输入表名"
          @change="loadRules"
        />
      </div>
      <button @click="loadRules" class="btn-primary" :disabled="!datasourceId">
        刷新规则
      </button>
      <button
        @click="runValidate"
        class="btn-primary"
        :disabled="!datasourceId || !tableName"
      >
        跑校验
      </button>
      <button @click="showCreate = true" class="btn-secondary" :disabled="!datasourceId || !tableName">
        + 新建规则
      </button>
    </div>

    <!-- 规则列表 -->
    <div v-if="loading" class="text-stone-400">加载中...</div>

    <div v-if="rules.length" class="mb-6">
      <h2 class="text-lg font-semibold mb-2">质量规则（{{ rules.length }}）</h2>
      <ul class="space-y-2">
        <li v-for="rule in rules" :key="rule.id"
          class="flex items-center justify-between bg-white/[0.04] rounded p-3">
          <div>
            <span class="font-medium">{{ rule.name }}</span>
            <span class="text-xs text-stone-400 ml-2">{{ rule.kind }}</span>
            <span v-if="rule.engine !== 'builtin'" class="text-xs text-amber-400 ml-1">({{ rule.engine }})</span>
          </div>
          <button @click="removeRule(rule.id)" class="text-red-400 hover:text-red-300 text-sm">
            删除
          </button>
        </li>
      </ul>
    </div>

    <!-- 校验报告 -->
    <div v-if="report" class="mt-6">
      <h2 class="text-lg font-semibold mb-2">校验报告</h2>
      <div class="flex gap-4 mb-4 text-sm">
        <span :class="report.status === 'passed' ? 'text-emerald-400' : 'text-red-400'">
          状态：{{ report.status === 'passed' ? '通过' : report.status === 'error' ? '出错' : '失败' }}
        </span>
        <span class="text-stone-400">总行数：{{ report.total_rows }}</span>
        <span v-if="report.truncated" class="text-amber-400">（抽样）</span>
      </div>

      <div v-if="report.summary.errors.length" class="mb-4 bg-red-500/10 border border-red-500/20 rounded p-3">
        <p v-for="(e,i) in report.summary.errors" :key="i" class="text-red-400 text-sm">{{ e }}</p>
      </div>

      <ul class="space-y-2">
        <li v-for="rr in report.summary.rule_results" :key="rr.rule_id"
          class="bg-white/[0.04] rounded p-3">
          <div class="flex justify-between mb-1">
            <span class="font-medium">{{ rr.rule_name }}</span>
            <span :class="rr.failed_count === 0 ? 'text-emerald-400' : 'text-red-400'">
              {{ rr.passed_count }} / {{ rr.passed_count + rr.failed_count }}
            </span>
          </div>
          <div v-if="rr.sample_violations?.length" class="mt-2">
            <p class="text-xs text-stone-400 mb-1">异常样本：</p>
            <pre class="text-xs text-red-300 bg-black/20 rounded p-2 overflow-auto">{{ JSON.stringify(rr.sample_violations.slice(0, 5), null, 2) }}</pre>
          </div>
        </li>
      </ul>
    </div>

    <!-- 新建规则弹窗 -->
    <div v-if="showCreate" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-stone-800 rounded-xl p-6 w-full max-w-md">
        <h3 class="text-lg font-semibold mb-4">新建质量规则</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-stone-400 mb-1">规则类型</label>
            <select v-model="form.kind" class="ds-select w-full">
              <option v-for="k in ruleKinds" :key="k" :value="k">{{ k }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs text-stone-400 mb-1">规则名称</label>
            <input v-model="form.name" type="text" class="ds-select w-full" placeholder="如：名称非空" />
          </div>
          <div v-if="form.kind !== 'cross_field'">
            <label class="block text-xs text-stone-400 mb-1">字段</label>
            <input v-model="form.field" type="text" class="ds-select w-full" placeholder="列名" />
          </div>
          <template v-if="form.kind === 'cross_field'">
            <div>
              <label class="block text-xs text-stone-400 mb-1">左字段</label>
              <input v-model="form.left" type="text" class="ds-select w-full" />
            </div>
            <div>
              <label class="block text-xs text-stone-400 mb-1">右字段</label>
              <input v-model="form.right" type="text" class="ds-select w-full" />
            </div>
            <div>
              <label class="block text-xs text-stone-400 mb-1">比较符</label>
              <select v-model="form.op" class="ds-select w-full">
                <option value="<="><=</option>
                <option value="<"><</option>
                <option value=">=">>=</option>
                <option value=">">></option>
                <option value="==">==</option>
                <option value="!=">!=</option>
              </select>
            </div>
          </template>
          <template v-if="form.kind === 'range'">
            <div>
              <label class="block text-xs text-stone-400 mb-1">最小值</label>
              <input v-model.number="form.min" type="number" class="ds-select w-full" />
            </div>
            <div>
              <label class="block text-xs text-stone-400 mb-1">最大值</label>
              <input v-model.number="form.max" type="number" class="ds-select w-full" />
            </div>
          </template>
          <div v-if="form.kind === 'regex'">
            <label class="block text-xs text-stone-400 mb-1">正则</label>
            <input v-model="form.pattern" type="text" class="ds-select w-full" placeholder="^ok$" />
          </div>
          <div v-if="form.kind === 'enum'">
            <label class="block text-xs text-stone-400 mb-1">允许值（逗号分隔）</label>
            <input v-model="form.values" type="text" class="ds-select w-full" placeholder="ok,done" />
          </div>
        </div>
        <div class="flex gap-2 mt-6 justify-end">
          <button @click="showCreate = false" class="btn-secondary">取消</button>
          <button @click="submitRule" class="btn-primary" :disabled="!form.kind || !form.name">
            创建
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { governanceApi } from '@/api/governance'
import type { QualityRule, CheckRunReport } from '@/api/governance'
import { useBiDataSources } from '@/composables/useBiDataSources'
import type { DataSource } from '@/types'

const { datasources, loadDataSources } = useBiDataSources()

const datasourceId = ref('')
const tableName = ref('')
const rules = ref<QualityRule[]>([])
const ruleKinds = ref<string[]>([])
const loading = ref(false)
const showCreate = ref(false)
const report = ref<CheckRunReport | null>(null)

const form = ref({
  kind: 'not_null',
  name: '',
  field: '',
  left: '',
  right: '',
  op: '<=',
  min: undefined as number | undefined,
  max: undefined as number | undefined,
  pattern: '',
  values: '',
})

onMounted(async () => {
  await loadDataSources()
  ruleKinds.value = await governanceApi.ruleKinds()
})

async function loadRules() {
  if (!datasourceId.value) return
  loading.value = true
  rules.value = await governanceApi.listRules(datasourceId.value, tableName.value || undefined)
  loading.value = false
}

function onDatasourceChange() {
  loadRules()
}

function buildParams(): Record<string, unknown> {
  const k = form.value.kind
  if (k === 'cross_field') return { left: form.value.left, right: form.value.right, op: form.value.op }
  if (k === 'range') return { field: form.value.field, min: form.value.min, max: form.value.max }
  if (k === 'regex') return { field: form.value.field, pattern: form.value.pattern }
  if (k === 'enum') return { field: form.value.field, values: form.value.values.split(',').map((s: string) => s.trim()) }
  return { field: form.value.field }
}

async function submitRule() {
  await governanceApi.createRule({
    datasource_id: datasourceId.value,
    table_name: tableName.value,
    kind: form.value.kind,
    name: form.value.name,
    params: buildParams(),
    engine: 'builtin',
  })
  showCreate.value = false
  await loadRules()
}

async function removeRule(id: string) {
  await governanceApi.deleteRule(id)
  await loadRules()
}

async function runValidate() {
  report.value = await governanceApi.validate(datasourceId.value, tableName.value)
}
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
.ds-select:focus { outline: none; border-color: rgba(217,119,6,0.4); }
.btn-primary {
  background: #d97706;
  color: #1c1917;
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
}
.btn-primary:disabled { opacity: 0.4; }
.btn-secondary {
  background: rgba(255,255,255,0.06);
  color: #d6d3d1;
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
}
.btn-secondary:hover { background: rgba(255,255,255,0.1); }
</style>
