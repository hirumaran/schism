'use client'

import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import { useStore } from '@/lib/store'
import { validateKey, testOllamaConnection } from '@/lib/api'
import type { Provider, EmbeddingProvider } from '@/lib/types'

const ANTHROPIC_MODELS = [
  { value: 'claude-3-5-sonnet-latest', label: 'claude-3-5-sonnet-latest', desc: 'Backend default, balanced quality' },
  { value: 'claude-3-5-haiku-latest', label: 'claude-3-5-haiku-latest', desc: 'Fast and cheaper for larger jobs' },
]

const OPENAI_MODELS = [
  { value: 'gpt-4.1-mini', label: 'gpt-4.1-mini', desc: 'Backend default, best value' },
  { value: 'gpt-4.1', label: 'gpt-4.1', desc: 'Higher quality reasoning' },
  { value: 'gpt-4o-mini', label: 'gpt-4o-mini', desc: 'Alternative low-cost option' },
]

const OLLAMA_CHIPS = ['llama3.1', 'mistral', 'mixtral', 'phi3', 'gemma']

export function SettingsModal() {
  const { settings, updateSettings, settingsOpen, setSettingsOpen, addToast } = useStore()
  const [activeTab, setActiveTab] = useState<Provider>(settings.provider)
  const [localSettings, setLocalSettings] = useState(settings)
  const [validating, setValidating] = useState(false)
  const [validationResult, setValidationResult] = useState<'valid' | 'invalid' | 'error' | null>(null)
  const [ollamaModels, setOllamaModels] = useState<string[]>([])

  useEffect(() => {
    if (settingsOpen) {
      setLocalSettings(settings)
      setActiveTab(settings.provider)
      setValidationResult(null)
    }
  }, [settingsOpen, settings])

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSettingsOpen(false)
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [setSettingsOpen])

  if (!settingsOpen) return null

  const handleTabChange = (tab: Provider) => {
    setActiveTab(tab)
    setLocalSettings((s) => ({ ...s, provider: tab }))
    setValidationResult(null)
  }

  const handleValidate = async () => {
    setValidating(true)
    setValidationResult(null)
    try {
      const valid = await validateKey(localSettings)
      setValidationResult(valid ? 'valid' : 'invalid')
    } catch {
      setValidationResult('error')
    }
    setValidating(false)
  }

  const handleTestOllama = async () => {
    setValidating(true)
    setValidationResult(null)
    try {
      const result = await testOllamaConnection(localSettings.baseUrl)
      setOllamaModels(result.models)
      setValidationResult('valid')
    } catch {
      setValidationResult('error')
    }
    setValidating(false)
  }

  const handleSave = () => {
    const finalModel =
      localSettings.provider === 'anthropic'
        ? localSettings.anthropicModel
        : localSettings.provider === 'openai'
          ? localSettings.openaiModel
          : localSettings.ollamaModel
    const finalSettings = { ...localSettings, model: finalModel }
    setLocalSettings(finalSettings)
    updateSettings(finalSettings)
    addToast('Settings saved', 'success')
    setSettingsOpen(false)
  }

  return (
    <div className="fixed inset-0 z-50">
      <div
        className="absolute inset-0 bg-black/50"
        onClick={() => setSettingsOpen(false)}
      />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-[560px] bg-background border border-border rounded-lg shadow-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b border-border">
          <h2 className="font-serif text-xl">API settings</h2>
          <button
            onClick={() => setSettingsOpen(false)}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex border-b border-border">
          {(['anthropic', 'openai', 'ollama', 'mock'] as Provider[]).map((tab) => (
            <button
              key={tab}
              onClick={() => handleTabChange(tab)}
              className={`flex-1 py-3 text-sm capitalize ${
                activeTab === tab
                  ? 'border-b-2 border-foreground font-medium'
                  : 'text-muted-foreground'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        <div className="p-6 space-y-6">
          {activeTab === 'anthropic' && (
            <>
              <p className="text-sm text-muted-foreground">
                Anthropic Claude models. Your key is never stored on any server - it&apos;s sent directly from your browser to the Anthropic API via the Schism backend.
              </p>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1">API key</label>
                  <input
                    type="password"
                    placeholder="sk-ant-..."
                    value={localSettings.apiKey}
                    onChange={(e) =>
                      setLocalSettings((s) => ({ ...s, apiKey: e.target.value }))
                    }
                    className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background"
                  />
                  <a
                    href="https://console.anthropic.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-muted-foreground hover:underline"
                  >
                    Get your key at console.anthropic.com
                  </a>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Model</label>
                  <select
                    value={localSettings.anthropicModel}
                    onChange={(e) =>
                      setLocalSettings((s) => ({ ...s, anthropicModel: e.target.value }))
                    }
                    className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background"
                  >
                    {ANTHROPIC_MODELS.map((m) => (
                      <option key={m.value} value={m.value}>
                        {m.label}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-muted-foreground mt-1">
                    {ANTHROPIC_MODELS.find((m) => m.value === localSettings.anthropicModel)?.desc}
                  </p>
                </div>
                <button
                  onClick={handleValidate}
                  disabled={validating || !localSettings.apiKey}
                  className="px-4 py-2 text-sm border border-border rounded-md hover:bg-accent disabled:opacity-50"
                >
                  {validating ? 'Checking...' : 'Check backend connection'}
                </button>
                {validationResult === 'valid' && (
                  <p className="text-sm text-green-600">Backend is reachable</p>
                )}
                {validationResult === 'invalid' && (
                  <p className="text-sm text-red-600">Backend check failed</p>
                )}
                {validationResult === 'error' && (
                  <p className="text-sm text-red-600">Could not reach the Schism backend</p>
                )}
              </div>
            </>
          )}

          {activeTab === 'openai' && (
            <>
              <p className="text-sm text-muted-foreground">
                OpenAI models. Used for claim extraction and contradiction scoring. Local sentence-transformers are used for embeddings by default unless you change the embedding setting below.
              </p>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1">API key</label>
                  <input
                    type="password"
                    placeholder="sk-..."
                    value={localSettings.apiKey}
                    onChange={(e) =>
                      setLocalSettings((s) => ({ ...s, apiKey: e.target.value }))
                    }
                    className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background"
                  />
                  <a
                    href="https://platform.openai.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-muted-foreground hover:underline"
                  >
                    Get your key at platform.openai.com
                  </a>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Model</label>
                  <select
                    value={localSettings.openaiModel}
                    onChange={(e) =>
                      setLocalSettings((s) => ({ ...s, openaiModel: e.target.value }))
                    }
                    className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background"
                  >
                    {OPENAI_MODELS.map((m) => (
                      <option key={m.value} value={m.value}>
                        {m.label}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-muted-foreground mt-1">
                    {OPENAI_MODELS.find((m) => m.value === localSettings.openaiModel)?.desc}
                  </p>
                </div>
                <button
                  onClick={handleValidate}
                  disabled={validating || !localSettings.apiKey}
                  className="px-4 py-2 text-sm border border-border rounded-md hover:bg-accent disabled:opacity-50"
                >
                  {validating ? 'Checking...' : 'Check backend connection'}
                </button>
                {validationResult === 'valid' && (
                  <p className="text-sm text-green-600">Backend is reachable</p>
                )}
                {validationResult === 'invalid' && (
                  <p className="text-sm text-red-600">Backend check failed</p>
                )}
                {validationResult === 'error' && (
                  <p className="text-sm text-red-600">Could not reach the Schism backend</p>
                )}
              </div>
            </>
          )}

          {activeTab === 'ollama' && (
            <>
              <p className="text-sm text-muted-foreground">
                Run models locally with Ollama. No API key needed. Ollama must be running on your machine or network. Results are slower but completely free and private.
              </p>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Ollama base URL</label>
                  <input
                    type="text"
                    placeholder="http://localhost:11434"
                    value={localSettings.baseUrl}
                    onChange={(e) =>
                      setLocalSettings((s) => ({ ...s, baseUrl: e.target.value }))
                    }
                    className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Change this if Ollama runs on another machine
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Model</label>
                  <input
                    type="text"
                    placeholder="llama3.1"
                    value={localSettings.ollamaModel}
                    onChange={(e) =>
                      setLocalSettings((s) => ({ ...s, ollamaModel: e.target.value }))
                    }
                    className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Must be pulled in Ollama first: ollama pull llama3.1
                  </p>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {OLLAMA_CHIPS.map((chip) => (
                      <button
                        key={chip}
                        onClick={() =>
                          setLocalSettings((s) => ({ ...s, ollamaModel: chip }))
                        }
                        className="px-3 py-1 text-xs border border-border rounded-full hover:bg-accent"
                      >
                        {chip}
                      </button>
                    ))}
                  </div>
                </div>
                <button
                  onClick={handleTestOllama}
                  disabled={validating}
                  className="px-4 py-2 text-sm border border-border rounded-md hover:bg-accent disabled:opacity-50"
                >
                  {validating ? 'Testing...' : 'Test connection'}
                </button>
                {validationResult === 'valid' && ollamaModels.length > 0 && (
                  <p className="text-sm text-green-600">
                    Connected - {ollamaModels.length} models available
                  </p>
                )}
                {validationResult === 'error' && (
                  <p className="text-sm text-red-600">
                    Cannot connect to Ollama at {localSettings.baseUrl}
                  </p>
                )}
              </div>
            </>
          )}

          {activeTab === 'mock' && (
            <>
              <p className="text-sm text-muted-foreground">
                Mock mode uses Schism&apos;s built-in heuristic pipeline. No external LLM is called. Claims are extracted with keyword heuristics and contradictions are detected by direction comparison only. Results are lower quality but work without any API key.
              </p>
              <div className="p-4 bg-accent/50 rounded-md">
                <p className="text-sm">
                  Mock mode is active. Paper ingestion from arXiv, Semantic Scholar, PubMed, and OpenAlex still works fully. Only the LLM claim extraction and contradiction scoring steps use heuristics instead of a real model.
                </p>
              </div>
            </>
          )}

          <div className="pt-6 border-t border-border">
            <label className="block text-sm font-medium mb-2">Embedding provider</label>
            <p className="text-xs text-muted-foreground mb-3">
              Used to cluster papers by topic. Local is free and runs on your machine. Requires the sentence-transformers Python package.
            </p>
            <div className="space-y-3">
              {[
                { value: 'local', label: 'Local (sentence-transformers)', desc: 'Free, no key needed. Runs on CPU. Slightly slower.' },
                { value: 'openai', label: 'OpenAI (text-embedding-3-small)', desc: 'Fast, high quality. Uses your OpenAI key above.' },
                { value: 'cohere', label: 'Cohere (embed-english-v3.0)', desc: 'Requires a Cohere API key.' },
              ].map((option) => (
                <label key={option.value} className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="radio"
                    name="embedding"
                    checked={localSettings.embeddingProvider === option.value}
                    onChange={() =>
                      setLocalSettings((s) => ({
                        ...s,
                        embeddingProvider: option.value as EmbeddingProvider,
                      }))
                    }
                    className="mt-1"
                  />
                  <div>
                    <span className="text-sm font-medium">{option.label}</span>
                    <p className="text-xs text-muted-foreground">{option.desc}</p>
                    {option.value === 'cohere' && localSettings.embeddingProvider === 'cohere' && (
                      <input
                        type="password"
                        placeholder="Cohere API key"
                        value={localSettings.cohereKey}
                        onChange={(e) =>
                          setLocalSettings((s) => ({ ...s, cohereKey: e.target.value }))
                        }
                        className="mt-2 w-full px-3 py-2 border border-border rounded-md text-sm bg-background"
                      />
                    )}
                  </div>
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="p-6 border-t border-border">
          <button
            onClick={handleSave}
            className="w-full py-3 bg-foreground text-background rounded-md text-sm font-medium hover:bg-foreground/90"
          >
            Save settings
          </button>
          <p className="text-xs text-muted-foreground text-center mt-3">
            Settings are stored locally in your browser only. API keys are never sent to Schism servers.
          </p>
        </div>
      </div>
    </div>
  )
}
