import type { RoleTemplate } from '@/api'
import type { User } from '@/types'

export function roleToTemplate(role: string): string {
  return { admin: 'admin', user: 'standard', guest: 'readonly' }[role] || 'standard'
}

export function resolveTemplateId(user: Pick<User, 'role' | 'role_template_id'>): string {
  return user.role_template_id || roleToTemplate(user.role)
}

export function templateDisplayName(
  templateId: string,
  t: (key: string) => string,
  templates?: RoleTemplate[],
): string {
  const i18nKey = `role.${templateId}`
  const translated = t(i18nKey)
  if (translated !== i18nKey) return translated
  const tmpl = templates?.find((item) => item.id === templateId)
  return tmpl?.name || templateId
}

export const ROLE_BADGE_CLASSES: Record<string, string> = {
  admin: 'bg-red-900/50 text-red-400',
  developer: 'bg-violet-900/50 text-violet-300',
  analyst: 'bg-sky-900/50 text-sky-300',
  insight_analyst: 'bg-indigo-900/50 text-indigo-300',
  operator: 'bg-orange-900/50 text-orange-300',
  standard: 'bg-blue-900/50 text-blue-400',
  readonly: 'bg-gray-900/50 text-gray-400',
}

export function roleBadgeClass(user: Pick<User, 'role' | 'role_template_id'>): string {
  const id = resolveTemplateId(user)
  return ROLE_BADGE_CLASSES[id] || ROLE_BADGE_CLASSES.standard
}
