import { describe, expect, it } from 'vitest'
import {
  resolveTemplateId,
  roleBadgeClass,
  roleToTemplate,
  templateDisplayName,
} from './roleDisplay'

describe('roleDisplay', () => {
  const t = (key: string) => (key === 'role.developer' ? '开发者' : key)

  it('maps legacy roles to template ids', () => {
    expect(roleToTemplate('admin')).toBe('admin')
    expect(roleToTemplate('user')).toBe('standard')
    expect(roleToTemplate('guest')).toBe('readonly')
  })

  it('prefers role_template_id when present', () => {
    expect(
      resolveTemplateId({ role: 'user', role_template_id: 'developer' }),
    ).toBe('developer')
  })

  it('uses i18n label before template name', () => {
    expect(templateDisplayName('developer', t, [{ id: 'developer', name: 'Dev' }])).toBe('开发者')
  })

  it('styles badges by resolved template id', () => {
    expect(roleBadgeClass({ role: 'user', role_template_id: 'developer' })).toContain('violet')
  })
})
