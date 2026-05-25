import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ChartRenderer from './ChartRenderer.vue'

describe('ChartRenderer table', () => {
  it('renders styled table with row numbers and numeric alignment', () => {
    const wrapper = mount(ChartRenderer, {
      props: {
        chartType: 'table',
        echartsOption: {
          columns: [
            { field: 'id', header: 'id' },
            { field: 'amount', header: 'amount' },
          ],
          data: [
            { id: 1, amount: 1234.5 },
            { id: 2, amount: null },
          ],
        },
      },
    })

    expect(wrapper.find('.table-shell').exists()).toBe(true)
    expect(wrapper.findAll('.col-index')).toHaveLength(3)
    expect(wrapper.find('.col-numeric').exists()).toBe(true)
    expect(wrapper.text()).toContain('NULL')
    expect(wrapper.text()).toContain('1,234.5')
  })
})
