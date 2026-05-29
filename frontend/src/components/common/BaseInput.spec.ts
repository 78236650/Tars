import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import BaseInput from './BaseInput.vue'

describe('BaseInput', () => {
  it('emits update:modelValue on input', async () => {
    const w = mount(BaseInput, { props: { modelValue: '' } })
    await w.find('input').setValue('hi')
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['hi'])
  })
})
