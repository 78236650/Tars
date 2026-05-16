import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AppSurfaceDialog from './AppSurfaceDialog.vue'

describe('AppSurfaceDialog', () => {
  it('renders title, description, and footer slot', () => {
    const wrapper = mount(AppSurfaceDialog, {
      props: { open: true, title: '编辑技能', description: '统一弹层壳' },
      slots: {
        default: '<div class="body">Body</div>',
        footer: '<button class="save">保存</button>',
      },
    })

    expect(wrapper.text()).toContain('编辑技能')
    expect(wrapper.text()).toContain('统一弹层壳')
    expect(wrapper.find('.save').exists()).toBe(true)
  })

  it('emits close when the close button is clicked', async () => {
    const wrapper = mount(AppSurfaceDialog, {
      props: { open: true, title: '编辑技能' },
    })

    await wrapper.find('[data-test="surface-close"]').trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
