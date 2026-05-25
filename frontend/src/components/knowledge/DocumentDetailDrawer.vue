<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { knowledgeApi } from '@/api'
import type { DocProfile, DocumentPassage, KnowledgeDocument } from '@/types'
import { useI18n } from '@/i18n'
import { useToast } from '@/composables/useToast'
import { getErrorDetail } from '@/utils/errorExtractor'

const props = defineProps<{
  open: boolean
  collectionId: string
  document: KnowledgeDocument | null
}>()

const emit = defineEmits<{ close: [] }>()

const { t } = useI18n()
const toast = useToast()

const profile = ref<DocProfile | null>(null)
const loading = ref(false)
const reEnriching = ref(false)
const expandedSectionId = ref<string | null>(null)
const sectionPassages = ref<Record<string, DocumentPassage[]>>({})
const pollTimer = ref<number | null>(null)

const CONFIDENCE_THRESHOLD = 0.6
const POLL_INTERVAL_MS = 2000
const POLL_TIMEOUT_MS = 60000

const isProcessing = computed(() => {
  const status = profile.value?.status || props.document?.status || ''
  return ['pending', 'parsing', 'enriching', 'indexing'].includes(status)
})

const showLowConfidence = computed(() => {
  const c = profile.value?.confidence
  return c != null && c < CONFIDENCE_THRESHOLD
})

const docTypeLabel = computed(() => {
  const type = profile.value?.doc_type || props.document?.doc_type || 'generic'
  return t(`knowledge.docType.${type}`)
})

const statusLabel = computed(() => {
  const status = profile.value?.status || props.document?.status || ''
  return t(`knowledge.docStatus.${status}`, status)
})

