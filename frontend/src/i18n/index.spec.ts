import { beforeEach, describe, expect, it } from 'vitest'
import { useI18n } from './index'

describe('useI18n', () => {
  beforeEach(() => {
    localStorage.clear()

    const { setLocale } = useI18n()
    setLocale('zh')
  })

  it('toggles locale and persists the selected language', () => {
    const { locale, toggleLocale } = useI18n()

    expect(locale.value).toBe('zh')

    toggleLocale()

    expect(locale.value).toBe('en')
    expect(localStorage.getItem('tars_locale')).toBe('en')
  })

  it('falls back to zh and supports parameter replacement', () => {
    const { t, setLocale } = useI18n()

    setLocale('en')

    expect(t('common.save')).toBe('Save')
    expect(t('missing.key')).toBe('missing.key')
    expect(t('modelsPage.fetchOk', { count: 3 })).toBe('Fetched 3 models')
  })
})
