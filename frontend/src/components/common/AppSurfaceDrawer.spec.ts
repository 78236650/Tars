import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AppSurfaceDrawer from './AppSurfaceDrawer.vue'

describe('AppSurfaceDrawer', () => {
  it('renders right-side drawer content when open', () => {
    const wrapper = mount(AppSurfaceDrawer, {
      props: { open: true, title: '提醒详情', side: 'right' },
      slots: { default: '<div class="drawer-body">Drawer</div>' },
    })

    expect(wrapper.find('.drawer-body').exists()).toBe(true)
    expect(wrapper.text()).toContain('提醒详情')
  })
})
