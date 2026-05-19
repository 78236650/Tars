import { describe, expect, it } from 'vitest'
import router from './index'

describe('insight route', () => {
  it('registers /insight workbench', () => {
    const match = router.resolve('/insight')
    expect(match.name).toBe('insight')
    expect(match.matched.length).toBeGreaterThan(0)
  })
})
