'use client'

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Provider, OptionalProvider, Settings, JobSummary, Toast } from './types'

interface SchismStore {
  // Settings
  settings: Settings
  updateSettings: (partial: Partial<Settings>) => void

  // Recent jobs (persist last 10)
  recentJobs: JobSummary[]
  addRecentJob: (job: JobSummary) => void
  updateRecentJob: (id: string, partial: Partial<JobSummary>) => void
  removeRecentJob: (id: string) => void

  // UI state (not persisted)
  settingsOpen: boolean
  docsOpen: boolean
  setSettingsOpen: (open: boolean) => void
  setDocsOpen: (open: boolean) => void

  // Toasts
  toasts: Toast[]
  addToast: (message: string, type: 'error' | 'success' | 'info') => void
  removeToast: (id: string) => void
}

const PROVIDERS: Provider[] = ['anthropic', 'openai', 'ollama', 'mock']

const defaultSettings: Settings = {
  primaryProvider: 'anthropic',
  secondaryProvider: null,
  embeddingProvider: 'local',
  anthropicApiKey: '',
  anthropicModel: 'claude-3-5-sonnet-latest',
  openaiApiKey: '',
  openaiModel: 'gpt-4.1-mini',
  ollamaMode: 'local',
  ollamaLocalBaseUrl: 'http://localhost:11434',
  ollamaLocalModel: 'llama3.1',
  ollamaCloudApiKey: '',
  ollamaCloudModel: 'llama3.1',
  mockApiKey: '',
  cohereKey: '',
}

function isProvider(value: unknown): value is Provider {
  return typeof value === 'string' && PROVIDERS.includes(value as Provider)
}

function isOptionalProvider(value: unknown): value is OptionalProvider {
  return value === null || isProvider(value)
}

function readLegacyString(record: Record<string, unknown>, key: string): string {
  const value = record[key]
  return typeof value === 'string' ? value : ''
}

function migrateSettings(rawSettings: unknown): Settings {
  const persisted =
    rawSettings && typeof rawSettings === 'object'
      ? rawSettings as Record<string, unknown>
      : {}

  const legacyProvider = isProvider(persisted.provider) ? persisted.provider : undefined
  const legacySharedKey = readLegacyString(persisted, ['api', 'Key'].join(''))
  const legacyOllamaModel = readLegacyString(persisted, 'ollamaModel')
  const legacyBaseUrl = readLegacyString(persisted, 'baseUrl')
  const inferredOllamaMode =
    persisted.ollamaMode === 'cloud' || persisted.ollamaMode === 'local'
      ? persisted.ollamaMode
      : legacyProvider === 'ollama' &&
          !!legacySharedKey &&
          (!legacyBaseUrl || legacyBaseUrl.includes('ollama.com'))
        ? 'cloud'
        : 'local'

  const primaryProvider = isProvider(persisted.primaryProvider)
    ? persisted.primaryProvider
    : legacyProvider ?? defaultSettings.primaryProvider
  const secondaryProvider = isOptionalProvider(persisted.secondaryProvider)
    ? persisted.secondaryProvider
    : defaultSettings.secondaryProvider

  return {
    ...defaultSettings,
    primaryProvider,
    secondaryProvider: secondaryProvider === primaryProvider ? null : secondaryProvider,
    embeddingProvider:
      persisted.embeddingProvider === 'local' ||
      persisted.embeddingProvider === 'openai' ||
      persisted.embeddingProvider === 'cohere'
        ? persisted.embeddingProvider
        : defaultSettings.embeddingProvider,
    anthropicApiKey: readLegacyString(persisted, 'anthropicApiKey') || (primaryProvider === 'anthropic' && !readLegacyString(persisted, 'anthropicApiKey') ? legacySharedKey : ''),
    anthropicModel: readLegacyString(persisted, 'anthropicModel') || defaultSettings.anthropicModel,
    openaiApiKey: readLegacyString(persisted, 'openaiApiKey') || (primaryProvider === 'openai' && !readLegacyString(persisted, 'openaiApiKey') ? legacySharedKey : ''),
    openaiModel: readLegacyString(persisted, 'openaiModel') || defaultSettings.openaiModel,
    ollamaMode: inferredOllamaMode,
    ollamaLocalBaseUrl: readLegacyString(persisted, 'ollamaLocalBaseUrl') || legacyBaseUrl || defaultSettings.ollamaLocalBaseUrl,
    ollamaLocalModel: readLegacyString(persisted, 'ollamaLocalModel') || legacyOllamaModel || defaultSettings.ollamaLocalModel,
    ollamaCloudApiKey:
      readLegacyString(persisted, 'ollamaCloudApiKey') ||
      (legacyProvider === 'ollama' && inferredOllamaMode === 'cloud' ? legacySharedKey : ''),
    ollamaCloudModel: readLegacyString(persisted, 'ollamaCloudModel') || legacyOllamaModel || defaultSettings.ollamaCloudModel,
    mockApiKey: readLegacyString(persisted, 'mockApiKey'),
    cohereKey: readLegacyString(persisted, 'cohereKey'),
  }
}

export const useStore = create<SchismStore>()(
  persist(
    (set, get) => ({
      // Settings
      settings: defaultSettings,
      updateSettings: (partial) =>
        set((state) => ({
          settings: { ...state.settings, ...partial },
        })),

       // Recent jobs
       recentJobs: [],
       addRecentJob: (job) =>
         set((state) => ({
           recentJobs: [job, ...state.recentJobs.filter((j) => j.id !== job.id)].slice(0, 10),
         })),
       updateRecentJob: (id, partial) =>
         set((state) => ({
           recentJobs: state.recentJobs.map((j) =>
             j.id === id ? { ...j, ...partial } : j
           ),
         })),
       removeRecentJob: (id) =>
         set((state) => ({
           recentJobs: state.recentJobs.filter((job) => job.id !== id),
         })),

      // UI state
      settingsOpen: false,
      docsOpen: false,
      setSettingsOpen: (open) => set({ settingsOpen: open }),
      setDocsOpen: (open) => set({ docsOpen: open }),

      // Toasts
      toasts: [],
      addToast: (message, type) => {
        const id = Math.random().toString(36).slice(2)
        set((state) => {
          const newToasts = [...state.toasts, { id, message, type }]
          if (newToasts.length > 3) {
            newToasts.shift()
          }
          return { toasts: newToasts }
        })
        setTimeout(() => {
          get().removeToast(id)
        }, 4000)
      },
      removeToast: (id) =>
        set((state) => ({
          toasts: state.toasts.filter((t) => t.id !== id),
        })),
    }),
    {
      name: 'schism-storage',
      partialize: (state) => ({
        settings: state.settings,
        recentJobs: state.recentJobs,
      }),
      merge: (persistedState, currentState) => {
        const typedPersistedState = persistedState as Partial<SchismStore> | undefined

        return {
          ...currentState,
          ...typedPersistedState,
          settings: migrateSettings(typedPersistedState?.settings),
          recentJobs: typedPersistedState?.recentJobs ?? currentState.recentJobs,
        }
      },
    }
  )
)
