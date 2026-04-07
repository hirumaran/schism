'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { ModeToggle } from '@/components/input/mode-toggle'
import { QueryInput } from '@/components/input/query-input'
import { DropZone } from '@/components/input/drop-zone'
import { PasteArea } from '@/components/input/paste-area'
import { SourcePicker } from '@/components/input/source-picker'
import { ProviderBadge } from '@/components/input/provider-badge'
import { RecentJobs } from '@/components/input/recent-jobs'
import { useStore } from '@/lib/store'
import { analyzeQuery, analyzePaper, ApiError } from '@/lib/api'

type Mode = 'query' | 'paper'

export default function InputPage() {
  const router = useRouter()
  const { settings, addRecentJob, addToast, setSettingsOpen } = useStore()

  const [mode, setMode] = useState<Mode>('query')
  const [query, setQuery] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [text, setText] = useState('')
  const [title, setTitle] = useState('')
  const [sources, setSources] = useState(['arxiv', 'semantic_scholar', 'pubmed', 'openalex'])
  const [maxResults, setMaxResults] = useState(50)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async () => {
    setError(null)

    // Validation
    if (mode === 'query') {
      if (!query.trim()) {
        setError('Please enter a search query')
        return
      }
    } else {
      if (!file && !text.trim()) {
        setError('Please upload a file or paste text')
        return
      }
    }

    if (sources.length === 0) {
      setError('Please select at least one source')
      return
    }

    // Warn about mock mode
    if (settings.provider !== 'mock' && settings.provider !== 'ollama' && !settings.apiKey) {
      addToast('No API key set — using mock mode', 'info')
    }

    setLoading(true)

    try {
      let response
      if (mode === 'query') {
        response = await analyzeQuery(
          { query, max_results: maxResults, sources },
          settings
        )
      } else {
        console.log('Paper mode - file:', file?.name, 'text length:', text?.length)
        response = await analyzePaper(
          { file: file ?? undefined, text: text || undefined, title: title || undefined, max_results: maxResults, sources },
          settings
        )
      }

      addRecentJob({
        id: response.job_id,
        query: mode === 'query' ? query : title || 'Paper analysis',
        status: response.status,
        contradiction_count: 0,
        created_at: new Date().toISOString(),
      })

      router.push(`/jobs/${response.job_id}`)
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 400) {
          setError(err.detail || err.message)
        } else if (err.status === 401 || err.status === 403) {
          addToast('API key rejected. Check Settings.', 'error')
          setSettingsOpen(true)
        } else if (err.status === 502) {
          addToast('LLM provider error. Your API key may be invalid or rate-limited.', 'error')
        } else {
          addToast(`Analysis failed: ${err.message}`, 'error')
        }
      } else {
        addToast('Cannot reach the Schism backend. Check NEXT_PUBLIC_API_URL and that the API server is running.', 'error')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="pt-20 pb-16 px-6">
      <div className="max-w-[680px] mx-auto">
        <div className="text-center">
          <h1 className="font-serif text-5xl font-normal">Schism</h1>
          <p className="mt-2 text-lg text-muted-foreground">
            Find papers that contradict each other.
          </p>
        </div>

        <ModeToggle mode={mode} onModeChange={setMode} />

        <div className="mt-8 space-y-4">
          {mode === 'query' ? (
            <QueryInput value={query} onChange={setQuery} onSubmit={handleSubmit} />
          ) : (
            <>
              <DropZone file={file} onFileChange={setFile} />
              <div className="flex items-center gap-4">
                <div className="flex-1 h-px bg-border" />
                <span className="text-sm text-muted-foreground">or</span>
                <div className="flex-1 h-px bg-border" />
              </div>
              <PasteArea value={text} onChange={setText} />
              <div>
                <label className="block text-sm font-medium mb-1">
                  Paper title (optional)
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Helps with result labeling"
                  className="w-full h-11 px-4 text-sm border border-border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            </>
          )}

          <SourcePicker
            selected={sources}
            onChange={setSources}
            maxResults={maxResults}
            onMaxResultsChange={setMaxResults}
          />

          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}

          <div className="pt-4 space-y-3">
            <ProviderBadge />
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="w-full h-[52px] bg-foreground text-background text-base font-medium rounded-md hover:bg-foreground/90 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Starting analysis...' : mode === 'query' ? 'Analyze' : 'Analyze paper'}
            </button>
          </div>

          <RecentJobs />
        </div>
      </div>
    </div>
  )
}
