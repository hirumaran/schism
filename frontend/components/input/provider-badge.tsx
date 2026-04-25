'use client'

import { useStore } from '@/lib/store'

export function ProviderBadge() {
  const { settings, setSettingsOpen } = useStore()

  const getLabel = () => {
    switch (settings.primaryProvider) {
      case 'anthropic':
        return `Anthropic · ${settings.anthropicModel}`
      case 'openai':
        return `OpenAI · ${settings.openaiModel}`
      case 'ollama':
        return `Ollama · ${settings.ollamaMode === 'cloud' ? settings.ollamaCloudModel : settings.ollamaLocalModel}`
      case 'mock':
        return 'mock — results use heuristics'
    }
  }

  const isMock = settings.primaryProvider === 'mock'

  return (
    <button
      onClick={() => setSettingsOpen(true)}
      className={`text-sm ${isMock ? 'text-warning' : 'text-muted-foreground'} hover:underline`}
    >
      Provider: {getLabel()}
    </button>
  )
}
