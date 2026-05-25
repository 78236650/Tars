const STORAGE_KEY = 'meeting_asr_language'

export type MeetingAsrLanguage = 'auto' | 'zh' | 'en'

export function getMeetingAsrLanguage(): MeetingAsrLanguage {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved === 'zh' || saved === 'en' || saved === 'auto') {
    return saved
  }
  return 'zh'
}

export function setMeetingAsrLanguage(language: MeetingAsrLanguage): void {
  localStorage.setItem(STORAGE_KEY, language)
}

export function meetingAsrLanguageForApi(language?: MeetingAsrLanguage): string | undefined {
  const lang = language ?? getMeetingAsrLanguage()
  return lang === 'auto' ? undefined : lang
}
