import { mount } from '@vue/test-utils'
import { describe, expect, it, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { useI18n } from '@/i18n'
import TranscriptionList from './TranscriptionList.vue'

describe('TranscriptionList', () => {
  beforeEach(() => {
    localStorage.clear()
    useI18n().setLocale('zh')
  })

  it('switches empty-state copy with locale', async () => {
    const wrapper = mount(TranscriptionList, {
      props: { transcriptions: [], selectedId: '' },
    })

    expect(wrapper.text()).toContain('暂无转录记录')

    const { setLocale } = useI18n()
    setLocale('en')
    await nextTick()

    expect(wrapper.text()).toContain('No transcriptions yet')

    setLocale('zh')
  })
})
