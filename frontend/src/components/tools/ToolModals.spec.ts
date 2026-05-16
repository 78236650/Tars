import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import AddToolModal from './AddToolModal.vue'
import ToolDetailModal from './ToolDetailModal.vue'

describe('tool modals', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('renders add-tool actions inside the shared dialog shell', () => {
    const wrapper = mount(AddToolModal)

    expect(wrapper.find('[data-test="surface-close"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('创建')
  })

  it('renders tool detail actions inside the shared dialog shell', () => {
    const wrapper = mount(ToolDetailModal, {
      props: {
        tool: {
          id: 'skill-1',
          name: 'Prompt Writer',
          type: 'prompt',
          description: '帮助生成写作提示词',
          enabled: true,
        },
      },
    })

    expect(wrapper.find('[data-test="surface-close"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('禁用')
  })
})
