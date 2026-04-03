'use client'

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Settings, JobSummary, Toast } from './types'

interface SchismStore {
  // Settings
  settings: Settings
  updateSettings: (partial: Partial<Settings>) => void

  // Recent jobs (persist last 10)
  recentJobs: JobSummary[]
  addRecentJob: (job: JobSummary) => void
  updateRecentJob: (id: string, partial: Partial<JobSummary>) => void

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

const defaultSettings: Settings = {
  provider: 'mock',
  apiKey: '',
  model: 'claude-sonnet-4-6',
  embeddingProvider: 'local',
  baseUrl: 'http://localhost:11434',
  anthropicModel: 'claude-sonnet-4-6',
  openaiModel: 'gpt-4o-mini',
  ollamaModel: 'llama3',
  cohereKey: '',
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

      // UI state
      settingsOpen: false,
      docsOpen: false,
      setSettingsOpen: (open) => set({ settingsOpen: open }),
      setDocsOpen: (open) => set({ docsOpen: open }),

      // Toasts
      toasts: [],
      addToast: (message, type) => {
        const id = Math.random().toString(36).slice(2)
        set((state) => ({
          toasts: [...state.toasts, { id, message, type }].slice(-3),
        }))
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
    }
  )
)
