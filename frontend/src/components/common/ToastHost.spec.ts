import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import ToastHost from './ToastHost.vue'

vi.mock('@/composables/useToast', () => {
  const toasts = ref([
    { id: 1, message: '连接成功', type: 'success' as const },
  ])
  return {
    useToast: () => ({ toasts }),
  }
})

describe('ToastHost', () => {
  it('renders global toast messages', () => {
    const wrapper = mount(ToastHost, { attachTo: document.body })
    expect(document.body.textContent).toContain('连接成功')
    wrapper.unmount()
  })
})
