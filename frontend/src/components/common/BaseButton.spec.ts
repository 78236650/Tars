import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import BaseButton from './BaseButton.vue'

describe('BaseButton', () => {
  it('renders slot and applies variant class', () => {
    const w = mount(BaseButton, { props: { variant: 'primary' }, slots: { default: 'Go' } })
    expect(w.text()).toBe('Go')
    expect(w.classes().join(' ')).toContain('btn-primary')
  })
  it('disables when disabled prop set', () => {
    const w = mount(BaseButton, { props: { disabled: true } })
    expect(w.attributes('disabled')).toBeDefined()
  })
})