function stopPolling() {
  if (pollTimer.value != null) {
    window.clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

async function loadProfile() {
  if (!props.document) return
  loading.value = true
  try {
    profile.value = await knowledgeApi.getDocumentProfile(props.collectionId, props.document.id)
  } catch (e) {
    toast.error(t('knowledge.detail.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function pollStatus(startedAt: number) {
  if (!props.document) return
  if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
    stopPolling()
    return
  }
  try {
    const status = await knowledgeApi.getDocumentStatus(props.collectionId, props.document.id)
    if (profile.value) {
      profile.value.status = status.status
      profile.value.profile_ready = status.profile_ready
      profile.value.one_liner = status.one_liner || profile.value.one_liner
    }
    if (['ready', 'enrichment_failed', 'failed'].includes(status.status)) {
      stopPolling()
      await loadProfile()
    }
  } catch {
    stopPolling()
  }
}

function startPollingIfNeeded() {
  stopPolling()
  if (!props.document || !isProcessing.value) return
  const startedAt = Date.now()
  pollTimer.value = window.setInterval(() => pollStatus(startedAt), POLL_INTERVAL_MS)
}

async function toggleSection(sectionId: string) {
  if (expandedSectionId.value === sectionId) {
    expandedSectionId.value = null
    return
  }
  expandedSectionId.value = sectionId
  if (!sectionPassages.value[sectionId] && props.document) {
    try {
      const res = await knowledgeApi.getDocumentPassages(props.collectionId, props.document.id, sectionId)
      sectionPassages.value[sectionId] = res.passages
    } catch {
      toast.error(t('knowledge.detail.passagesFailed'))
    }
  }
}

async function handleReEnrich() {
  if (!props.document) return
  reEnriching.value = true
  try {
    await knowledgeApi.reEnrichDocument(props.collectionId, props.document.id)
    if (profile.value) {
      profile.value.status = 'pending'
      profile.value.profile_ready = false
    }
    startPollingIfNeeded()
    toast.success(t('knowledge.detail.reEnrichStarted'))
  } catch (e: any) {
    toast.error(getErrorDetail(e) || t('knowledge.detail.reEnrichFailed'))
  } finally {
    reEnriching.value = false
  }
}

watch(
  () => [props.open, props.document?.id] as const,
  async ([open]) => {
    if (!open || !props.document) {
      stopPolling()
      profile.value = null
      expandedSectionId.value = null
      sectionPassages.value = {}
      return
    }
    await loadProfile()
    startPollingIfNeeded()
  },
  { immediate: true },
)

onUnmounted(stopPolling)
</script>

<template>
  <Teleport to="body">
    <div v-if="open && document" class="drawer-backdrop" @click.self="emit('close')">
      <aside class="drawer-panel" data-test="document-detail-drawer">
        <header class="drawer-header">
          <div>
            <h2>{{ profile?.title || document.file_name }}</h2>
            <div class="badges">
              <span class="badge type">{{ docTypeLabel }}</span>
              <span class="badge status" :class="profile?.status || document.status">{{ statusLabel }}</span>
              <span v-if="showLowConfidence" class="badge warn">{{ t('knowledge.detail.lowConfidence') }}</span>
            </div>
          </div>
          <button type="button" class="drawer-close" data-test="drawer-close" @click="emit('close')">×</button>
        </header>

        <div v-if="loading && !profile" class="drawer-loading">{{ t('knowledge.detail.loading') }}</div>

        <div v-else-if="isProcessing" class="drawer-loading">
          {{ t('knowledge.detail.processing', { status: statusLabel }) }}
        </div>

        <div v-else-if="!profile?.summary && !profile?.key_points?.length" class="drawer-empty">
          <p>{{ t('knowledge.detail.noProfile') }}</p>
          <button class="btn-primary" :disabled="reEnriching" data-test="re-enrich-btn" @click="handleReEnrich">
            {{ reEnriching ? t('knowledge.detail.reEnriching') : t('knowledge.detail.reEnrich') }}
          </button>
        </div>

        <div v-else class="drawer-body">
          <section v-if="profile?.one_liner" class="block">
            <h3>{{ t('knowledge.detail.oneLiner') }}</h3>
            <p>{{ profile.one_liner }}</p>
          </section>

          <section v-if="profile?.summary" class="block">
            <h3>{{ t('knowledge.detail.summary') }}</h3>
            <p class="summary-text">{{ profile.summary }}</p>
          </section>

          <section v-if="profile?.key_points?.length" class="block" data-test="key-points">
            <h3>{{ t('knowledge.detail.keyPoints') }}</h3>
            <ul>
              <li v-for="(point, idx) in profile.key_points" :key="idx">{{ point }}</li>
            </ul>
          </section>

          <section v-if="profile?.key_facts?.length" class="block">
            <h3>{{ t('knowledge.detail.keyFacts') }}</h3>
            <ul>
              <li v-for="(fact, idx) in profile.key_facts" :key="idx">{{ fact }}</li>
            </ul>
          </section>

          <section v-if="profile?.sections?.length" class="block">
            <h3>{{ t('knowledge.detail.sections') }}</h3>
            <div v-for="sec in profile.sections" :key="sec.section_id" class="section-item">
              <div class="section-head">
                <strong>{{ sec.title }}</strong>
                <button type="button" class="link-btn" @click="toggleSection(sec.section_id)">
                  {{ expandedSectionId === sec.section_id ? t('knowledge.detail.collapse') : t('knowledge.detail.expandPassage') }}
                </button>
              </div>
              <p v-if="sec.summary" class="section-summary">{{ sec.summary }}</p>
              <div v-if="expandedSectionId === sec.section_id && sectionPassages[sec.section_id]?.length" class="passages">
                <p v-for="p in sectionPassages[sec.section_id]" :key="p.chunk_index" class="passage-text">{{ p.text }}</p>
              </div>
            </div>
          </section>

          <section v-if="profile?.glossary?.length" class="block">
            <h3>{{ t('knowledge.detail.glossary') }}</h3>
            <dl>
              <template v-for="item in profile.glossary" :key="item.term">
                <dt>{{ item.term }}</dt>
                <dd>{{ item.definition }}</dd>
              </template>
            </dl>
          </section>

          <section v-if="profile?.enriched_at" class="block meta">
            <span>{{ t('knowledge.detail.enrichedAt', { time: profile.enriched_at }) }}</span>
            <span v-if="profile.confidence != null">{{ t('knowledge.detail.confidence', { value: (profile.confidence * 100).toFixed(0) }) }}</span>
          </section>

          <div v-if="profile?.status === 'enrichment_failed'" class="actions">
            <button class="btn-primary" :disabled="reEnriching" @click="handleReEnrich">
              {{ reEnriching ? t('knowledge.detail.reEnriching') : t('knowledge.detail.reEnrich') }}
            </button>
          </div>
        </div>
      </aside>
    </div>
  </Teleport>
</template>

<style scoped>
.drawer-backdrop {
  position: fixed;
  inset: 0;
  z-index: 60;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  justify-content: flex-end;
}
.drawer-panel {
  width: min(480px, 94vw);
  height: 100%;
  background: #1c1917;
  border-left: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.drawer-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.drawer-header h2 {
  margin: 0 0 8px;
  font-size: 18px;
  color: #f5f0e8;
}
.badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: #d6d3d1;
}
.badge.type { background: rgba(217, 119, 6, 0.2); color: #fbbf24; }
.badge.warn { background: rgba(234, 179, 8, 0.15); color: #facc15; }
.badge.ready { background: rgba(34, 197, 94, 0.15); color: #86efac; }
.badge.enrichment_failed, .badge.failed { background: rgba(239, 68, 68, 0.15); color: #fca5a5; }
.drawer-close {
  background: none;
  border: none;
  color: #a8a29e;
  font-size: 24px;
  cursor: pointer;
  line-height: 1;
}
.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 18px 24px;
}
.drawer-loading, .drawer-empty {
  padding: 24px 18px;
  color: #a8a29e;
}
.block {
  margin-bottom: 20px;
}
.block h3 {
  margin: 0 0 8px;
  font-size: 13px;
  color: #fbbf24;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.block p, .block li, .block dd {
  color: #d6d3d1;
  font-size: 14px;
  line-height: 1.6;
}
.summary-text { white-space: pre-wrap; }
.block ul { margin: 0; padding-left: 18px; }
.section-item {
  margin-bottom: 12px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
}
.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.link-btn {
  background: none;
  border: none;
  color: #fbbf24;
  cursor: pointer;
  font-size: 12px;
}
.passage-text {
  margin-top: 8px;
  font-size: 13px;
  color: #a8a29e;
  white-space: pre-wrap;
}
.meta {
  font-size: 12px;
  color: #78716c;
  display: flex;
  gap: 12px;
}
.btn-primary {
  background: #d97706;
  color: #0c0b09;
  border: none;
  padding: 8px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}
.actions { margin-top: 12px; }
</style>
