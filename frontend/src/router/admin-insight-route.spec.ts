import { describe, expect, it } from 'vitest'
import router from './index'

describe('admin insight route', () => {
  it('registers /admin/insight/llm', () => {
    const match = router.resolve('/admin/insight/llm')
    expect(match.name).toBe('admin-insight-llm')
  })
})
