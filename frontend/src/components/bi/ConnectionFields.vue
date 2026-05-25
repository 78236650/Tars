<template>
  <div class="connection-fields">
    <div class="form-group">
      <label>{{ t('bi.dbTypeLabel') }}</label>
      <select v-model="local.db_type" @change="onDbTypeChange">
        <option value="mysql">MySQL</option>
        <option value="postgresql">PostgreSQL</option>
        <option value="sqlite">SQLite</option>
        <option value="clickhouse">ClickHouse</option>
        <option value="oracle">Oracle</option>
        <option value="sqlserver">SQL Server</option>
        <option value="doris">Doris</option>
      </select>
    </div>

    <template v-if="local.db_type === 'sqlite'">
      <div class="form-group">
        <label>{{ t('bi.sqlitePathLabel') }}</label>
        <input
          v-model="local.database"
          type="text"
          :placeholder="t('bi.sqlitePathPlaceholder')"
        />
      </div>
    </template>

    <template v-else>
      <div class="form-row">
        <div class="form-group flex-2">
          <label>{{ t('bi.hostLabel') }}</label>
          <input
            v-model="local.host"
            type="text"
            :placeholder="t('bi.hostPlaceholder')"
          />
        </div>
        <div class="form-group flex-1">
          <label>{{ t('bi.portLabel') }}</label>
          <input
            v-model.number="local.port"
            type="number"
            min="1"
            max="65535"
          />
        </div>
      </div>

      <div class="form-row">
        <div class="form-group flex-1">
          <label>{{ t('bi.usernameLabel') }}</label>
          <input
            v-model="local.username"
            type="text"
            autocomplete="username"
            :placeholder="t('bi.usernamePlaceholder')"
          />
        </div>
        <div class="form-group flex-1">
          <label>{{ t('bi.passwordLabel') }}</label>
          <input
            v-model="local.password"
            type="password"
            autocomplete="new-password"
            :placeholder="passwordOptional ? t('bi.passwordKeepHint') : t('bi.passwordPlaceholder')"
          />
        </div>
      </div>

      <div class="form-group">
        <label>{{ t('bi.databaseLabel') }}</label>
        <input
          v-model="local.database"
          type="text"
          :placeholder="t('bi.databasePlaceholder')"
        />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from '@/i18n'
import { CONNECTION_DEFAULT_PORTS, type ConnectionFormState } from './connectionForm'

export type { ConnectionFormState }

const props = defineProps<{
  modelValue: ConnectionFormState
  passwordOptional?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: ConnectionFormState]
}>()

const { t } = useI18n()

const local = computed({
  get: () => props.modelValue,
  set: (value: ConnectionFormState) => emit('update:modelValue', value),
})

function onDbTypeChange() {
  const current = props.modelValue
  const dbType = current.db_type
  emit('update:modelValue', {
    ...current,
    port: CONNECTION_DEFAULT_PORTS[dbType] ?? current.port,
    host: dbType === 'sqlite' ? '' : (current.host || '127.0.0.1'),
  })
}
</script>

<style scoped>
.connection-fields {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.form-row {
  display: flex;
  gap: 12px;
}

.flex-1 {
  flex: 1;
}

.flex-2 {
  flex: 2;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
  font-weight: 500;
  color: #d6d3d1;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid rgba(245, 158, 11, 0.15);
  border-radius: 6px;
  font-size: 14px;
  box-sizing: border-box;
  background: rgba(255,255,255,0.04);
  color: #e7e5e4;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: rgba(245, 158, 11, 0.4);
}
</style>
