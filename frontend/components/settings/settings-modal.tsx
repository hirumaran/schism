'use client'

import { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import { useStore } from '@/lib/store'
import { DEFAULT_OLLAMA_CLOUD_BASE_URL, validateKey, testOllamaConnection } from '@/lib/api'
import type { Provider, EmbeddingProvider, OllamaMode, Settings } from '@/lib/types'

const ANTHROPIC_FALLBACK_MODELS = ['claude-opus-4-6', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001']

const OPENAI_FALLBACK_MODELS = ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo']

const OLLAMA_CHIPS = ['llama3.1', 'mistral', 'mixtral', 'phi3', 'gemma']

const PROVIDER_LABELS: Record<Provider, string> = {
  anthropic: 'Anthropic',
  openai: 'OpenAI',
  ollama: 'Ollama',
  mock: 'Mock',
}

function sortModels(models: string[]) {
  return [...new Set(models)].sort((a, b) => a.localeCompare(b))
}

function getSelectedModel(models: string[], currentModel: string) {
  return models.includes(currentModel) ? currentModel : (models[0] ?? currentModel)
}

function getOllamaModel(settings: Settings) {
  return settings.ollamaMode === 'cloud' ? settings.ollamaCloudModel : settings.ollamaLocalModel
}

function getOllamaBaseUrl(settings: Settings) {
  return settings.ollamaMode === 'cloud'
    ? DEFAULT_OLLAMA_CLOUD_BASE_URL
    : settings.ollamaLocalBaseUrl
}

function getOllamaApiKey(settings: Settings) {
  return settings.ollamaMode === 'cloud' ? settings.ollamaCloudApiKey : ''
}

async function fetchAnthropicModels(apiKey: string) {
  const response = await fetch('https://api.anthropic.com/v1/models', {
    headers: {
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
    },
  })

  if (!response.ok) {
    throw new Error('Failed to fetch Anthropic models')
  }

  const data = await response.json()
  if (!Array.isArray(data?.models)) {
    throw new Error('Invalid Anthropic models response')
  }

  return sortModels(
    data.models
      .map((model: { id?: string }) => model.id)
      .filter((id: string | undefined): id is string => typeof id === 'string' && id.startsWith('claude-'))
  )
}

async function fetchOpenAIModels(apiKey: string) {
  const response = await fetch('https://api.openai.com/v1/models', {
    headers: {
      Authorization: `Bearer ${apiKey}`,
    },
  })

  if (!response.ok) {
    throw new Error('Failed to fetch OpenAI models')
  }

  const data = await response.json()
  if (!Array.isArray(data?.data)) {
    throw new Error('Invalid OpenAI models response')
  }

  return sortModels(
    data.data
      .map((model: { id?: string }) => model.id)
      .filter(
        (id: string | undefined): id is string =>
          typeof id === 'string' && (id.includes('gpt-4') || id.includes('gpt-3.5'))
      )
  )
}

export function SettingsModal() {
  const { settings, updateSettings, settingsOpen, setSettingsOpen, addToast } = useStore()
  const [activeTab, setActiveTab] = useState<Provider>(settings.primaryProvider)
  const [localSettings, setLocalSettings] = useState(settings)
  const [validating, setValidating] = useState(false)
  const [validationResult, setValidationResult] = useState<'valid' | 'invalid' | 'error' | null>(null)
  const [ollamaModels, setOllamaModels] = useState<string[]>([])
  const [anthropicModels, setAnthropicModels] = useState<string[]>([])
  const [openaiModels, setOpenaiModels] = useState<string[]>([])
  const [fetchingModels, setFetchingModels] = useState(false)
  const [ollamaValidationMessage, setOllamaValidationMessage] = useState<string | null>(null)
  const validationRequestId = useRef(0)
  const isOllamaCloud = localSettings.ollamaMode === 'cloud'
  const currentOllamaModel = getOllamaModel(localSettings)

  const resetOllamaValidation = () => {
    validationRequestId.current += 1
    setValidating(false)
    setFetchingModels(false)
    setValidationResult(null)
    setOllamaValidationMessage(null)
    setOllamaModels([])
  }

  useEffect(() => {
    if (settingsOpen) {
      validationRequestId.current += 1
      setLocalSettings(settings)
      setActiveTab(settings.primaryProvider)
      setValidating(false)
      setValidationResult(null)
      setAnthropicModels([])
      setOpenaiModels([])
      setOllamaModels([])
      setFetchingModels(false)
      setOllamaValidationMessage(null)
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
    validationRequestId.current += 1
    setActiveTab(tab)
    setValidating(false)
    setValidationResult(null)
    setAnthropicModels([])
    setOpenaiModels([])
    setOllamaModels([])
    setFetchingModels(false)
    setOllamaValidationMessage(null)
  }

  const handleValidate = async () => {
    const requestId = ++validationRequestId.current
    setValidating(true)
    setValidationResult(null)
    setOllamaValidationMessage(null)
    try {
      const valid = await validateKey(localSettings, activeTab)
      if (requestId !== validationRequestId.current) return
      if (valid) {
        setValidationResult('valid')
        setFetchingModels(true)
        try {
          if (activeTab === 'anthropic') {
            const models = await fetchAnthropicModels(localSettings.anthropicApiKey)
            if (requestId !== validationRequestId.current) return
            setAnthropicModels(models)
            if (models.length > 0) {
              setLocalSettings((s) => ({
                ...s,
                anthropicModel: getSelectedModel(models, s.anthropicModel),
              }))
            }
          } else if (activeTab === 'openai') {
            const models = await fetchOpenAIModels(localSettings.openaiApiKey)
            if (requestId !== validationRequestId.current) return
            setOpenaiModels(models)
            if (models.length > 0) {
              setLocalSettings((s) => ({
                ...s,
                openaiModel: getSelectedModel(models, s.openaiModel),
              }))
            }
          }
        } catch {
          if (requestId !== validationRequestId.current) return
          if (activeTab === 'anthropic') {
            setAnthropicModels(ANTHROPIC_FALLBACK_MODELS)
            setLocalSettings((s) => ({
              ...s,
              anthropicModel: getSelectedModel(ANTHROPIC_FALLBACK_MODELS, s.anthropicModel),
            }))
          } else if (activeTab === 'openai') {
            setOpenaiModels(OPENAI_FALLBACK_MODELS)
            setLocalSettings((s) => ({
              ...s,
              openaiModel: getSelectedModel(OPENAI_FALLBACK_MODELS, s.openaiModel),
            }))
          }
        } finally {
          if (requestId === validationRequestId.current) {
            setFetchingModels(false)
          }
        }
      } else {
        setValidationResult('invalid')
      }
    } catch {
      if (requestId === validationRequestId.current) {
        setValidationResult('error')
      }
    }
    if (requestId === validationRequestId.current) {
      setValidating(false)
    }
  }

  const handleTestOllama = async () => {
    const requestId = ++validationRequestId.current
    const baseUrl = getOllamaBaseUrl(localSettings)
    const apiKey = getOllamaApiKey(localSettings)

    setValidating(true)
    setValidationResult(null)
    setOllamaValidationMessage(null)
    try {
      const result = await testOllamaConnection(baseUrl, apiKey)
      if (requestId !== validationRequestId.current) return

      const models = sortModels(result.models)
      setOllamaModels(models)
      if (models.length > 0) {
        setOllamaModels(models)
        setLocalSettings((s) => {
          const selectedModel = getSelectedModel(models, getOllamaModel(s))
          return s.ollamaMode === 'cloud'
            ? { ...s, ollamaCloudModel: selectedModel, ollamaModel: selectedModel }
            : { ...s, ollamaLocalModel: selectedModel, ollamaModel: selectedModel }
        })
      }

      setValidationResult('valid')
      setOllamaValidationMessage(
        isOllamaCloud
          ? models.length > 0
            ? `API key validated - ${models.length} models available`
            : 'API key validated. No cloud models were returned, so enter one manually.'
          : models.length > 0
            ? `Connected - ${models.length} models available`
            : 'Connected. No installed models were returned, so enter one manually.'
      )
    } catch (error) {
      if (requestId !== validationRequestId.current) return
      setOllamaModels([])
      setValidationResult('error')
      setOllamaValidationMessage(
        error instanceof Error
          ? error.message
          : isOllamaCloud
            ? 'Could not validate the Ollama Cloud API key'
            : `Cannot connect to Ollama at ${baseUrl}`
      )
    }
    if (requestId === validationRequestId.current) {
      setValidating(false)
    }
  }

  const handleSave = () => {
    const finalOllamaModel = getOllamaModel(localSettings)
    const finalSettings = {
      ...localSettings,
      ollamaModel: finalOllamaModel,
    }
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
              className={`flex-1 py-3 text-sm ${
                activeTab === tab
                  ? 'border-b-2 border-foreground font-medium'
                  : 'text-muted-foreground'
              }`}
            >
              {PROVIDER_LABELS[tab]}
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
                    value={localSettings.anthropicApiKey}
                    onChange={(e) => {
                      validationRequestId.current += 1
                      setValidating(false)
                      setFetchingModels(false)
                      setValidationResult(null)
                      setAnthropicModels([])
                      setLocalSettings((s) => ({ ...s, anthropicApiKey: e.target.value }))
                    }}
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
                  {anthropicModels.length > 0 ? (
                    <select
                      value={anthropicModels.includes(localSettings.anthropicModel) ? localSettings.anthropicModel : anthropicModels[0]}
                      onChange={(e) =>
                        setLocalSettings((s) => ({ ...s, anthropicModel: e.target.value }))
                      }
                      className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background"
                    >
                      {anthropicModels.map((id) => (
                        <option key={id} value={id}>{id}</option>
                      ))}
                    </select>
                  ) : (
                    <>
                      <input
                        type="text"
                        placeholder="e.g. claude-sonnet-4-6"
                        value={localSettings.anthropicModel}
                        onChange={(e) =>
                          setLocalSettings((s) => ({ ...s, anthropicModel: e.target.value }))
                        }
                        className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background"
                      />
                      <p className="text-xs text-muted-foreground mt-1">
                        Validate your key to see available models.
                      </p>
                    </>
                  )}
                </div>
                <button
                  onClick={handleValidate}
                  disabled={validating || fetchingModels || !localSettings.anthropicApiKey}
                  className="px-4 py-2 text-sm border border-border rounded-md hover:bg-accent disabled:opacity-50"
                >
                  {fetchingModels ? 'Fetching models...' : validating ? 'Checking...' : 'Check backend connection'}
                </button>
                {validationResult === 'valid' && (
                  <p className="text-sm text-success">Backend is reachable</p>
                )}
                {validationResult === 'invalid' && (
                  <p className="text-sm text-destructive">Backend check failed</p>
                )}
                {validationResult === 'error' && (
                  <p className="text-sm text-destructive">Could not reach the Schism backend</p>
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
                    value={localSettings.openaiApiKey}
                    onChange={(e) => {
                      validationRequestId.current += 1
                      setValidating(false)
                      setFetchingModels(false)
                      setValidationResult(null)
                      setOpenaiModels([])
                      setLocalSettings((s) => ({ ...s, openaiApiKey: e.target.value }))
                    }}
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
                  {openaiModels.length > 0 ? (
                    <select
                      value={openaiModels.includes(localSettings.openaiModel) ? localSettings.openaiModel : openaiModels[0]}
                      onChange={(e) =>
                        setLocalSettings((s) => ({ ...s, openaiModel: e.target.value }))
                      }
                      className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background"
                    >
                      {openaiModels.map((id) => (
                        <option key={id} value={id}>{id}</option>
                      ))}
                    </select>
                  ) : (
                    <>
                      <input
                        type="text"
                        placeholder="e.g. gpt-4o"
                        value={localSettings.openaiModel}
                        onChange={(e) =>
                          setLocalSettings((s) => ({ ...s, openaiModel: e.target.value }))
                        }
                        className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background"
                      />
                      <p className="text-xs text-muted-foreground mt-1">
                        Validate your key to see available models.
                      </p>
                    </>
                  )}
                </div>
                <button
                  onClick={handleValidate}
                  disabled={validating || fetchingModels || !localSettings.openaiApiKey}
                  className="px-4 py-2 text-sm border border-border rounded-md hover:bg-accent disabled:opacity-50"
                >
                  {fetchingModels ? 'Fetching models...' : validating ? 'Checking...' : 'Check backend connection'}
                </button>
                {validationResult === 'valid' && (
                  <p className="text-sm text-success">Backend is reachable</p>
                )}
                {validationResult === 'invalid' && (
                  <p className="text-sm text-destructive">Backend check failed</p>
                )}
                {validationResult === 'error' && (
                  <p className="text-sm text-destructive">Could not reach the Schism backend</p>
                )}
              </div>
            </>
          )}

          {activeTab === 'ollama' && (
            <>
              <p className="text-sm text-muted-foreground">
                {isOllamaCloud
                  ? 'Use Ollama Cloud with an API key. Validate the key to load cloud models, or type a model name manually if discovery is unavailable.'
                  : 'Run models locally with Ollama. No API key needed. Ollama must be running on your machine or network. Results are slower but completely free and private.'}
              </p>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Mode</label>
                  <div className="grid grid-cols-2 gap-2">
                    {([
                      { value: 'local', label: 'Local Ollama' },
                      { value: 'cloud', label: 'Ollama Cloud' },
                    ] as { value: OllamaMode; label: string }[]).map((mode) => (
                      <button
                        key={mode.value}
                        onClick={() => {
                          if (localSettings.ollamaMode === mode.value) return
                          resetOllamaValidation()
                          setLocalSettings((s) => ({
                            ...s,
                            ollamaMode: mode.value,
                            ollamaModel: mode.value === 'cloud' ? s.ollamaCloudModel : s.ollamaLocalModel,
                          }))
                        }}
                        className={`px-3 py-2 text-sm border border-border rounded-md ${
                          localSettings.ollamaMode === mode.value
                            ? 'bg-accent font-medium'
                            : 'text-muted-foreground'
                        }`}
                      >
                        {mode.label}
                      </button>
                    ))}
                  </div>
                </div>
                {isOllamaCloud ? (
                  <div>
                    <label className="block text-sm font-medium mb-1">API key</label>
                    <input
                      type="password"
                      placeholder="ollama_..."
                      value={localSettings.ollamaCloudApiKey}
                      onChange={(e) => {
                        resetOllamaValidation()
                        setLocalSettings((s) => ({ ...s, ollamaCloudApiKey: e.target.value }))
                      }}
                      className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Cloud requests use Bearer token auth against {DEFAULT_OLLAMA_CLOUD_BASE_URL}/api.
                    </p>
                  </div>
                ) : (
                  <div>
                    <label className="block text-sm font-medium mb-1">Ollama base URL</label>
                    <input
                      type="text"
                      placeholder="http://localhost:11434"
                      value={localSettings.ollamaLocalBaseUrl}
                      onChange={(e) => {
                        resetOllamaValidation()
                        setLocalSettings((s) => ({ ...s, ollamaLocalBaseUrl: e.target.value }))
                      }}
                      className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Change this if Ollama runs on another machine
                    </p>
                  </div>
                )}
                <div>
                  <label className="block text-sm font-medium mb-1">Model</label>
                  {ollamaModels.length > 0 ? (
                    <select
                      value={ollamaModels.includes(currentOllamaModel) ? currentOllamaModel : ollamaModels[0]}
                      onChange={(e) =>
                        setLocalSettings((s) =>
                          s.ollamaMode === 'cloud'
                            ? { ...s, ollamaCloudModel: e.target.value, ollamaModel: e.target.value }
                            : { ...s, ollamaLocalModel: e.target.value, ollamaModel: e.target.value }
                        )
                      }
                      className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background"
                    >
                      {ollamaModels.map((name) => (
                        <option key={name} value={name}>{name}</option>
                      ))}
                    </select>
                  ) : (
                    <>
                      <input
                        type="text"
                        placeholder={isOllamaCloud ? 'e.g. llama3.1' : 'llama3.1'}
                        value={currentOllamaModel}
                        onChange={(e) =>
                          setLocalSettings((s) =>
                            s.ollamaMode === 'cloud'
                              ? { ...s, ollamaCloudModel: e.target.value, ollamaModel: e.target.value }
                              : { ...s, ollamaLocalModel: e.target.value, ollamaModel: e.target.value }
                          )
                        }
                        className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background"
                      />
                      {isOllamaCloud ? (
                        <p className="text-xs text-muted-foreground mt-1">
                          Validate your API key to see available models.
                        </p>
                      ) : (
                        <>
                          <p className="text-xs text-muted-foreground mt-1">
                            Must be pulled in Ollama first: ollama pull llama3.1
                          </p>
                          <div className="flex flex-wrap gap-2 mt-2">
                            {OLLAMA_CHIPS.map((chip) => (
                              <button
                                key={chip}
                                onClick={() =>
                                  setLocalSettings((s) => ({
                                    ...s,
                                    ollamaLocalModel: chip,
                                    ollamaModel: chip,
                                  }))
                                }
                                className="px-3 py-1 text-xs border border-border rounded-full hover:bg-accent"
                              >
                                {chip}
                              </button>
                            ))}
                          </div>
                        </>
                      )}
                    </>
                  )}
                </div>
                <button
                  onClick={handleTestOllama}
                  disabled={validating || (isOllamaCloud ? !localSettings.ollamaCloudApiKey : !localSettings.ollamaLocalBaseUrl)}
                  className="px-4 py-2 text-sm border border-border rounded-md hover:bg-accent disabled:opacity-50"
                >
                  {validating
                    ? (isOllamaCloud ? 'Validating...' : 'Testing...')
                    : (isOllamaCloud ? 'Validate key' : 'Test connection')}
                </button>
                {validationResult === 'valid' && ollamaValidationMessage && (
                  <p className="text-sm text-success">{ollamaValidationMessage}</p>
                )}
                {validationResult === 'error' && ollamaValidationMessage && (
                  <p className="text-sm text-destructive">{ollamaValidationMessage}</p>
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

          <div className="pt-6 border-t border-border">
            <label className="block text-sm font-medium mb-3">Primary provider</label>
            <p className="text-xs text-muted-foreground mb-3">
              Schism uses this provider for all LLM calls. Select a provider that is configured above.
            </p>
            <div className="grid grid-cols-2 gap-2">
              {(['anthropic', 'openai', 'ollama', 'mock'] as Provider[]).map((p) => {
                const isConfigured = p === 'mock' || (
                  p === 'anthropic' ? Boolean(localSettings.anthropicApiKey) :
                  p === 'openai' ? Boolean(localSettings.openaiApiKey) :
                  p === 'ollama' ? (localSettings.ollamaMode === 'cloud' ? Boolean(localSettings.ollamaCloudApiKey) : Boolean(localSettings.ollamaLocalBaseUrl)) :
                  true
                )
                const isPrimary = localSettings.primaryProvider === p
                return (
                  <button
                    key={p}
                    type="button"
                    onClick={() => {
                      if (!isConfigured) return
                      setLocalSettings((s) => ({ ...s, primaryProvider: p }))
                    }}
                    className={`px-3 py-2 text-sm border rounded-md text-left ${
                      isPrimary
                        ? 'border-foreground bg-accent font-medium'
                        : isConfigured
                          ? 'border-border hover:bg-accent'
                          : 'border-border opacity-40 cursor-not-allowed'
                    }`}
                  >
                    <span className="block font-medium">{PROVIDER_LABELS[p]}</span>
                    {isPrimary && <span className="text-xs text-muted-foreground">Primary</span>}
                    {!isConfigured && !isPrimary && <span className="text-xs text-muted-foreground">Not configured</span>}
                  </button>
                )
              })}
            </div>
            {!localSettings.anthropicApiKey && !localSettings.openaiApiKey &&
             (localSettings.ollamaMode === 'cloud' ? !localSettings.ollamaCloudApiKey : !localSettings.ollamaLocalBaseUrl) &&
             localSettings.primaryProvider !== 'mock' && (
              <p className="text-xs text-warning mt-2">
                No API keys detected. Configure a provider above or set Primary to &quot;Mock&quot;.
              </p>
            )}
          </div>

          <div className="pt-6 border-t border-border">
            <label className="block text-sm font-medium mb-3">Fallback provider (optional)</label>
            <p className="text-xs text-muted-foreground mb-3">
              If the primary provider fails with a retriable error (rate limit, service unavailable), Schism automatically retries with this provider.
            </p>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setLocalSettings((s) => ({ ...s, secondaryProvider: null }))}
                className={`px-3 py-2 text-sm border rounded-md text-left ${
                  localSettings.secondaryProvider === null
                    ? 'border-foreground bg-accent font-medium'
                    : 'border-border hover:bg-accent'
                }`}
              >
                <span className="block font-medium">None</span>
                <span className="text-xs text-muted-foreground">No fallback</span>
              </button>
              {(['anthropic', 'openai', 'ollama'] as Provider[]).map((p) => {
                const isConfigured = (
                  p === 'anthropic' ? Boolean(localSettings.anthropicApiKey) :
                  p === 'openai' ? Boolean(localSettings.openaiApiKey) :
                  p === 'ollama' ? (localSettings.ollamaMode === 'cloud' ? Boolean(localSettings.ollamaCloudApiKey) : Boolean(localSettings.ollamaLocalBaseUrl)) :
                  true
                )
                const isSecondary = localSettings.secondaryProvider === p
                const isPrimary = localSettings.primaryProvider === p
                return (
                  <button
                    key={p}
                    type="button"
                    onClick={() => {
                      if (!isConfigured || isPrimary) return
                      setLocalSettings((s) => ({ ...s, secondaryProvider: p }))
                    }}
                    className={`px-3 py-2 text-sm border rounded-md text-left ${
                      isSecondary
                        ? 'border-foreground bg-accent font-medium'
                        : isConfigured && !isPrimary
                          ? 'border-border hover:bg-accent'
                          : 'border-border opacity-40 cursor-not-allowed'
                    }`}
                  >
                    <span className="block font-medium">{PROVIDER_LABELS[p]}</span>
                    {isSecondary && <span className="text-xs text-muted-foreground">Fallback</span>}
                    {!isConfigured && !isSecondary && !isPrimary && <span className="text-xs text-muted-foreground">Not configured</span>}
                    {isPrimary && !isSecondary && <span className="text-xs text-muted-foreground">Primary only</span>}
                  </button>
                )
              })}
            </div>
            {localSettings.secondaryProvider === localSettings.primaryProvider && (
              <p className="text-xs text-destructive mt-2">Fallback cannot be the same as primary.</p>
            )}
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
