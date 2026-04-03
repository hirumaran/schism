'use client'

import { useStore } from '@/lib/store'

export function ProviderBadge() {
  const { settings, setSettingsOpen } = useStore()

  const getLabel = () => {
    switch (settings.provider) {
      case 'anthropic':
        return `Anthropic · ${settings.anthropicModel}`
      case 'openai':
        return `OpenAI · ${settings.openaiModel}`
      case 'ollama':
        return `Ollama · ${settings.ollamaModel}`
      case 'mock':
        return 'mock — results use heuristics'
    }
  }

  const isMock = settings.provider === 'mock'

  return (
    <button
      onClick={() => setSettingsOpen(true)}
      className={`text-sm ${isMock ? 'text-amber-600' : 'text-muted-foreground'} hover:underline`}
    >
      Provider: {getLabel()}
    </button>
  )
}
